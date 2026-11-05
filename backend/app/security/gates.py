"""
AegisGraph — hard security gates: checks on one piece of text that force a minimum
risk regardless of the user's behaviour.

Queries get two checks. Attacks on the system (prompt injection, claiming authority)
go straight to HIGH. Everything else is rated on two independent questions: what kind
of data does it name, and what does it ask to do with it? DISCLOSURE_FLOORS turns that
pair into a floor, so one salary lookup is masked while "list all salaries" is blocked.

Retrieved rows get the attack check too, since an email can carry an instruction that
the user never typed (quarantine).
"""
import re
from typing import Any

HIGH = 0.65
MEDIUM = 0.35

_OVERRIDE = r"(?:ignore|disregard|forget|set aside|stop following|override|bypass)"
_RULES = r"(?:instructions?|rules?|prompts?|guidelines?|polic(?:y|ies)|guardrails?|restrictions?|filters?|security|access)"
_AUTHORITY = r"(?:admin|administrator|root|developer|auditor|superuser)"

# Instructions aimed at the AI. Never legitimate, whoever or whatever says them.
_ATTACK = (
    rf"{_OVERRIDE}\s+(?:(?:all|any|the|your|my|of|previous|prior|above|earlier|these|those)\s+)*{_RULES}"
    r"|(?:reveal|show|print|repeat|what\s+(?:is|are))\s+(?:me\s+)?(?:your\s+|the\s+)?(?:system|hidden|initial)\s+(?:prompt|instructions?)"
    r"|developer\s+mode|jailbreak"
    rf"|{_AUTHORITY}\s+mode"
    # Claiming to have no limits, or that the limits are gone.
    r"|(?:pretend|imagine|act\s+as\s+if)\b.{0,40}\b(?:no|without)\s+(?:any\s+)?(?:rules|restrictions|filters|limits)"
    r"|(?:rules?|restrictions?|polic(?:y|ies)|filters?)\s+(?:no\s+longer\s+appl(?:y|ies)|(?:are|is)\s+(?:lifted|void|off))"
    rf"|you\s+are\s+now\s+(?:the\s+|an?\s+)?(?:system\s+|aegisgraph\s+)?{_AUTHORITY}"
    rf"|(?:act|behave|pose)\s+as\s+(?:the\s+|an?\s+)?(?:system\s+)?{_AUTHORITY}"
    # Asking for the protection itself to be switched off.
    r"|(?:turn\s+off|disable|remove|skip)\s+(?:the\s+|any\s+|all\s+)?(?:mask(?:ing)?|redaction|filters?)"
    r"|\bunmask\b"
)
# Claiming authority: an attack in a question, but ordinary in an email ("I have full access").
_CLAIM = (
    rf"i(?:'m|\s+am)\s+(?:the\s+|an?\s+)?(?:system\s+|database\s+)?{_AUTHORITY}"
    rf"|as\s+(?:the\s+|an?\s+)?(?:system\s+)?{_AUTHORITY}\b.{{0,40}}\b(?:authori[sz]e|order|instruct)"
    r"|(?:with|has|have)\s+(?:full|unrestricted|admin)\s+(?:clearance|access|privileges)"
)
ATTACK = re.compile(_ATTACK, re.IGNORECASE)
INJECTION = re.compile(f"{_ATTACK}|{_CLAIM}", re.IGNORECASE)

# Kinds of data a question can name.
_CLASSES = {
    "identifier": re.compile(
        r"\b(?:ssns?|social\s+security|passports?|credit\s+cards?|bank\s+accounts?|passwords?|credentials?|"
        r"dates?\s+of\s+birth|birth\s*dates?|home\s+(?:phone|address)|personal\s+(?:phone|email|cell|mobile|address)|pii)\b",
        re.IGNORECASE),
    "contact": re.compile(r"\b(?:phone|mobile|cell)\s+numbers?\b|\bemail\s+addresses\b|\bemail\s+address\b", re.IGNORECASE),
    "compensation": re.compile(
        r"\b(?:salary|salaries|compensation|bonus(?:es)?|severance|payroll|"
        r"retention\s+(?:agreements?|bonus(?:es)?|payments?|plans?))\b",
        re.IGNORECASE),
    "legal": re.compile(r"\b(?:privileged|attorney[-\s]client|lawsuits?|litigation|subpoenas?)\b", re.IGNORECASE),
    "confidential": re.compile(r"\b(?:confidential|proprietary|trade\s+secrets?|insider\s+information)\b", re.IGNORECASE),
}

# What the question asks for, most consequential first; anything else is one lookup.
ENUMERATE, DESCRIBE, LOOKUP = "list everything", "a summary", "a lookup"
_ENUMERATE = re.compile(r"\b(?:list|every|all(?!\s+about\b)|each|dump|export|enumerate|verbatim|raw|bulk|entire|complete)\b", re.IGNORECASE)
_DESCRIBE = re.compile(r"\b(?:summari[sz]e|describe|overview|general\s+sense|trends?\s+in|discuss(?:ed|es)?|all\s+about)\b", re.IGNORECASE)

# A pair not listed here adds nothing; behaviour still applies.
DISCLOSURE_FLOORS = {
    ("identifier", DESCRIBE): MEDIUM,
    ("identifier", LOOKUP): HIGH,
    ("identifier", ENUMERATE): HIGH,
    ("contact", LOOKUP): MEDIUM,
    ("contact", ENUMERATE): HIGH,
    ("compensation", LOOKUP): MEDIUM,
    ("compensation", ENUMERATE): HIGH,
    ("legal", LOOKUP): MEDIUM,
    ("legal", ENUMERATE): HIGH,
    ("confidential", ENUMERATE): MEDIUM,
}

_TERM = r"(?:ssns?|social\s+security(?:\s+numbers?)?|pii|passwords?|credentials?|compensation|severance|salary|bonus(?:es)?)"
_SAFE = re.compile(
    # A definition: the term alone, about nobody in particular.
    rf"^\s*(?:what\s+(?:is|are|does)|define|meaning\s+of)\s+(?:an?\s+|the\s+)?{_TERM}(?:\s+(?:mean|used\s+for|stand\s+for))?\s*\??\s*$"
    # Asking how to protect the data rather than asking for it.
    r"|\bhow\s+(?:do|should|can|could|would|to)\b.{0,30}\b(?:protect|secure|safeguard|prevent|redact|detect|comply)\b"
    r"|\bbest\s+practices\s+for\b",
    re.IGNORECASE,
)

_COUNT_QUESTION = re.compile(r"\bhow\s+many\b|\b(?:number|count|total)\s+of\b|\bheadcount\b", re.IGNORECASE)


def action_of(query: str) -> str:
    if _ENUMERATE.search(query):
        return ENUMERATE
    return DESCRIBE if _DESCRIBE.search(query) else LOOKUP


def gate_check(query: str) -> tuple[float, str]:
    """The minimum risk this query forces, and why (for the admin alert)."""
    if INJECTION.search(query):
        return HIGH, "Prompt-injection / privilege-escalation attempt detected"
    if _SAFE.search(query):
        return 0.0, ""
    action = action_of(query)
    floor, reason = 0.0, ""
    for name, pattern in _CLASSES.items():
        tier = DISCLOSURE_FLOORS.get((name, action), 0.0)
        if tier > floor and pattern.search(query):
            floor, reason = tier, f"Sensitive request detected: {name} data, asked for as {action}"
    return floor, reason


def gate_score(query: str) -> float:
    return gate_check(query)[0]


def is_count_question(query: str) -> bool:
    return bool(_COUNT_QUESTION.search(query))


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def quarantine(rows: list) -> tuple[list, int]:
    """Drop rows whose text looks like an attack, so neither model ever reads it.
    Returns the rows to keep and how many were withheld."""
    kept = [row for row in rows if not any(ATTACK.search(s) for s in _strings(row))]
    return kept, len(rows) - len(kept)
