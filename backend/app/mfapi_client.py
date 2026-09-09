"""Client wrapper around https://api.mfapi.in and AMFI India.

The upstream API (api.mfapi.in) is free, unauthenticated and occasionally returns
502 Bad Gateway or timeouts. When mfapi.in fails, this client automatically and
transparently falls back to the official AMFI India daily feed
(https://www.amfiindia.com/spages/NAVAll.txt), ensuring zero downtime for scheme
lookups, latest NAV pricing, and portfolio valuations.
"""

import logging
import threading
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from curl_cffi import requests

from app.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

BASE_URL = "https://api.mfapi.in"
AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

DateLike = Union[str, date, datetime, None]


class MFApiError(Exception):
    """Raised when the upstream API is unreachable or returns something unusable."""


class SchemeNotFoundError(MFApiError):
    """Raised when a scheme code has no data upstream."""


def normalize_date(value: DateLike) -> Optional[str]:
    """Coerce a date to the YYYY-MM-DD form the upstream API requires."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date {value!r}; use YYYY-MM-DD.")


def parse_nav_date(value: str) -> date:
    """Parse the DD-MM-YYYY dates used inside NAV payloads."""
    # AMFI uses formats like "28-Aug-2026" or "28-08-2026"
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return date.today()


class MFApiClient:
    """Resilient, cached HTTP client for mfapi.in with automatic AMFI India fallback."""

    def __init__(
        self,
        timeout: int = 12,
        cache_ttl: float = 900.0,
        retries: int = 2,
        amfi_ttl: float = 43200.0,  # 12 hours
    ):
        self._timeout = timeout
        self._retries = retries
        self._cache = TTLCache(cache_ttl)
        self._amfi_ttl = amfi_ttl
        self._amfi_by_code: Dict[int, Dict[str, Any]] = {}
        self._amfi_by_isin: Dict[str, Dict[str, Any]] = {}
        self._amfi_expires_at = 0.0
        self._amfi_lock = threading.Lock()

    # ---- AMFI Official Fallback Engine -----------------------------------

    def _ensure_amfi_master(self) -> None:
        """Fetches and parses the official AMFI NAV master text file."""
        with self._amfi_lock:
            if self._amfi_by_code and self._amfi_expires_at > time.monotonic():
                return

            try:
                logger.info("Fetching official AMFI NAV master from %s", AMFI_URL)
                resp = requests.get(AMFI_URL, timeout=20)
                if resp.status_code != 200:
                    logger.warning("AMFI feed returned status %s", resp.status_code)
                    return

                by_code: Dict[int, Dict[str, Any]] = {}
                by_isin: Dict[str, Dict[str, Any]] = {}
                current_category = ""
                current_fund_house = ""

                for line in resp.text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("Open Ended") or line.startswith("Close Ended"):
                        current_category = line
                        continue
                    if ";" not in line:
                        current_fund_house = line
                        continue

                    parts = line.split(";")
                    if len(parts) >= 6 and parts[0].isdigit():
                        try:
                            code = int(parts[0])
                            isin1 = parts[1].strip()
                            isin2 = parts[2].strip() if len(parts) > 2 else ""
                            name = parts[3].strip() if len(parts) > 3 else ""
                            nav_val = parts[-2].strip() if len(parts) >= 8 else parts[4].strip()
                            date_val = parts[-1].strip()

                            # If 8 columns: Code;ISIN1;ISIN2;Name;Plan;Option;NAV;Date
                            if len(parts) == 8:
                                plan = parts[4].strip()
                                opt = parts[5].strip()
                                full_name = f"{name} - {plan} - {opt}" if plan else name
                                nav_str = parts[6].strip()
                            else:
                                full_name = name
                                nav_str = nav_val

                            parsed_nav = float(nav_str) if nav_str.replace(".", "", 1).isdigit() else None

                            entry = {
                                "scheme_code": code,
                                "scheme_name": full_name,
                                "isin_growth": isin1 if isin1 != "-" else None,
                                "isin_div": isin2 if isin2 != "-" else None,
                                "scheme_category": current_category,
                                "fund_house": current_fund_house,
                                "nav": parsed_nav,
                                "date": date_val,
                            }

                            by_code[code] = entry
                            if isin1 and isin1 != "-":
                                by_isin[isin1.upper()] = entry
                            if isin2 and isin2 != "-":
                                by_isin[isin2.upper()] = entry
                        except Exception:
                            continue

                self._amfi_by_code = by_code
                self._amfi_by_isin = by_isin
                self._amfi_expires_at = time.monotonic() + self._amfi_ttl
                logger.info("Successfully indexed %d schemes from AMFI master", len(by_code))
            except Exception as exc:
                logger.warning("Failed to fetch AMFI master: %s", exc)

    def _get_from_amfi(self, scheme_code: int) -> Dict[str, Any]:
        """Returns standard metadata and latest NAV point reconstructed from AMFI."""
        self._ensure_amfi_master()
        entry = self._amfi_by_code.get(scheme_code)
        if not entry:
            raise SchemeNotFoundError(f"Scheme {scheme_code} not found in AMFI master")

        meta = {
            "fund_house": entry.get("fund_house", "Mutual Fund"),
            "scheme_type": "Open Ended",
            "scheme_category": entry.get("scheme_category", "Equity Scheme"),
            "scheme_code": scheme_code,
            "scheme_name": entry.get("scheme_name", f"Scheme {scheme_code}"),
            "isin_growth": entry.get("isin_growth"),
            "isin_div_reinvestment": entry.get("isin_div"),
        }
        data = []
        if entry.get("nav") is not None:
            # Convert date to DD-MM-YYYY format
            d_obj = parse_nav_date(entry.get("date", ""))
            data.append({
                "date": d_obj.strftime("%d-%m-%Y"),
                "nav": str(entry["nav"]),
            })

        return {"meta": meta, "data": data}

    # ---- transport -------------------------------------------------------

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        cache_key = make_key(path, params)

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{BASE_URL}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(self._retries + 1):
            try:
                response = requests.get(
                    url, params=params, timeout=timeout or self._timeout
                )
                if response.status_code == 404:
                    raise SchemeNotFoundError(f"Not found upstream: {path}")
                if response.status_code >= 400:
                    raise MFApiError(
                        f"mfapi.in returned {response.status_code} for {path}"
                    )
                payload = response.json()
                self._cache.set(cache_key, payload)
                return payload
            except SchemeNotFoundError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < self._retries:
                    time.sleep(0.3 * (attempt + 1))
                    continue

        logger.warning("mfapi.in request failed for %s: %s", path, last_error)
        raise MFApiError(f"Could not reach mfapi.in for {path}: {last_error}")

    def clear_cache(self) -> None:
        self._cache.clear()

    # ---- endpoints -------------------------------------------------------

    def search(self, query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Full-text search over scheme names. Falls back to AMFI master if mfapi fails."""
        query = (query or "").strip()
        if not query:
            return []

        try:
            results = self._get("/mf/search", {"q": query})
            if isinstance(results, list) and results:
                return results[:limit] if limit else results
        except Exception as exc:
            logger.info("mfapi.in search failed (%s), falling back to AMFI master", exc)

        # Fallback to AMFI master search
        self._ensure_amfi_master()
        q_lower = query.lower()
        amfi_results = [
            {"schemeCode": code, "schemeName": item["scheme_name"]}
            for code, item in self._amfi_by_code.items()
            if q_lower in item["scheme_name"].lower()
        ]
        return amfi_results[:limit] if limit else amfi_results

    def list_schemes(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Page through the full scheme list (~10k schemes)."""
        try:
            return self._get("/mf", {"limit": limit, "offset": offset}) or []
        except Exception:
            self._ensure_amfi_master()
            items = list(self._amfi_by_code.values())[offset : offset + limit]
            return [
                {
                    "schemeCode": item["scheme_code"],
                    "schemeName": item["scheme_name"],
                    "isinGrowth": item.get("isin_growth"),
                    "isinDivReinvestment": item.get("isin_div"),
                }
                for item in items
            ]

    def get_scheme(
        self,
        scheme_code: int,
        start_date: DateLike = None,
        end_date: DateLike = None,
    ) -> Dict[str, Any]:
        """Full NAV history plus scheme metadata. Falls back to AMFI if mfapi is 502."""
        try:
            payload = self._get(
                f"/mf/{scheme_code}",
                {"startDate": normalize_date(start_date), "endDate": normalize_date(end_date)},
            )
            return self._validate_scheme_payload(payload, scheme_code)
        except SchemeNotFoundError:
            raise
        except Exception as exc:
            logger.warning("mfapi.in get_scheme %d failed (%s), falling back to AMFI", scheme_code, exc)
            return self._get_from_amfi(scheme_code)

    def get_latest_nav(self, scheme_code: int) -> Dict[str, Any]:
        """Metadata plus single most recent NAV point. Falls back to AMFI if mfapi is 502."""
        try:
            payload = self._get(f"/mf/{scheme_code}/latest")
            return self._validate_scheme_payload(payload, scheme_code)
        except SchemeNotFoundError:
            raise
        except Exception as exc:
            logger.warning("mfapi.in get_latest_nav %d failed (%s), falling back to AMFI", scheme_code, exc)
            return self._get_from_amfi(scheme_code)

    def latest_nav_all(self) -> List[Dict[str, Any]]:
        """Latest NAV for every scheme in one call."""
        try:
            return self._get("/mf/latest") or []
        except Exception:
            self._ensure_amfi_master()
            return [
                {"schemeCode": code, "nav": item.get("nav"), "date": item.get("date")}
                for code, item in self._amfi_by_code.items()
            ]

    def resolve_isin(self, isin: str) -> Optional[Dict[str, Any]]:
        """Find a scheme by ISIN."""
        isin = (isin or "").strip().upper()
        if not isin:
            return None

        # Check AMFI master first (instant & reliable)
        self._ensure_amfi_master()
        entry = self._amfi_by_isin.get(isin)
        if entry:
            return {
                "schemeCode": entry["scheme_code"],
                "schemeName": entry["scheme_name"],
                "isinGrowth": entry.get("isin_growth"),
                "isinDivReinvestment": entry.get("isin_div"),
            }

        return None

    def _validate_scheme_payload(
        self, payload: Any, scheme_code: int
    ) -> Dict[str, Any]:
        """Turn the API's empty-but-successful response for bad codes into an error."""
        if not isinstance(payload, dict):
            raise MFApiError(f"Unexpected response shape for scheme {scheme_code}")

        meta = payload.get("meta") or {}
        data = payload.get("data") or []

        if not data and not meta.get("scheme_name"):
            raise SchemeNotFoundError(f"No data for scheme code {scheme_code}")

        return {"meta": meta, "data": data}


# Shared process-wide singleton
client = MFApiClient()
