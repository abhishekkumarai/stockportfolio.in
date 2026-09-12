"""Fyers API v3 client (market data + login flow).

Fyers is a broker API, so unlike mfapi.in every data call needs a per-user access
token obtained through an interactive OAuth login:

    1. build_auth_url()  -> the user opens this and logs in with their Fyers ID,
                            PIN and TOTP. Only the account holder can do this.
    2. Fyers redirects to FYERS_REDIRECT_URI with ?auth_code=... in the query.
    3. exchange_auth_code(code) -> access token, valid for one day. Fyers does not
                            officially document the exact expiry time, so treat it
                            as "expires daily" and re-authenticate on 401.

The same response also carries a refresh_token (15-day validity) which can mint a
new access token without a full login — but Fyers requires the account PIN in that
call, so it is stored here and left for the account holder to use deliberately.

The token is what authorises data calls; the app secret only ever appears inside
the SHA-256 appIdHash sent at step 3, never in a data request.
"""

import hashlib
import logging
import os
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

# curl_cffi rather than requests: it is already a declared dependency, whereas
# requests is only present transitively via yfinance.
from curl_cffi import requests

from app.rate_limit import RateLimiter, RateLimitExceeded, fyers_limiter

logger = logging.getLogger(__name__)

AUTH_BASE = "https://api-t1.fyers.in/api/v3"
DATA_BASE = "https://api-t1.fyers.in/data"

# Maximum span Fyers accepts in a single /history call, established by bisecting
# the live API rather than trusting the docs (which say 366 for daily):
#   1D       -> 367 days OK, 368 rejected with "Invalid input"
#   intraday -> 100 days OK, 101 rejected
# Chunking uses slightly less to leave room for the boundaries being inclusive.
MAX_DAYS_DAILY = 365
MAX_DAYS_INTRADAY = 99

# Fyers rejects a quotes call carrying more than 50 symbols.
MAX_QUOTE_SYMBOLS = 50

DateLike = Union[str, date, datetime]


def _as_date(value: DateLike) -> date:
    """Coerce YYYY-MM-DD strings, datetimes and dates to a plain date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()


def _is_daily(resolution: str) -> bool:
    """True for the daily resolution, which has a wider window than intraday."""
    return str(resolution).strip().upper() in {"1D", "D", "DAY"}


class FyersError(Exception):
    """Raised when Fyers rejects a request or is unreachable."""


class FyersAuthError(FyersError):
    """Raised when the access token is missing, expired or invalid."""


class FyersRateLimitError(FyersError):
    """Raised when our own throttle says the request would breach Fyers' quota."""


class FyersClient:
    def __init__(
        self,
        app_id: Optional[str] = None,
        secret_id: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: int = 15,
        limiter: Optional[RateLimiter] = None,
        max_throttle_wait: float = 20.0,
    ):
        auth_disabled = (
            os.getenv("DISABLE_AUTH", "").lower() in ("true", "1", "yes")
            or os.getenv("AUTH_DISABLED", "").lower() in ("true", "1", "yes")
        )
        self.app_id = app_id or os.getenv("FYERS_APP_ID", "") or ("DOCKER-DEV-APP-ID" if auth_disabled else "")
        self.secret_id = secret_id or os.getenv("FYERS_SECRET_ID", "") or ("DOCKER-DEV-SECRET" if auth_disabled else "")
        self.redirect_uri = redirect_uri or os.getenv("FYERS_REDIRECT_URI", "")
        self.access_token = access_token or os.getenv("FYERS_ACCESS_TOKEN", "") or ("DOCKER-LOCAL-DEV-TOKEN" if auth_disabled else "")
        self.refresh_token = ""
        self._timeout = timeout
        # Shared by default: the quota belongs to the app key, and a new client
        # is built per request, so a per-instance limiter would count nothing.
        self._limiter = limiter or fyers_limiter
        self._max_throttle_wait = max_throttle_wait

        if not self.app_id and not auth_disabled:
            raise FyersError("FYERS_APP_ID is not set")

    # ---- login flow ------------------------------------------------------

    def build_auth_url(self, state: str = "sp") -> str:
        """URL the account holder opens to log in. Returns ?auth_code=... on redirect."""
        # urlencode, not f-string interpolation: the redirect URI contains "://"
        # and may carry its own query, which must not leak into these params.
        params = urllib.parse.urlencode(
            {
                "client_id": self.app_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "state": state,
            }
        )
        return f"{AUTH_BASE}/generate-authcode?{params}"

    def _app_id_hash(self) -> str:
        """SHA-256 of "app_id:secret_id" — how Fyers wants the secret presented."""
        if not self.secret_id:
            raise FyersError("FYERS_SECRET_ID is not set")
        return hashlib.sha256(f"{self.app_id}:{self.secret_id}".encode()).hexdigest()

    def exchange_auth_code(self, auth_code: str) -> str:
        """Swap the one-time auth_code from the redirect for an access token."""
        response = requests.post(
            f"{AUTH_BASE}/validate-authcode",
            json={
                "grant_type": "authorization_code",
                "appIdHash": self._app_id_hash(),
                "code": auth_code,
            },
            timeout=self._timeout,
        )
        payload = response.json()
        if payload.get("s") != "ok" or not payload.get("access_token"):
            raise FyersAuthError(
                f"Fyers rejected the auth code: {payload.get('message') or payload}"
            )
        self.access_token = payload["access_token"]
        # Kept so a 15-day refresh is possible without repeating the full login.
        self.refresh_token = payload.get("refresh_token", "")
        return self.access_token

    # ---- data ------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        if not self.access_token:
            raise FyersAuthError(
                "No Fyers access token. Complete the login flow and set FYERS_ACCESS_TOKEN."
            )
        # The "version" header is required by v3; without it Fyers can fall back
        # to older behaviour. Matches what the official SDK sends.
        return {
            "Authorization": f"{self.app_id}:{self.access_token}",
            "Content-Type": "application/json",
            "version": "3",
        }

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Built outside the try: a missing token is an auth error, not a network one.
        headers = self._headers()

        # Throttle before the call, not after a rejection: Fyers counts requests
        # that it rate-limits, so backing off only once refused digs the hole
        # deeper. Waiting here costs latency and keeps the quota intact.
        try:
            waited = self._limiter.acquire(max_wait=self._max_throttle_wait)
        except RateLimitExceeded as exc:
            raise FyersRateLimitError(str(exc)) from exc
        if waited > 1.0:
            logger.info("Throttled %.1fs before calling Fyers %s", waited, url)

        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=self._timeout
            )
        except Exception as exc:
            raise FyersError(f"Could not reach Fyers: {exc}") from exc

        if response.status_code == 401:
            raise FyersAuthError("Fyers access token is invalid or has expired.")
        if response.status_code == 429:
            # We throttle locally, so this means the limiter's ceiling is still
            # too high — most likely several workers sharing one app key.
            raise FyersRateLimitError(
                "Fyers rejected the request as rate limited (HTTP 429)."
            )

        payload = response.json()
        if payload.get("s") == "error" or payload.get("code", 0) < 0:
            message = payload.get("message", payload)
            # Fyers signals an expired daily token through the message body.
            if "token" in str(message).lower():
                raise FyersAuthError(str(message))
            raise FyersError(str(message))
        return payload

    def profile(self) -> Dict[str, Any]:
        """Account holder details. The cheapest way to verify a token works."""
        return self._get(f"{AUTH_BASE}/profile")

    def quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Live quotes, e.g. ["NSE:SBIN-EQ", "NSE:NIFTY50-INDEX"].

        Fyers caps a single call at 50 symbols, so longer lists are split and
        the `d` arrays concatenated. Callers get one result regardless of how
        many round trips it took.
        """
        if not symbols:
            return {"s": "ok", "d": []}
        if len(symbols) <= MAX_QUOTE_SYMBOLS:
            return self._get(f"{DATA_BASE}/quotes", {"symbols": ",".join(symbols)})

        merged: List[Any] = []
        for start in range(0, len(symbols), MAX_QUOTE_SYMBOLS):
            chunk = symbols[start : start + MAX_QUOTE_SYMBOLS]
            payload = self._get(f"{DATA_BASE}/quotes", {"symbols": ",".join(chunk)})
            merged.extend(payload.get("d") or [])
        return {"s": "ok", "d": merged}

    def holdings(self) -> Dict[str, Any]:
        """Delivery holdings: what the account actually owns.

        Returns {"overall": {...totals...}, "holdings": [...]}. Each holding
        carries symbol, quantity, costPrice, ltp, marketVal, pl and isin —
        but *not* a purchase date, so per-holding XIRR is impossible from this
        source alone. The user supplies buy dates in the UI when they want it.
        """
        return self._get(f"{AUTH_BASE}/holdings")

    def positions(self) -> Dict[str, Any]:
        """Intraday and F&O positions — distinct from delivery holdings."""
        return self._get(f"{AUTH_BASE}/positions")

    def funds(self) -> Dict[str, Any]:
        """Available margin and cash balance.

        Note: this endpoint has been observed hanging upstream (connection
        opens, no bytes, times out) while holdings and positions respond
        normally. Callers should treat a failure here as non-fatal — cash
        balance is a nice-to-have next to the holdings themselves.
        """
        return self._get(f"{AUTH_BASE}/funds")

    def option_chain(
        self,
        symbol: str,
        strike_count: int = 10,
        timestamp: str = "",
    ) -> Dict[str, Any]:
        """Live option chain for an index or F&O stock.

        Uses Fyers' authenticated endpoint rather than scraping NSE. The NSE
        site sits behind a cookie/JS wall that has to be re-solved every time
        it changes, and a broker API that returns the same data under a token
        we already hold is strictly better.

        `strike_count` is strikes *per side* of the at-the-money strike, so 10
        returns roughly 21 strikes. `timestamp` selects an expiry (Fyers'
        `expiryData` epoch); empty means the nearest expiry.

        Response shape: `{"data": {"expiryData": [...], "optionsChain": [...],
        "callOi": n, "putOi": n, "indiavixData": {...}}}`, where each
        optionsChain row carries `symbol`, `strike_price`, `option_type`
        ("CE"/"PE"), `ltp`, `oi`, `prev_oi`, `volume`, `bid`, `ask`, `ltpch`.
        The first row has `option_type: ""` and is the underlying itself.
        """
        params: Dict[str, Any] = {"symbol": symbol, "strikecount": strike_count}
        if timestamp:
            params["timestamp"] = timestamp
        return self._get(f"{DATA_BASE}/options-chain-v3", params)

    def history(
        self,
        symbol: str,
        resolution: str = "1D",
        range_from: str = "",
        range_to: str = "",
    ) -> Dict[str, Any]:
        """OHLCV candles. Dates as YYYY-MM-DD.

        Valid resolutions per the official SDK: "1D" (or "Day") and the minute
        values "1", "2", "3", "5", "10", "15", "20", "30", "60", "120", "240".
        A bare "D" is not among them.
        """
        return self._get(
            f"{DATA_BASE}/history",
            {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": 1,
                "range_from": range_from,
                "range_to": range_to,
                "cont_flag": 1,
            },
        )

    def history_range(
        self,
        symbol: str,
        resolution: str = "1D",
        range_from: Optional[DateLike] = None,
        range_to: Optional[DateLike] = None,
    ) -> Dict[str, Any]:
        """History over any span, chunked around Fyers' per-call window limit.

        A single /history call is capped (367 days daily, 100 intraday), so
        asking for five years silently fails with "Invalid input". This splits
        the request, stitches the candles back together in chronological order
        and de-duplicates the overlaps at chunk boundaries.

        Every chunk costs a request against the daily quota, so a 10-year daily
        pull is 10 calls — worth remembering before fanning this out across a
        whole portfolio.
        """
        end = _as_date(range_to) if range_to else date.today()
        start = _as_date(range_from) if range_from else end - timedelta(days=MAX_DAYS_DAILY)

        if start > end:
            raise FyersError(f"range_from {start} is after range_to {end}")

        span = MAX_DAYS_DAILY if _is_daily(resolution) else MAX_DAYS_INTRADAY

        candles: List[List[Any]] = []
        seen_timestamps = set()
        chunk_start = start

        while chunk_start <= end:
            chunk_end = min(chunk_start + timedelta(days=span), end)
            payload = self.history(
                symbol, resolution, chunk_start.isoformat(), chunk_end.isoformat()
            )
            for candle in payload.get("candles") or []:
                # Boundaries are inclusive on both ends, so consecutive chunks
                # share a day. Keying on the timestamp drops the duplicate.
                if candle and candle[0] not in seen_timestamps:
                    seen_timestamps.add(candle[0])
                    candles.append(candle)
            if chunk_end >= end:
                break
            chunk_start = chunk_end + timedelta(days=1)

        candles.sort(key=lambda c: c[0])
        return {
            "s": "ok",
            "symbol": symbol,
            "resolution": resolution,
            "range_from": start.isoformat(),
            "range_to": end.isoformat(),
            "candles": candles,
        }
