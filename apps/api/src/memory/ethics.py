from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Callable
import json
import os
import re
import structlog

logger = structlog.get_logger("memory.ethics")

# Defaults
DEFAULT_MAX_SCAN_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass(frozen=True)
class EthicsError:
    where: str
    id: Optional[str]
    message: str


Rule = Dict[str, Any]
CompiledRule = Tuple[Rule, re.Pattern]


class PolicyEngine:
    """
    Configurable ethical policy checks with safeguards and extensibility.

    Features:
    - Regex rules with input size guard to avoid regex DoS.
      Each rule: {"id":"...", "pattern":"regex", "action":"deny|flag", "severity":"low|medium|high", "reason":"..."}
    - Allowlist: metadata["whitelist"] or metadata["allowlist"] skips rule evaluation (returns "allow").
    - Metadata policies: pluggable callables that inspect metadata for domain-specific checks (e.g., GDPR).
    - Decision aggregation: summary() collapses decisions to an overall action.
      - deny if any decision.action == "deny"
      - else flag if any "flag"
      - else allow
    - Structured error capture via EthicsError for clean logging.

    Usage:
      engine = PolicyEngine(rules_path="rules.json")
      decisions = engine.evaluate(text, metadata)
      overall = engine.summary(decisions)
    """

    def __init__(
        self,
        rules: Optional[List[Rule]] = None,
        rules_path: Optional[str] = None,
        max_scan_bytes: Optional[int] = None,
        short_circuit_on_oversize: bool = True,
        metadata_policies: Optional[List[Tuple[str, Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]]]] = None,
    ) -> None:
        self.errors: List[EthicsError] = []
        self.max_scan_bytes = int(
            max_scan_bytes if max_scan_bytes is not None else int(os.getenv("ETHICS_MAX_SCAN_BYTES", DEFAULT_MAX_SCAN_BYTES))
        )
        self.short_circuit_on_oversize = bool(short_circuit_on_oversize)
        loaded = rules or self._load_rules(rules_path or os.getenv("ETHICS_RULES_PATH"))
        self.rules: List[CompiledRule] = []
        self._compile(loaded)
        self.metadata_policies: List[Tuple[str, Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]]] = []
        # Register built-ins first, then user-provided
        for pol in self._default_metadata_policies():
            self.add_metadata_policy(*pol)
        if metadata_policies:
            for name, fn in metadata_policies:
                self.add_metadata_policy(name, fn)

    # ---------- Loading and compilation ----------

    def _load_rules(self, path: Optional[str]) -> List[Rule]:
        if not path:
            # Sensible defaults
            return [
                {
                    "id": "pii_email",
                    "pattern": r"\b[\w\.-]+@[\w\.-]+\.\w+\b",
                    "action": "flag",
                    "severity": "medium",
                    "reason": "PII: email detected",
                },
                {
                    "id": "credential_like",
                    "pattern": r"\b(AKI[A-Z0-9]{16}|secret_key|password|x-api-key)\b",
                    "action": "deny",
                    "severity": "high",
                    "reason": "Secrets detected",
                },
            ]
        try:
            content = open(path, "r", encoding="utf-8").read()
            return json.loads(content)
        except Exception as e:
            err = EthicsError(where="load_rules", id=None, message=str(e))
            self.errors.append(err)
            logger.warning("ethics_rules_load_failed", error=str(e), path=path)
            return []

    def _compile(self, rules: List[Rule]) -> None:
        self.rules.clear()
        for r in rules:
            rid = r.get("id")
            pat = r.get("pattern", "")
            try:
                compiled = re.compile(pat, re.I | re.M)
                self.rules.append((r, compiled))
            except Exception as e:
                err = EthicsError(where="compile_rule", id=rid, message=str(e))
                self.errors.append(err)
                logger.warning("ethics_rule_compile_failed", id=rid, error=str(e))

    # ---------- Metadata policies ----------

    def add_metadata_policy(self, name: str, fn: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]) -> None:
        """
        Policy fn signature: (metadata) -> decision | None
        decision should be of the form:
          {"id": name, "action": "deny|flag|allow", "severity": "low|medium|high", "reason": "...", "matches": True}
        """
        self.metadata_policies.append((name, fn))

    def _default_metadata_policies(self) -> List[Tuple[str, Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]]]:
        def policy_public_pii(md: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if md.get("public") is True and md.get("contains_pii") is True:
                return {
                    "id": "public_with_pii",
                    "action": "deny",
                    "severity": "high",
                    "reason": "PII not allowed in public artifacts",
                    "matches": True,
                }
            return None

        def policy_gdpr(md: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            # If flagged as personal_data, require lawful_basis
            if md.get("personal_data") is True and not md.get("lawful_basis"):
                return {
                    "id": "gdpr_lawful_basis_missing",
                    "action": "flag",
                    "severity": "medium",
                    "reason": "Personal data without lawful basis",
                    "matches": True,
                }
            return None

        def policy_safety(md: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            # Example: block unsafe model usage contexts
            if (md.get("model_safety") or "").lower() in {"unsafe", "experimental"} and md.get("exposure") == "public":
                return {
                    "id": "model_safety_public_exposure",
                    "action": "flag",
                    "severity": "medium",
                    "reason": "Experimental/unsafe model exposed publicly",
                    "matches": True,
                }
            return None

        return [("public_pii", policy_public_pii), ("gdpr", policy_gdpr), ("safety", policy_safety)]

    # ---------- Evaluation ----------

    def evaluate_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Evaluate text against regex rules with input-size guard.
        - If input exceeds max_scan_bytes and short_circuit_on_oversize=True, short-circuit with a single 'flag' decision.
        """
        if not text:
            return []

        # Guard: approximate size by character count; conservative for ReDoS avoidance.
        text_len = len(text)
        if text_len > self.max_scan_bytes and self.short_circuit_on_oversize:
            logger.warning(
                "ethics_input_oversize",
                length=text_len,
                max_scan_bytes=self.max_scan_bytes,
            )
            return [
                {
                    "id": "input_too_large",
                    "action": "flag",
                    "severity": "low",
                    "reason": f"Input exceeds max scan size ({self.max_scan_bytes} bytes); regex checks skipped",
                    "matches": True,
                    "details": {"length": text_len, "max_scan_bytes": self.max_scan_bytes},
                }
            ]

        # Optionally truncate to limit but continue scanning (safe bound)
        truncated = False
        content = text
        if text_len > self.max_scan_bytes and not self.short_circuit_on_oversize:
            content = text[: self.max_scan_bytes]
            truncated = True

        decisions: List[Dict[str, Any]] = []
        for r, pat in self.rules:
            try:
                if pat.search(content):
                    decisions.append(
                        {
                            "id": r.get("id", "rule"),
                            "action": r.get("action", "flag"),
                            "severity": r.get("severity", "low"),
                            "reason": r.get("reason", ""),
                            "matches": True,
                        }
                    )
            except Exception as e:
                err = EthicsError(where="regex_eval", id=r.get("id"), message=str(e))
                self.errors.append(err)
                logger.warning("ethics_rule_eval_failed", id=r.get("id"), error=str(e))
        if truncated:
            decisions.append(
                {
                    "id": "input_truncated",
                    "action": "flag",
                    "severity": "low",
                    "reason": f"Input truncated at {self.max_scan_bytes} bytes for safe scanning",
                    "matches": True,
                }
            )
        return decisions

    def evaluate_metadata(self, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        md = metadata or {}
        decisions: List[Dict[str, Any]] = []

        # Built-in quick check retained for backward compatibility
        if md.get("public") is True and md.get("contains_pii") is True:
            decisions.append(
                {
                    "id": "public_with_pii",
                    "action": "deny",
                    "severity": "high",
                    "reason": "PII not allowed in public artifacts",
                    "matches": True,
                }
            )

        # Registered metadata policies
        for name, fn in self.metadata_policies:
            try:
                res = fn(md)
                if res:
                    # ensure id present
                    if "id" not in res:
                        res["id"] = name
                    decisions.append(res)
            except Exception as e:
                err = EthicsError(where="metadata_policy", id=name, message=str(e))
                self.errors.append(err)
                logger.warning("ethics_metadata_policy_failed", policy=name, error=str(e))

        return decisions

    def evaluate(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Allowlist/whitelist short-circuit
        md = metadata or {}
        if md.get("whitelist") is True or md.get("allowlist") is True:
            return [
                {
                    "id": "allowlist",
                    "action": "allow",
                    "severity": "low",
                    "reason": "Content allowlisted; rules skipped",
                    "matches": True,
                }
            ]

        out: List[Dict[str, Any]] = []
        out.extend(self.evaluate_text(text or ""))
        out.extend(self.evaluate_metadata(md))
        return out

    # ---------- Aggregation ----------

    @staticmethod
    def summary(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Collapse detailed decisions into an overall action.
        Rules:
          - 'deny' if any decision.action == 'deny'
          - else 'flag' if any decision.action == 'flag'
          - else 'allow'
        """
        deny = [d for d in decisions if str(d.get("action", "")).lower() == "deny"]
        flag = [d for d in decisions if str(d.get("action", "")).lower() == "flag"]
        allow = [d for d in decisions if str(d.get("action", "")).lower() == "allow"]

        if deny:
            overall = "deny"
        elif flag:
            overall = "flag"
        else:
            overall = "allow"

        return {
            "action": overall,
            "counts": {"deny": len(deny), "flag": len(flag), "allow": len(allow)},
            "ids": [d.get("id") for d in decisions],
            "decisions": decisions,
        }