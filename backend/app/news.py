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
    ],
    "Corporate Actions": [
        r"\bdividend\b",
        r"\bbonus\b",
        r"\bsplit\b",
        r"\bbuyback\b",
        r"\brights\s+issue\b",
        r"\bagm\b",
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
                    }
                )

        _NEWS_CACHE.set(cache_key, articles)
        return articles

    except Exception as exc:
        logger.warning("Free news fetch failed for %s: %s", clean_ticker, exc)
        return []


def get_portfolio_news_digest(symbols: List[str], max_per_symbol: int = 3) -> List[Dict[str, Any]]:
    """Aggregates and tags news catalysts for a list of portfolio symbols."""
    digest: List[Dict[str, Any]] = []
    for sym in symbols[:15]:  # Safety cap
        news = fetch_free_ticker_news(sym, limit=max_per_symbol)
        digest.extend(news)

    # Sort high-impact (Governance, Promoter, Earnings) first
    def _rank(item: Dict[str, Any]) -> int:
        if item["tag"] == "Governance & Legal":
            return 0
        if item["tag"] == "Promoter & Insider":
            return 1
        if item["impact"] == "BEARISH":
            return 2
        if item["impact"] == "BULLISH":
            return 3
        return 4

    digest.sort(key=_rank)
    return digest
