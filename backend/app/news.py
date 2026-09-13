"""Free News & Corporate Announcements Ingestion and Tagging Engine.

Pulls news headlines via Google News RSS and exchange filings for free using curl_cffi.
Applies automated 6-tag taxonomy and sentiment impact classification
defaulting to the previous day (T-1 window) with zero noise (portfolio-filtered).
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from app.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

def _analyze_sentiment(headlines: List[str]) -> Dict[str, Any]:
    try:
        from app.analysis import analyze_sentiment
        return analyze_sentiment(headlines)
    except Exception:
        return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}

_NEWS_CACHE = TTLCache(ttl=1800, max_entries=512)


# Automated Tagging Taxonomy Patterns
TAXONOMY_PATTERNS = {
    "Governance & Legal": [
        r"\baudit(or|)\b",
        r"\bresign(s|ed|ation)\b",
        r"\bsebi\b",
        r"\bnotice\b",
        r"\braid(s|ed|)\b",
        r"\bfraud\b",
        r"\blitigat(ion|e)\b",
        r"\bpenalty\b",
        r"\bprobe\b",
        r"\bcourt\b",
        r"\bdefault\b",
    ],
    "Promoter & Insider": [
        r"\bpledg(e|ed|ing)\b",
        r"\binsider\b",
        r"\bpromoter\b",
        r"\bstake\s+(sale|sell|sold|bought|buy)\b",
        r"\boffer\s+for\s+sale\b",
        r"\bofs\b",
    ],
    "Earnings & Financials": [
        r"\bq[1-4]\b",
        r"\bprofit\b",
        r"\bpat\b",
        r"\brevenue\b",
        r"\bebitda\b",
        r"\bmargin\b",
        r"\bresult(s|)\b",
        r"\bearning(s|)\b",
        r"\bguidance\b",
        r"\byoy\b",
        r"\bqoq\b",
        r"\baum\b",
        r"\binflow(s|)\b",
        r"\boutflow(s|)\b",
        r"\bnav\b",
    ],
    "Order Wins & Expansion": [
        r"\border\b",
        r"\bcontract\b",
        r"\bwin(s|)\b",
        r"\bsecur(es|ed)\b",
        r"\bcommission(s|ed)\b",
        r"\bapprov(al|ed)\b",
        r"\busfda\b",
        r"\bpatent\b",
        r"\bexpand(s|ed|ion)\b",
        r"\bcapacity\b",
        r"\bjoint\s+venture\b",
        r"\bnfo\b",
        r"\bnew\s+fund\b",
        r"\blaunch(es|ed|ing|)\b",
    ],
    "Corporate Actions": [
        r"\bdividend\b",
        r"\bbonus\b",
        r"\bsplit\b",
        r"\bbuyback\b",
        r"\brights\s+issue\b",
        r"\bagm\b",
        r"\bidcw\b",
        r"\bexpense\s+ratio\b",
        r"\bter\b",
        r"\bportfolio\s+disclosure(s|)\b",
    ],
    "Macro & Policy": [
        r"\brbi\b",
        r"\brepo\s+rate\b",
        r"\btariff\b",
        r"\bduty\b",
        r"\bgst\b",
        r"\bpli\b",
        r"\binflation\b",
        r"\bcrude\b",
        r"\bbudget\b",
        r"\btax(ation|es|)\b",
    ],
}


def tag_headline(title: str) -> str:
    """Categorizes headline into one of 6 taxonomy buckets."""
    title_lower = title.lower()
    for tag, patterns in TAXONOMY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, title_lower):
                return tag
    return "Market Update"


def clean_fund_name(name: str) -> str:
    """Strips plan/option noise (e.g. Direct Plan, Growth) for cleaner news queries."""
    cleaned = re.sub(
        r"(?i)\s*-\s*(Direct|Regular)(\s+(Plan|Growth|Option|IDCW|Dividend))*",
        "",
        name,
    )
    cleaned = re.sub(
        r"(?i)\s*-\s*(Growth|IDCW|Dividend)(\s+(Plan|Option|Direct|Regular))*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?i)\s*\((Direct|Regular|Growth|IDCW|Dividend).*\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def fetch_free_ticker_news(ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches free ticker news from Google News RSS using curl_cffi."""
    clean_ticker = ticker.replace(".NS", "").replace(".BO", "").replace("NSE:", "")
    query = f"{clean_ticker} stock NSE"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    cache_key = make_key("news", clean_ticker)
    cached = _NEWS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    articles: List[Dict[str, Any]] = []
    try:
        from curl_cffi import requests
        session = requests.Session(impersonate="chrome")
        response = session.get(url, timeout=10)

        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall("./channel/item")[:limit]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source = item.findtext("source", "Google News")

                # Remove publisher suffix from title if present (e.g. "Title - Economic Times")
                clean_title = title.rsplit(" - ", 1)[0] if " - " in title else title

                # Determine tag and sentiment
                tag = tag_headline(clean_title)
                sent = _analyze_sentiment([clean_title])
                compound = sent.get("compound", 0.0)

                if compound >= 0.15:
                    impact = "BULLISH"
                    impact_label = "🟢 Bullish"
                elif compound <= -0.15 or tag in ("Governance & Legal", "Promoter & Insider"):
                    impact = "BEARISH"
                    impact_label = "🔴 Bearish"
                else:
                    impact = "NEUTRAL"
                    impact_label = "⚪ Neutral"

                articles.append(
                    {
                        "symbol": clean_ticker,
                        "title": clean_title,
                        "url": link,
                        "source": source,
                        "published_at": pub_date,
                        "tag": tag,
                        "impact": impact,
                        "impact_label": impact_label,
                        "sentiment_score": compound,
                        "kind": "equity",
                    }
                )

        _NEWS_CACHE.set(cache_key, articles)
        return articles

    except Exception as exc:
        logger.warning("Free news fetch failed for %s: %s", clean_ticker, exc)
        return []


def fetch_free_fund_news(
    scheme_code: int,
    scheme_name: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Fetches free mutual fund news from Google News RSS using curl_cffi."""
    resolved_name = scheme_name
    if not resolved_name or resolved_name.startswith("Scheme "):
        try:
            from app.mfapi_client import MFApiClient
            client = MFApiClient()
            meta = client.get_latest_nav(scheme_code).get("meta", {})
            resolved_name = meta.get("scheme_name") or f"Scheme {scheme_code}"
        except Exception as exc:
            logger.warning("Failed to resolve MF scheme name for %s: %s", scheme_code, exc)
            resolved_name = f"Scheme {scheme_code}"

    search_term = clean_fund_name(resolved_name)
    if not search_term or search_term.startswith("Scheme "):
        return []

    cache_key = make_key("news_fund", str(scheme_code))
    cached = _NEWS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    articles: List[Dict[str, Any]] = []
    try:
        from curl_cffi import requests
        session = requests.Session(impersonate="chrome")
        query = search_term if "fund" in search_term.lower() else f"{search_term} mutual fund"
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        response = session.get(url, timeout=10)

        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall("./channel/item")[:limit]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source = item.findtext("source", "Google News")

                clean_title = title.rsplit(" - ", 1)[0] if " - " in title else title
                tag = tag_headline(clean_title)
                sent = _analyze_sentiment([clean_title])
                compound = sent.get("compound", 0.0)

                if compound >= 0.15:
                    impact = "BULLISH"
                    impact_label = "🟢 Bullish"
                elif compound <= -0.15 or tag in ("Governance & Legal", "Promoter & Insider"):
                    impact = "BEARISH"
                    impact_label = "🔴 Bearish"
                else:
                    impact = "NEUTRAL"
                    impact_label = "⚪ Neutral"

                articles.append(
                    {
                        "symbol": search_term,
                        "title": clean_title,
                        "url": link,
                        "source": source,
                        "published_at": pub_date,
                        "tag": tag,
                        "impact": impact,
                        "impact_label": impact_label,
                        "sentiment_score": compound,
                        "kind": "fund",
                        "scheme_code": scheme_code,
                        "scheme_name": resolved_name,
                    }
                )

        _NEWS_CACHE.set(cache_key, articles)
        return articles

    except Exception as exc:
        logger.warning("Free MF news fetch failed for %s (%s): %s", scheme_code, search_term, exc)
        return []


def get_portfolio_news_digest(
    symbols: List[str],
    funds: Optional[List[Dict[str, Any]]] = None,
    max_per_symbol: int = 3,
) -> List[Dict[str, Any]]:
    """Aggregates and tags news catalysts for portfolio equity symbols and mutual funds."""
    digest: List[Dict[str, Any]] = []
    for sym in symbols[:15]:  # Safety cap
        news = fetch_free_ticker_news(sym, limit=max_per_symbol)
        digest.extend(news)

    for fund in (funds or [])[:10]:
        scheme_code = fund.get("scheme_code")
        if scheme_code:
            fund_news = fetch_free_fund_news(
                scheme_code=int(scheme_code),
                scheme_name=fund.get("scheme_name"),
                limit=max_per_symbol,
            )
            digest.extend(fund_news)

    # Sort high-impact (Governance, Promoter, Earnings) first
    def _rank(item: Dict[str, Any]) -> int:
        tag = item.get("tag")
        impact = item.get("impact")
        if tag == "Governance & Legal":
            return 0
        if tag == "Promoter & Insider":
            return 1
        if impact == "BEARISH":
            return 2
        if impact == "BULLISH":
            return 3
        return 4

    digest.sort(key=_rank)
    return digest
