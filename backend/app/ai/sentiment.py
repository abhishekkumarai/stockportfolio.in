"""Headline sentiment for Indian financial news.

VADER, which `analysis.analyze_sentiment` currently uses, is a lexicon tuned on
English social media. On an Indian markets headline it is close to useless:

    "PAT up 12% YoY, margin guidance trimmed"      -> 0.0 (neutral)
    "Auditor resigns citing lack of information"   -> 0.0 (neutral)
    "Promoter pledges additional 8% stake"         -> 0.0 (neutral)

Every one of those carries a clear directional read for an equity holder, and
the middle one is among the strongest sell signals in the language. VADER
scores them all as neutral because none of its lexicon words appear.

An LLM classifier reads them correctly, so this module replaces VADER as the
primary path — and keeps it as the fallback, because the AI layer is optional
and a portfolio must still render without an API key.

Batching matters: headlines are classified a screenful at a time in one
request rather than one call per headline, which for a 30-headline digest is
one round trip instead of thirty.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from app.ai.client import AIUnavailable, CLASSIFIER_MODEL, get_client, is_configured, refused, text_of
from app.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

# Headlines do not change their meaning, so a classification is cacheable
# indefinitely in practice. Six hours keeps the cache bounded across restarts
# of a long-lived process.
_SENTIMENT_CACHE = TTLCache(ttl=21600, max_entries=4096)

# Beyond this the response risks the token ceiling and the model starts
# skipping entries rather than truncating visibly.
MAX_BATCH = 25

IMPACT_VALUES = ("BULLISH", "BEARISH", "NEUTRAL")

CLASSIFIER_SYSTEM = """You classify Indian stock market news headlines for an \
equity portfolio tool.

For each headline, judge the likely direction of impact on the shareholder of \
the company named, over the next few weeks.

Rules that matter for this domain:
- Governance events are the strongest negatives regardless of tone: auditor \
resignation, SEBI notice or show-cause, tax raid, promoter pledge increase, \
CFO/CEO abrupt exit, qualified audit opinion, related-party concerns.
- Results are directional on the substance, not the adjectives. "Profit up \
40% on a low base with margin contraction" is not straightforwardly bullish.
- Order wins, capacity expansion, regulatory approvals (USFDA, CDSCO), and \
credit rating upgrades are positive catalysts.
- Dividends, splits, bonus issues and record dates are usually neutral \
information, not a directional signal.
- Broker target-price changes are weak signals; weight them low.
- A headline that names no company outcome (market wraps, index levels, \
"top gainers today") is NEUTRAL with low confidence.

Score from -1.0 (strongly negative for the shareholder) to +1.0 (strongly \
positive). Confidence is how sure you are the headline supports any \
directional read at all, not how extreme the score is."""

BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "impact": {"type": "string", "enum": list(IMPACT_VALUES)},
                    "score": {"type": "number"},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                },
                "required": ["index", "impact", "score", "confidence", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _vader_fallback(headline: str) -> Dict[str, Any]:
    """VADER, kept only as the no-API-key path. Honest about its limits."""
    try:
        from app.analysis import sia

        scores = sia.polarity_scores(headline)
        compound = float(scores["compound"])
    except Exception:
        return {
            "impact": "NEUTRAL",
            "score": 0.0,
            "confidence": 0.0,
            "rationale": "No sentiment engine available.",
            "source": "none",
        }

    impact = "BULLISH" if compound > 0.15 else "BEARISH" if compound < -0.15 else "NEUTRAL"
    return {
        "impact": impact,
        "score": round(compound, 3),
        # Capped at 0.4 deliberately: VADER's confidence on a financial
        # headline should never be presented as comparable to the classifier's.
        "confidence": round(min(0.4, abs(compound)), 3),
        "rationale": "Lexicon sentiment (VADER), which is unreliable on financial headlines.",
        "source": "vader",
    }


def classify_batch(
    headlines: Sequence[str], use_llm: bool = True
) -> List[Dict[str, Any]]:
    """Classify headlines, cache-first, LLM where available, VADER otherwise.

    Always returns one result per input headline in the same order. A partial
    LLM response — the model skipping an entry — is filled from VADER rather
    than shifting every subsequent result by one, which is the failure mode
    that makes a batched classifier quietly wrong.
    """
    if not headlines:
        return []

    results: List[Optional[Dict[str, Any]]] = [None] * len(headlines)
    pending: List[int] = []

    for index, headline in enumerate(headlines):
        cached = _SENTIMENT_CACHE.get(make_key("sentiment", headline))
        if cached is not None:
            results[index] = cached
        else:
            pending.append(index)

    if pending and use_llm and is_configured():
        for start in range(0, len(pending), MAX_BATCH):
            chunk = pending[start : start + MAX_BATCH]
            try:
                classified = _classify_with_llm([headlines[i] for i in chunk])
            except AIUnavailable as exc:
                logger.info("LLM sentiment unavailable, using VADER: %s", exc)
                break
            except Exception:
                logger.exception("LLM sentiment classification failed; using VADER")
                break

            for offset, payload in classified.items():
                if 0 <= offset < len(chunk):
                    index = chunk[offset]
                    results[index] = payload
                    _SENTIMENT_CACHE.set(make_key("sentiment", headlines[index]), payload)

    for index, headline in enumerate(headlines):
        if results[index] is None:
            results[index] = _vader_fallback(headline)

    return [result for result in results if result is not None]


def _classify_with_llm(headlines: Sequence[str]) -> Dict[int, Dict[str, Any]]:
    """One structured-output call over a batch. Returns {batch_index: result}."""
    client = get_client()
    numbered = "\n".join(f"{i}. {headline}" for i, headline in enumerate(headlines))

    response = client.messages.create(
        model=CLASSIFIER_MODEL,
        max_tokens=4000,
        system=CLASSIFIER_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    "Classify each headline. Return one result per headline, "
                    "using the same index shown.\n\n" + numbered
                ),
            }
        ],
        # A JSON schema rather than "reply with JSON" in the prompt: the
        # response is guaranteed parseable, so there is no repair path to
        # write and no silent drift when the model decides to add a preamble.
        output_config={"format": {"type": "json_schema", "schema": BATCH_SCHEMA}},
    )

    declined = refused(response)
    if declined:
        raise AIUnavailable(f"Classifier declined: {declined}")

    payload = json.loads(text_of(response))
    out: Dict[int, Dict[str, Any]] = {}
    for entry in payload.get("results", []):
        index = entry.get("index")
        if not isinstance(index, int):
            continue
        impact = str(entry.get("impact", "NEUTRAL")).upper()
        out[index] = {
            "impact": impact if impact in IMPACT_VALUES else "NEUTRAL",
            "score": max(-1.0, min(1.0, float(entry.get("score", 0.0)))),
            "confidence": max(0.0, min(1.0, float(entry.get("confidence", 0.0)))),
            "rationale": str(entry.get("rationale", ""))[:400],
            "source": "llm",
        }
    return out


def classify(headline: str, use_llm: bool = True) -> Dict[str, Any]:
    """Classify one headline. Prefer `classify_batch` for more than a couple."""
    return classify_batch([headline], use_llm)[0]


def aggregate(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll a set of classifications into one confidence-weighted read.

    Weighting by confidence rather than averaging raw scores stops a pile of
    "top gainers today" filler — correctly classified as neutral with low
    confidence — from diluting one genuine governance red flag into nothing.
    """
    if not results:
        return {"available": False, "reason": "No headlines to aggregate."}

    total_weight = sum(r["confidence"] for r in results)
    weighted = (
        sum(r["score"] * r["confidence"] for r in results) / total_weight
        if total_weight > 0
        else 0.0
    )
    counts = {value: sum(1 for r in results if r["impact"] == value) for value in IMPACT_VALUES}
    llm_share = sum(1 for r in results if r.get("source") == "llm") / len(results)

    return {
        "available": True,
        "headlines": len(results),
        "weighted_score": round(weighted, 3),
        "impact": (
            "BULLISH" if weighted > 0.15 else "BEARISH" if weighted < -0.15 else "NEUTRAL"
        ),
        "counts": counts,
        "average_confidence": round(total_weight / len(results), 3),
        "llm_share": round(llm_share, 2),
        "engine": (
            "llm" if llm_share > 0.8 else "mixed" if llm_share > 0 else "vader"
        ),
        "caveat": (
            None if llm_share > 0.8 else
            "Some or all headlines fell back to VADER lexicon scoring, which is "
            "unreliable on financial headlines. Set ANTHROPIC_API_KEY for the "
            "LLM classifier."
        ),
    }
