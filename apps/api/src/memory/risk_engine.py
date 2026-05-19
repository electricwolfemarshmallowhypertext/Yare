from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional, Iterable, Callable
from datetime import datetime, timedelta, timezone
import statistics
import re
import math
import structlog

logger = structlog.get_logger("memory.risk_engine")

# Detector registry

DetectorFn = Callable[[List[Dict[str, Any]], Dict[str, Any]], Optional[Dict[str, Any]]]
_DETECTORS: Dict[str, DetectorFn] = {}


def register_detector(name: str):
    def deco(fn: DetectorFn):
        _DETECTORS[name] = fn
        return fn
    return deco


NEGATIVE_HINTS = (
    "delay", "blocker", "blocked", "stuck", "error", "fail", "failed",
    "risk", "late", "overdue", "problem", "issue", "bug", "crash",
    "urgent", "panic", "on fire"
)
POSITIVE_HINTS = ("progress", "done", "success", "fixed", "shipped", "resolved", "unblocked")

PREFERS_RE = re.compile(r"\b(prefer[s]?|like[s]?|favor[s]?)\s+(?P<thing>[a-z0-9_\- ]{2,})", re.I)
DISLIKES_RE = re.compile(r"\b(dislike[s]?|avoid[s]?|hate[s]?|not prefer[s]?|do not prefer)\s+(?P<thing>[a-z0-9_\- ]{2,})", re.I)


class RiskEngine:
    """
    Extensible risk engine aggregating pluggable detectors.
    - Each detector returns a risk dict or None.
    - Aggregator assigns severity and returns deduplicated list.
    """

    def __init__(self, store, weights: Optional[Dict[str, float]] = None) -> None:
        self.store = store
        self.weights = weights or {}

    def compute_risks(self, limit: int = 400) -> List[Dict[str, Any]]:
        mems = self.store.query(limit=limit)
        if not mems:
            return []
        buckets: Dict[Tuple[Optional[str], Optional[str], Optional[str], Optional[str]], List[Dict[str, Any]]] = {}
        for m in mems:
            key = (m.get("org_id"), m.get("user_id"), m.get("persona_id"), m.get("project_id"))
            buckets.setdefault(key, []).append(m)

        risks: List[Dict[str, Any]] = []
        for scope, items in buckets.items():
            items_sorted = sorted(items, key=lambda x: str(x.get("created_at", "")), reverse=True)
            scope_info = {"org_id": scope[0], "user_id": scope[1], "persona_id": scope[2], "project_id": scope[3]}
            # run detectors
            for name, fn in _DETECTORS.items():
                try:
                    r = fn(items_sorted, scope_info)
                    if r:
                        r["detector"] = name
                        risks.append(r)
                except Exception as e:
                    logger.warning("risk_detector_failed", detector=name, error=str(e))
        # de-dup by (type, scope)
        dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for r in risks:
            key = (r.get("type","unknown"), json_scope(r.get("scope") or {}))
            if key not in dedup:
                dedup[key] = r
            else:
                # keep higher severity
                if sev_rank(r.get("severity")) > sev_rank(dedup[key].get("severity")):
                    dedup[key] = r
        return sorted(dedup.values(), key=lambda x: sev_rank(x.get("severity")), reverse=True)


def sev_rank(sev: Optional[str]) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get((sev or "low").lower(), 0)


def json_scope(scope: Dict[str, Any]) -> str:
    return "|".join(str(scope.get(k,"")) for k in ("org_id","user_id","persona_id","project_id"))


def _parse_dt(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if isinstance(ts, datetime):
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        s = str(ts)
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


# Built-in detectors

@register_detector("inactivity")
def det_inactivity(items: List[Dict[str, Any]], scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not items:
        return None
    latest = _parse_dt(items[0].get("created_at"))
    if not latest:
        return None
    gap = datetime.now(timezone.utc) - latest
    if gap > timedelta(days=14):
        sev = "high"
    elif gap > timedelta(days=7):
        sev = "medium"
    else:
        return None
    return {"type": "inactivity", "severity": sev, "message": f"No activity for {gap.days} days", "scope": scope, "details": {"last_seen": latest.isoformat()}}

@register_detector("deadline")
def det_deadline(items: List[Dict[str, Any]], scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    for m in items[:100]:
        md = m.get("metadata") or {}
        dl = md.get("deadline")
        if not dl:
            continue
        dt = _parse_dt(dl)
        if not dt:
            continue
        delta = dt - now
        if delta.total_seconds() < 0:
            return {"type": "deadline", "severity": "high", "message": "Missed deadline", "scope": scope, "details": {"deadline": dt.isoformat(), "memory_id": m.get("id")}}
        if delta <= timedelta(days=1):
            return {"type": "deadline", "severity": "high", "message": "Deadline within 24 hours", "scope": scope, "details": {"deadline": dt.isoformat(), "memory_id": m.get("id")}}
        if delta <= timedelta(days=3):
            return {"type": "deadline", "severity": "medium", "message": "Deadline within 3 days", "scope": scope, "details": {"deadline": dt.isoformat(), "memory_id": m.get("id")}}
        if delta <= timedelta(days=7):
            return {"type": "deadline", "severity": "low", "message": "Deadline within a week", "scope": scope, "details": {"deadline": dt.isoformat(), "memory_id": m.get("id")}}
    return None

@register_detector("burstiness")
def det_burst(items: List[Dict[str, Any]], scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    last_hour = sum(1 for m in items if (t := _parse_dt(m.get("created_at"))) and now - t <= timedelta(hours=1))
    last_day = sum(1 for m in items if (t := _parse_dt(m.get("created_at"))) and now - t <= timedelta(days=1))
    if last_hour >= 20 or (last_hour >= 8 and last_hour > 0.5 * max(1, last_day)):
        return {"type": "burstiness", "severity": "medium" if last_hour < 20 else "high", "message": f"Spike: {last_hour}/h (day {last_day})", "scope": scope, "details": {"last_hour": last_hour, "last_day": last_day}}
    return None

@register_detector("negative_trend")
def det_sentiment(items: List[Dict[str, Any]], scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    texts = [(m.get("text") or "").lower() for m in items[:100]]
    neg = sum(1 for t in texts if any(k in t for k in NEGATIVE_HINTS))
    pos = sum(1 for t in texts if any(k in t for k in POSITIVE_HINTS))
    if neg >= 8 and neg > pos * 2:
        sev = "high"
    elif neg >= 5 and neg > pos * 1.5:
        sev = "medium"
    else:
        return None
    return {"type": "negative-trend", "severity": sev, "message": f"Negative {neg} vs positive {pos}", "scope": scope, "details": {"neg": neg, "pos": pos}}

@register_detector("preference_conflict")
def det_conflict(items: List[Dict[str, Any]], scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    prefers, dislikes = set(), set()
    for m in items[:200]:
        t = (m.get("text") or "").lower()
        for match in PREFERS_RE.finditer(t):
            prefers.add(match.group("thing").strip())
        for match in DISLIKES_RE.finditer(t):
            dislikes.add(match.group("thing").strip())
    conflicts = sorted(list(prefers.intersection(dislikes)))
    if conflicts:
        return {"type": "preference-contradiction", "severity": "low", "message": f"Conflicting: {', '.join(conflicts[:5])}", "scope": scope, "details": {"conflicts": conflicts}}
    return None

@register_detector("length_outliers")
def det_length(items: List[Dict[str, Any]], scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lengths = [len((m.get("text") or "")) for m in items[:200]]
    if len(lengths) < 10:
        return None
    mean = statistics.fmean(lengths)
    stdev = statistics.pstdev(lengths) or 1.0
    z = lambda L: (L - mean) / stdev
    high = sum(1 for L in lengths if z(L) > 3.0)
    low = sum(1 for L in lengths if z(L) < -2.5 and L < 20)
    if high >= 3 or low >= 5:
        return {"type": "content-outliers", "severity": "low", "message": f"Outlier lengths (high={high}, low={low})", "scope": scope, "details": {"mean": mean, "stdev": stdev, "high": high, "low": low}}
    return None