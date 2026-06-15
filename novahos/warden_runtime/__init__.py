"""Runtime WARDEN gate — the stateful, multi-agent enforcement surface. (Foundation; stdlib.)

The richer counterpart to the lean `novahos.warden` (`evaluate`/`score_action`): a 6-validator,
hash-chained-audited gate for the agent runtime, with agent suspension + cross-agent conflict +
auth-tier escalation. Both surfaces speak the same verdicts (approve/escalate/block) and, via
`adapters`, enforce the same novahos consent/privacy rules.

Quick start:  `w = build_warden(); d = w.evaluate(ActionRequest(agent="CROESUS", action="read",
action_class="read", payload={...}))` → `d.verdict`, `d.approved`, `w.audit_trail.verify_integrity()`.
"""
from .adapters import (  # noqa: F401
    NovahosConsentResolver,
    NovahosPrivacyClassifier,
    build_warden,
)
from .gate import Warden, WardenDecision  # noqa: F401
from .types import (  # noqa: F401
    ActionRequest,
    AuthTier,
    ConsentTier,
    Decision,
    PrivacyTier,
)
from .validators import default_validators  # noqa: F401

__all__ = [
    "build_warden", "Warden", "WardenDecision", "ActionRequest",
    "Decision", "ConsentTier", "AuthTier", "PrivacyTier",
    "NovahosConsentResolver", "NovahosPrivacyClassifier", "default_validators",
]
