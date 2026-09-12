"""Fyers login and market-data routes.

Token handling note. The access token used to be written into backend/.env by
the OAuth callback. That was wrong in three ways once deployed:

  * Render's filesystem is ephemeral, so the token vanished on every restart.
  * Multiple workers do not share a process environment, so one worker's login
    was invisible to the others.
  * The callback is necessarily unauthenticated — Fyers redirects a browser to
    it — so anyone who hit the deployed URL with their own auth code would
    overwrite the token every other user was relying on.

The token now belongs to the browser that logged in. The callback hands it back
in the redirect fragment, the frontend keeps it in sessionStorage, and every
subsequent call presents it as `X-Fyers-Token`. The server holds no user token
at all; concurrent users are naturally isolated because each carries their own.

The env var remains as a local-development fallback, and .env is still written
outside production so a restart during local work does not force another login.

Known tradeoff: a fragment token lands in browser history, and sessionStorage
is readable by any XSS on the frontend origin. Fixing that properly needs a
server-side session store, which arrives with Postgres in Phase 6. Until then
the exposure is one day of read-only market-data access on a token the account
holder can revoke by re-logging in.
"""

import logging
import os
import urllib.parse
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dotenv_lite import set_env_value
from app.fyers_client import (
    FyersAuthError,
    FyersClient,
    FyersError,
    FyersRateLimitError,
)
from app.schemas import HoldingsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fyers", tags=["Fyers"])

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def _is_production() -> bool:
    return os.getenv("ENV", "").lower() == "production"


def _is_auth_disabled() -> bool:
    return os.getenv("DISABLE_AUTH", "true").lower() in ("true", "1", "yes") and not _is_production()


def _frontend_origin() -> Optional[str]:
    """First configured frontend origin, used as the post-login redirect target."""
    raw = os.getenv("FRONTEND_ORIGIN", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins[0] if origins else None


def get_client(x_fyers_token: Optional[str] = Header(None)) -> Optional[FyersClient]:
    """Build a client for this request from the caller's own token.

    Falls back to FYERS_ACCESS_TOKEN so local development and scripts keep
    working without a browser round-trip. In production the header is the only
    real path — the env var is not set there.
    """
    token = x_fyers_token or os.getenv("FYERS_ACCESS_TOKEN")
    if not token:
        return None
    try:
        return FyersClient(access_token=token)
    except FyersError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _raise_for(exc: FyersError) -> HTTPException:
    """Map a client error onto the right status code."""
    if isinstance(exc, FyersAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, FyersRateLimitError):
        return HTTPException(status_code=429, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


def _page(title: str, body: str, ok: bool = True) -> HTMLResponse:
    colour = "#22c55e" if ok else "#ef4444"
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:system-ui,sans-serif;background:#0b0f14;color:#e2e8f0;
padding:60px;line-height:1.6">
<h2 style="color:{colour}">{title}</h2>{body}</body></html>""",
        status_code=200 if ok else 400,
    )


@router.get("/login")
def login(state: str = "sp", client: Optional[FyersClient] = Depends(get_client)):
    """Entry point for the browser: redirects to the Fyers auth screen.

    Requires FYERS_APP_ID and FYERS_SECRET_ID.
    """
    if not client:
        try:
            client = FyersClient()
        except FyersError as exc:
            return _page("Fyers not configured", f"<p><code>{exc}</code></p>", ok=False)

    if not client.app_id or not client.secret_id:
        return _page(
            "Fyers not configured",
            "<p>FYERS_APP_ID and FYERS_SECRET_ID must be set in the environment.</p>",
            ok=False,
        )
    return RedirectResponse(client.build_auth_url(state=state))


@router.get("/callback")
def callback(
    auth_code: Optional[str] = None,
    state: Optional[str] = None,
    client: Optional[FyersClient] = Depends(get_client),
):
    """Fyers redirects the user here with `?auth_code=...&state=...`.

    Exchanges the code for a 24-hour access token, writes it back into
    .env for other local tools to pick up, and redirects to the frontend
    with the token in the URL fragment so the SPA can store it.
    """
    if not auth_code:
        return _page("Login failed", "<p>No auth_code received from Fyers.</p>", ok=False)

    if not client:
        try:
            client = FyersClient()
        except FyersError as exc:
            return _page("Fyers not configured", f"<p><code>{exc}</code></p>", ok=False)

    try:
        token = client.exchange_code_for_token(auth_code)
    except FyersError as exc:
        return _page("Could not reach Fyers", f"<p><code>{exc}</code></p>", ok=False)

    # Local convenience only. Never in production: the container FS is
    # ephemeral and the file would be shared by every visitor.
    if not _is_production():
        set_env_value(ENV_PATH, "FYERS_ACCESS_TOKEN", token)
        if client.refresh_token:
            set_env_value(ENV_PATH, "FYERS_REFRESH_TOKEN", client.refresh_token)

    logger.info("Fyers token issued to caller (%d chars)", len(token))

    origin = _frontend_origin()
    if origin:
        # Fragment, not query: fragments are never sent to a server, never
        # appear in access logs, and are not forwarded in the Referer header.
        fragment = urllib.parse.urlencode({"fyers_token": token})
        return RedirectResponse(f"{origin}/portfolio#{fragment}")

    # No frontend configured (backend-only local dev): show the token so it can
    # be pasted into a .env or an API client.
    return _page(
        "Fyers connected",
        "<p>No FRONTEND_ORIGIN is configured, so here is the token directly:</p>"
        f"<p><code style='word-break:break-all'>{token}</code></p>"
        "<p>Verify with "
        "<a style='color:#22d3ee' href='/api/fyers/status'>/api/fyers/status</a>.</p>",
    )


@router.get("/status")
def status(client: Optional[FyersClient] = Depends(get_client)):
    """Whether the caller's token works, verified against the Fyers profile call."""
    if not client or not client.access_token:
        return {
            "connected": False,
            "reason": "No active broker session or access token supplied.",
            "login_url": "/api/fyers/login",
        }
    try:
        profile = client.profile()
    except FyersAuthError as exc:
        return {"connected": False, "reason": str(exc), "login_url": "/api/fyers/login"}
    except FyersError as exc:
        raise _raise_for(exc)

    data = profile.get("data", {})
    return {
        "connected": True,
        "name": data.get("name"),
        "fy_id": data.get("fy_id"),
        "email": data.get("email_id"),
    }


@router.get("/holdings", response_model=HoldingsResponse)
def holdings(client: Optional[FyersClient] = Depends(get_client)):
    """Delivery holdings, normalised and enriched from the NSE symbol master.

    Note that Fyers does not report a purchase date, so `buy_date` comes back
    null and holding-period return has to be supplied by the user.
    """
    if not client or not client.access_token:
        return HoldingsResponse(
            holdings=[],
            overall={"total_investment": 0.0, "total_current_value": 0.0, "total_pnl": 0.0, "pnl_percentage": 0.0},
            count=0,
        )
    try:
        return HoldingsResponse.from_fyers(client.holdings())
    except FyersError as exc:
        raise _raise_for(exc)


@router.get("/positions")
def positions(client: FyersClient = Depends(get_client)):
    """Intraday and F&O positions — separate from delivery holdings."""
    try:
        return client.positions()
    except FyersError as exc:
        raise _raise_for(exc)


@router.get("/funds")
def funds(client: FyersClient = Depends(get_client)):
    """Available margin and cash balance."""
    try:
        return client.funds()
    except FyersError as exc:
        raise _raise_for(exc)


@router.get("/quote")
def quote(
    symbols: str = Query("NSE:SBIN-EQ", description="Comma-separated, max 50"),
    client: FyersClient = Depends(get_client),
):
    """Live quotes, e.g. NSE:SBIN-EQ,NSE:NIFTY50-INDEX."""
    try:
        return client.quotes([s.strip() for s in symbols.split(",") if s.strip()])
    except FyersError as exc:
        raise _raise_for(exc)


@router.get("/history")
def history(
    symbol: str = Query("NSE:SBIN-EQ"),
    resolution: str = Query("1D", description='"1D" or minutes: 1,5,15,60...'),
    range_from: str = Query(..., description="YYYY-MM-DD"),
    range_to: str = Query(..., description="YYYY-MM-DD"),
    client: FyersClient = Depends(get_client),
):
    """Historical OHLCV candles."""
    try:
        return client.history(symbol, resolution, range_from, range_to)
    except FyersError as exc:
        raise _raise_for(exc)
