"""Alert rules: evaluation and delivery.

A rule is a standing question asked of a portfolio once a night — "is any
single holding above 25% of the book", "did anything death-cross", "has any
holding's promoter pledge jumped". Rules are pure functions of an already
computed analysis payload, which keeps evaluation free of network calls and
makes every rule unit-testable against a fixture.

Two behaviours worth knowing:

* **Cooldown, not deduplication.** A breached concentration limit stays
  breached for weeks. Firing nightly trains the user to ignore alerts, so each
  rule is silent for `cooldown_hours` after it fires. That is a property of
  the rule, not of the message text, so a *different* symbol breaching the same
  rule also waits — accepted deliberately, because the alternative (per-symbol
  state) buys precision nobody asked for at the cost of a second table.

* **Delivery failure is recorded, not raised.** The event row is written first
  and marked delivered afterwards. A Telegram outage must not lose the finding.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_HOURS = 20


@dataclass
class Finding:
    """One thing worth telling the user about."""

    title: str
    detail: str
    severity: str = "WARNING"
    symbol: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "detail": self.detail,
            "severity": self.severity,
            "symbol": self.symbol,
        }


# A rule takes (analysis payload, rule params) and returns zero or more findings.
RuleFn = Callable[[Dict[str, Any], Dict[str, Any]], List[Finding]]

RULES: Dict[str, RuleFn] = {}


def rule(kind: str) -> Callable[[RuleFn], RuleFn]:
    def register(fn: RuleFn) -> RuleFn:
        RULES[kind] = fn
        return fn

    return register


# ---- the rules -----------------------------------------------------------


@rule("danger_score_above")
def danger_score_above(analysis: Dict[str, Any], params: Dict[str, Any]) -> List[Finding]:
    threshold = float(params.get("threshold", 60.0))
    danger = analysis.get("danger") or {}
    score = danger.get("danger_score")
    if score is None or score < threshold:
        return []
    return [
        Finding(
            title=f"Portfolio danger score {score:.0f} (limit {threshold:.0f})",
            detail=(
                f"Danger level is '{danger.get('danger_level')}'. "
                f"{len(danger.get('flags') or [])} risk flags are active."
            ),
            severity="CRITICAL" if score >= 70 else "WARNING",
        )
    ]


@rule("single_holding_weight")
def single_holding_weight(analysis: Dict[str, Any], params: Dict[str, Any]) -> List[Finding]:
    threshold = float(params.get("threshold_pct", 20.0))
    holdings = (analysis.get("valuation") or {}).get("holdings") or []
    findings: List[Finding] = []
    for holding in holdings:
        weight = holding.get("weight_pct")
        if weight is not None and weight > threshold:
            findings.append(
                Finding(
                    title=f"{holding.get('key')} is {weight:.1f}% of the portfolio",
                    detail=(
                        f"Above your {threshold:.0f}% single-holding limit. "
                        "A single-name shock now moves the whole book."
                    ),
                    severity="CRITICAL" if weight > threshold * 1.25 else "WARNING",
                    symbol=holding.get("key"),
                )
            )
    return findings


@rule("drawdown_below")
def drawdown_below(analysis: Dict[str, Any], params: Dict[str, Any]) -> List[Finding]:
    """Any holding down more than N% from cost."""
    threshold = float(params.get("threshold_pct", 25.0))
    holdings = (analysis.get("valuation") or {}).get("holdings") or []
    return [
        Finding(
            title=f"{h.get('key')} is down {abs(h['pnl_pct']):.1f}% from cost",
            detail=(
                f"Unrealised loss of ₹{abs(h.get('pnl') or 0):,.0f}. "
                "Check whether the original thesis still holds."
            ),
            severity="WARNING",
            symbol=h.get("key"),
        )
        for h in holdings
        if h.get("pnl_pct") is not None and h["pnl_pct"] < -threshold
    ]


@rule("risk_flag_raised")
def risk_flag_raised(analysis: Dict[str, Any], params: Dict[str, Any]) -> List[Finding]:
    """Surface the danger engine's own flags at or above a severity."""
    minimum = str(params.get("min_severity", "CRITICAL")).upper()
    order = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
    floor = order.get(minimum, 2)
    return [
        Finding(
            title=flag.get("title", "Risk flag"),
            detail=flag.get("detail", ""),
            severity=flag.get("severity", "WARNING"),
        )
        for flag in (analysis.get("danger") or {}).get("flags") or []
        if order.get(str(flag.get("severity", "")).upper(), 1) >= floor
    ]


@rule("technical_breakdown")
def technical_breakdown(analysis: Dict[str, Any], params: Dict[str, Any]) -> List[Finding]:
    """Death cross or a close below the 200-day average on a holding.

    Reads the per-holding technicals the nightly job attaches to the analysis
    payload; absent them the rule stays quiet rather than guessing.
    """
    findings: List[Finding] = []
    for symbol, tech in (analysis.get("technicals") or {}).items():
        if not isinstance(tech, dict) or not tech.get("available"):
            continue
        if tech.get("death_cross"):
            findings.append(
                Finding(
                    title=f"{symbol}: death cross (50 SMA below 200 SMA)",
                    detail=(
                        f"Price {tech.get('current_price')} against 50 SMA "
                        f"{tech.get('sma50')} and 200 SMA {tech.get('sma200')}."
                    ),
                    severity="WARNING",
                    symbol=symbol,
                )
            )
        elif tech.get("above_sma200") is False and (tech.get("vol_surge") or 0) >= 1.5:
            findings.append(
                Finding(
                    title=f"{symbol}: broke below the 200 SMA on heavy volume",
                    detail=(
                        f"Volume {tech.get('vol_surge'):.1f}x the 20-day average "
                        "on a close below the long-term average."
                    ),
                    severity="WARNING",
                    symbol=symbol,
                )
            )
    return findings


@rule("promoter_pledge_above")
def promoter_pledge_above(analysis: Dict[str, Any], params: Dict[str, Any]) -> List[Finding]:
    threshold = float(params.get("threshold_pct", 20.0))
    findings: List[Finding] = []
    for symbol, fund in (analysis.get("fundamentals") or {}).items():
        if not isinstance(fund, dict):
            continue
        pledged = fund.get("pledged_pct")
        if pledged is not None and pledged > threshold:
            findings.append(
                Finding(
                    title=f"{symbol}: promoter pledging at {pledged:.1f}%",
                    detail=(
                        "Pledged promoter shares can be force-sold in a "
                        "drawdown, which is how a fall becomes a collapse."
                    ),
                    severity="CRITICAL",
                    symbol=symbol,
                )
            )
    return findings


# ---- evaluation ----------------------------------------------------------


def in_cooldown(last_fired_at: Optional[datetime], cooldown_hours: float) -> bool:
    if last_fired_at is None:
        return False
    if last_fired_at.tzinfo is None:
        # SQLite hands back naive datetimes even for timezone=True columns.
        last_fired_at = last_fired_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_fired_at < timedelta(hours=cooldown_hours)


def evaluate(kind: str, analysis: Dict[str, Any], params: Dict[str, Any]) -> List[Finding]:
    """Run one rule. An unknown kind is a config error, so it is logged loudly."""
    fn = RULES.get(kind)
    if fn is None:
        logger.error("Unknown alert rule kind: %s", kind)
        return []
    try:
        return fn(analysis, params or {})
    except Exception:
        # One malformed rule must not abort the nightly pass over every account.
        logger.exception("Alert rule %s raised", kind)
        return []


# ---- delivery ------------------------------------------------------------


def deliver(channel: str, target: Optional[str], findings: List[Finding]) -> None:
    """Send findings. Raises on failure so the caller can record the error."""
    if not findings:
        return
    if channel == "none":
        return
    if channel == "telegram":
        _deliver_telegram(target, findings)
    elif channel == "email":
        _deliver_email(target, findings)
    else:
        raise ValueError(f"Unsupported alert channel: {channel}")


def _format(findings: List[Finding]) -> str:
    icon = {"CRITICAL": "🔴", "WARNING": "🟠", "INFO": "⚪"}
    lines = ["stockportfolio.in — portfolio alerts", ""]
    for finding in findings:
        lines.append(f"{icon.get(finding.severity, '•')} {finding.title}")
        if finding.detail:
            lines.append(f"   {finding.detail}")
    lines.append("")
    lines.append("Diagnostics, not investment advice.")
    return "\n".join(lines)


def _deliver_telegram(target: Optional[str], findings: List[Finding]) -> None:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (target or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and a chat id are required for Telegram alerts.")

    from curl_cffi import requests

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": _format(findings), "disable_web_page_preview": True},
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Telegram rejected the message: HTTP {response.status_code}")


def _deliver_email(target: Optional[str], findings: List[Finding]) -> None:
    """SMTP, using whatever server is configured. No third-party mail SDK."""
    import smtplib
    from email.message import EmailMessage

    host = (os.getenv("SMTP_HOST") or "").strip()
    sender = (os.getenv("SMTP_FROM") or "").strip()
    if not host or not sender or not target:
        raise RuntimeError("SMTP_HOST, SMTP_FROM and a target address are required for email alerts.")

    message = EmailMessage()
    message["Subject"] = f"Portfolio alerts — {len(findings)} finding(s)"
    message["From"] = sender
    message["To"] = target
    message.set_content(_format(findings))

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.send_message(message)


def available_rules() -> List[Dict[str, Any]]:
    """Rule catalogue for the UI, with each rule's default parameters."""
    return [
        {"kind": "danger_score_above", "params": {"threshold": 60.0},
         "description": "Portfolio danger score crosses a limit."},
        {"kind": "single_holding_weight", "params": {"threshold_pct": 20.0},
         "description": "Any one holding exceeds a share of the portfolio."},
        {"kind": "drawdown_below", "params": {"threshold_pct": 25.0},
         "description": "Any holding falls more than N% below cost."},
        {"kind": "risk_flag_raised", "params": {"min_severity": "CRITICAL"},
         "description": "The danger engine raises a flag at or above a severity."},
        {"kind": "technical_breakdown", "params": {},
         "description": "Death cross, or a break below the 200 SMA on heavy volume."},
        {"kind": "promoter_pledge_above", "params": {"threshold_pct": 20.0},
         "description": "Promoter pledging on a holding exceeds a limit."},
    ]
