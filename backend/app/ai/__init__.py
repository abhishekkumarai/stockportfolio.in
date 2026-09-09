"""AI layer (Phase 11).

Two things, both strictly optional — without `ANTHROPIC_API_KEY` every feature
here reports `available: false` and the deterministic engines are unaffected:

* `narrative` — a monthly portfolio memo written over already-computed metrics,
  with every figure in the prose verified back against the data it was given.
* `sentiment` — an LLM classifier for Indian financial headlines, replacing
  VADER as the primary path and keeping it as the fallback.
"""

from app.ai.client import AIUnavailable, CLASSIFIER_MODEL, REPORT_MODEL, is_configured

__all__ = ["AIUnavailable", "CLASSIFIER_MODEL", "REPORT_MODEL", "is_configured"]
