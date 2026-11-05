"""The records behind an answer, shaped for the "Retrieved records" list in the UI.

Agent rows have whatever columns the LLM chose, so read them by name. In MASK mode every
piece of text goes through `clean` first, so the list shows what was hidden, not the data.
"""
from typing import Any, Callable

_SKIP = ("id", "embedding", "score", "pii", "seniority")
_DATE_KEYS = ("sent_on", "sent_at", "timestamp", "date")
_BODY_KEYS = ("body", "snippet", "text", "preview", "content")
_MAX_FIELDS = 6
_SNIPPET = 240


def _plain(value: Any) -> str:
    """A list or nested row as short text: themes and top people in an overview row."""
    if isinstance(value, list):
        return ", ".join(_plain(v) for v in value[:6])
    if isinstance(value, dict):
        return next((str(v) for v in value.values() if isinstance(v, str)), "")
    return str(value)


def build_records(rows: list[dict], limit: int, clean: Callable[[str], str] = lambda s: s) -> list[dict]:
    records = []
    for row in rows[:limit]:
        keys = {k.lower(): k for k in row}
        subject = row.get(keys.get("subject", ""))
        date = next((row[keys[k]] for k in _DATE_KEYS if row.get(keys.get(k, ""))), None)
        body = next((row[keys[k]] for k in _BODY_KEYS if row.get(keys.get(k, ""))), None)
        labels = row.get(keys.get("sensitivity", "")) or []

        fields = []
        for key, value in row.items():
            k = key.lower()
            if value in (None, "", []) or isinstance(value, bool) or k in ("subject", "sensitivity") or k in _DATE_KEYS or k in _BODY_KEYS or k.endswith(_SKIP):
                continue
            fields.append((key.replace("_", " "), _plain(value)))

        # A row with no subject (a ranking, a contact list) is titled by its first field.
        title = str(subject) if subject else (fields.pop(0)[1] if fields else "")
        if not title and not body:
            continue
        records.append({
            "title": clean(title[:120]),
            "date": str(date)[:10] if date else None,
            "fields": [{"name": name, "value": clean(value[:160])} for name, value in fields[:_MAX_FIELDS]],
            "snippet": clean(str(body)[:_SNIPPET]) if body else None,
            "labels": [str(label) for label in labels] if isinstance(labels, list) else [],
        })
    return records
