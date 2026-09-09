"""Shared Anthropic client plumbing for the AI layer.

Two things live here so neither `narrative.py` nor `sentiment.py` reinvents
them: constructing the client, and the rule that the whole AI layer is
*optional*. No `ANTHROPIC_API_KEY`, or no `anthropic` package installed, means
every AI feature reports `available: false` with a reason and the deterministic
path continues untouched. An LLM narrator is a presentation layer over numbers
this system already computed; it is never load-bearing.

Model choice follows the PRD: `claude-opus-5` for the monthly report, where the
output is read carefully and quality matters, and `claude-haiku-4-5` for
per-headline classification, where volume is high and each judgement is small.
"""

import logging
import os
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)

# The report model. Read once a month by a person making decisions.
REPORT_MODEL = "claude-opus-5"

# The classification model. Called once per headline, so the per-call price
# dominates and the task is simple enough not to need more.
CLASSIFIER_MODEL = "claude-haiku-4-5"

DEFAULT_TIMEOUT = 120.0


class AIUnavailable(RuntimeError):
    """Raised when the AI layer cannot run. Always caught and reported, never surfaced raw."""


def is_configured() -> bool:
    """Whether an API key is present. Cheap; safe to call per request."""
    return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())


@lru_cache(maxsize=1)
def get_client() -> Any:
    """The shared Anthropic client, built on first use.

    Cached because constructing one per request throws away the underlying
    connection pool, which on a cold Render instance is the slowest part of the
    call.
    """
    if not is_configured():
        raise AIUnavailable(
            "ANTHROPIC_API_KEY is not set. The AI narrative and LLM sentiment "
            "classifier are disabled; every deterministic score and metric is "
            "unaffected."
        )
    try:
        import anthropic
    except ImportError as exc:
        raise AIUnavailable(
            "The 'anthropic' package is not installed. Add it to "
            "pyproject.toml to enable the AI layer."
        ) from exc

    return anthropic.Anthropic(timeout=DEFAULT_TIMEOUT)


def text_of(response: Any) -> str:
    """Concatenate the text blocks of a response.

    Iterating and checking `.type` rather than reaching for `content[0].text`:
    with thinking enabled the first block is a thinking block, and indexing
    blindly picks up an empty string or raises.
    """
    return "".join(block.text for block in response.content if block.type == "text").strip()


def refused(response: Any) -> Optional[str]:
    """The refusal explanation if the model declined, else None.

    Checked before reading content on every call. A refusal returns HTTP 200
    with empty content, so code that goes straight to the text sees a
    successful call that produced nothing.
    """
    if getattr(response, "stop_reason", None) != "refusal":
        return None
    details = getattr(response, "stop_details", None)
    category = getattr(details, "category", None) if details else None
    explanation = getattr(details, "explanation", None) if details else None
    return explanation or f"Model declined the request ({category or 'unspecified'})."
