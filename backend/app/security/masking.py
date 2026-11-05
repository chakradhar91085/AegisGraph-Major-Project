"""
AegisGraph — deterministic masking for MEDIUM-risk responses.

Applied in code (not requested from the LLM): e-mail addresses, phone numbers,
SSNs, money amounts and person names are replaced before the context reaches the
LLM, and again on the LLM's answer and the graph payload.

Names are found three ways, because no one way catches them all: names in this
answer's own rows, a list of every full name in the graph, and spaCy's language
model for names the graph does not hold (a first name in an email body).
"""
import logging
import re
from functools import lru_cache
from typing import Any, Iterable

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"(?<!\d)\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
_SCALE = r"(?:\s?(?:thousand|million|billion|mm|bn|k|m)\b)?"
_MONEY = re.compile(
    rf"[$€£]\s?\d[\d,]*(?:\.\d+)?{_SCALE}|\b\d[\d,]*(?:\.\d+)?{_SCALE}\s?(?:usd|dollars?|euros?|pounds?)\b",
    re.IGNORECASE,
)
_MARKERS = re.compile(r"\[REDACTED_(NAME|EMAIL|PHONE|SSN|AMOUNT)\]")
_HIDDEN_LABELS = {"NAME": "names", "EMAIL": "emails", "PHONE": "phones", "SSN": "ids", "AMOUNT": "amounts"}

# Result columns the agent uses for people.
_PERSON_KEYS = ("name", "sender", "recipient", "contact", "person", "people", "employee", "executive", "author")

# ── Every full name in the graph ─────────────────────────────────────────────
_WORD = re.compile(r"[^\W\d_][\w'’-]*")
_MAX_NAME_WORDS = 4
_known_names: set[str] = set()
_name_words: set[str] = set()
_known_surnames: set[str] = set()
_known_first_names: set[str] = set()

# Words that make a graph "name" not a person ("Thank You", "American Express", "All Employees").
# Mostly measured: words the emails use in lower case far more than capitalised. A real person
# with one of these words in their name ("Brent A. Price") is still found by spaCy.
_NOT_NAME_WORDS = frozenset("""
the and you for com this with will your from not can any all call time mail www one information email week today more
deal who now when make work day message net review don list good forward help available still year very copy office group
two schedule business changes look price morning great working much first deals change process people contract she then
down aol order employees letter soon data system most way home talk doc end free current html place keep update approval
document offer long info documents case link prices found additional everyone line confirm rate book feedback hotmail add
support read etc visit customers edu transaction little heard text reports problem desk cost response counterparty short
products money weeks above sell party ask product buy account room signed distribution low stock job presentation fine
close prior database chance htm value event font confidential cell happy important bankruptcy delivery options volume
direct thoughts non trades resume far full family second advise ago head confirmation tax trip care summer income release
bills rates files fun tickets law plant town savings cover storage action travel calendar clear supply analysis play key
reply pass planning unsubscribe fyi commercial structure weather friends requests invoice offers events paper quick ect
mean word msn plus groups large computer experience life requirements electronic card guess share guy press reminder
friend kind leaving clean updates small utility post assets software investment application success attorney means traders
ticket brief invitation organization critical ideas story write significant mailing continuing front sportsline equity
payments test half man telephone internal lawyer reporting insurance equipment air connection communication survey fast
invite hand registration lists broker base rules border body field record outages advantage nyiso quality users benefits
pager vkamins serve flight strong knowledge games agent solution officers accounts step features baby estimate resolution
huge perfect reservations miles pira fly graphics golf subscription iso maintenance bin catch sample forget reasons extra
businesses revenue candidates vote parking lines sans ran dispute enerfax flo wide values andrews economic programs cool
kids player kurth warning winter sessions offices restricted maximum billing round valuable hot employment league dog
downtown career walk loop pep exception range greater proud sick straight sheets buys clause bond collection flash expedia
minor sound stocks birthday till bunch eligible pro hands aren messaging movie formal tie shift weight eei discover
platform design core block commodities parent cycle scientech notices partner
on of to in at by us my we thank daily gas express airlines airline alumni network enron news team center services
service online weekly monthly power energy trading capital inc corp llc company bank associates management department
staff announcements administrator crawler migration restructuring analyst economist
""".split())

# Surnames that are also everyday words, places or firms, so they stay unless a title or the
# full name shows they are a person ("cash flow", "Love it", "Morgan Stanley", "January").
_AMBIGUOUS_SURNAMES = frozenset("""
new may hope page cash house love security newsletter white cross rice black green sole announcement guest grant
stage alert partners ring sweet booth grow alerts recipients social masters snow shoemaker rich pace stack port delivers
bike gold gang wells styles rank webmaster dictionary couch harder gates grass tiller pagan loving confer brands berry
gentle bridges rode goode moon stout heal lien iii relations young king
january february march april june july august september october november december monday tuesday wednesday thursday
friday saturday sunday south north east west edison sierra washington morgan jesus valley vegas texas california
""".split())
# A first name on its own line ("Michelle," or a sign-off) or after a greeting: the language model
# misses these. In rows a line break is written as the two characters \n, and a value opens with a quote.
_LINE_NAME = re.compile(r'(?:^|\n|\\n|\\r|")\s*([A-Z][a-z]+),?(?=\s*(?:\\[nr]|\n|$))', re.MULTILINE)
_GREETED_NAME = re.compile(r"\b(?:[Hh]i|[Hh]ello|[Hh]ey|[Dd]ear)\s+([A-Z][a-z]+)\b")
# "I spoke with Michelle": a first name is only safe to assume after a word that takes a person,
# since capitalised first names are also words ("Mark to market", "Bill payment").
_AFTER_PERSON_WORD = re.compile(r"\b(?:with|from|to|by|ask|asked|call|called|tell|told|thanks|for|and|cc)\s+([A-Z][a-z]{2,})\b")
_NOT_GREETED = frozenset("thanks thank regards best cheers sincerely hello dear hi all team folks everyone sir madam attached yes no ok okay".split())
_TITLED = re.compile(r"\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Z][\w'’-]+")
_CAPITALISED = re.compile(r"\b[A-Z][\w’-]*(?:'[A-Za-z]+)?\b")


def _name_key(words: Iterable[str]) -> str:
    """'Kenneth L. Lay' and 'kenneth lay' compare equal: lower case, no initials, no possessive."""
    cleaned = (re.sub(r"['’]s$", "", w.lower().strip(".")) for w in words)
    return " ".join(w for w in cleaned if len(w) > 1)


def load_names(names: Iterable[str], active: Iterable[str] = ()) -> None:
    """Single words are skipped: 'legal' and 'houston' are in the graph as names too.
    `active` people write or receive enough mail that their surname alone identifies them."""
    _known_names.clear()
    _name_words.clear()
    _known_surnames.clear()
    _known_first_names.clear()
    for name in names:
        words = name.split()
        if len(words) >= 2 and not any(w.lower().strip(".,") in _NOT_NAME_WORDS for w in words):
            _known_names.add(_name_key(words))
            _known_names.add(_name_key((words[0], words[-1])))
            _name_words.update(_name_key([w]) for w in words)
    _known_names.difference_update(k for k in list(_known_names) if " " not in k)
    _name_words.discard("")
    for name in active:
        words = name.split()
        if (len(words) >= 2 and len(words[-1]) >= 3 and words[-1].lower() not in _AMBIGUOUS_SURNAMES
                and not any(w.lower().strip(".,") in _NOT_NAME_WORDS for w in words)):
            _known_surnames.add(words[-1].lower())
            _known_first_names.add(words[0].lower())


async def ensure_names() -> None:
    """Load the name list once. If the graph is down, retry on the next masked answer."""
    if _known_names:
        return
    from app.db.neo4j import neo4j_client
    try:
        rows = await neo4j_client.execute_read(
            "MATCH (p:Person) WHERE p.name CONTAINS ' ' RETURN DISTINCT p.name AS name, "
            "coalesce(p.sent_count, 0) >= 20 OR coalesce(p.received_count, 0) >= 100 AS active", {})
        load_names((r["name"] for r in rows), (r["name"] for r in rows if r["active"]))
        logger.info(f"Masking name list: {len(_known_names)} names")
    except Exception as e:
        logger.warning(f"Could not load the masking name list: {e}")


def _joinable(gap: str, previous: str) -> bool:
    """Words of one name are separated by a space, a comma, or the dot after an initial."""
    if len(previous) == 1 and gap.startswith("."):
        gap = gap[1:]
    return bool(re.fullmatch(r",?\s+", gap)) and "\n" not in gap


def _mask_known_names(text: str, found: set[str] | None = None) -> str:
    """Hide full names from the list; `found` collects the ones this text contained."""
    if not _known_names:
        return text
    words = list(_WORD.finditer(text))
    out, position, i = [], 0, 0
    while i < len(words):
        matched = 0
        for size in range(min(_MAX_NAME_WORDS, len(words) - i), 1, -1):
            window = words[i:i + size]
            gaps = [text[a.end():b.start()] for a, b in zip(window, window[1:])]
            if not all(_joinable(g, a.group()) for g, a in zip(gaps, window)):
                continue
            tokens = [w.group() for w in window]
            # "Lay, Kenneth L." reads surname first; a comma anywhere else ends the name.
            comma = [g for g in gaps if "," in g]
            if comma and "," not in gaps[0] or len(comma) > 1:
                continue
            key = _name_key(tokens[1:] + tokens[:1]) if comma else _name_key(tokens)
            if key in _known_names:
                matched = size
                break
        if matched:
            start, end = words[i].start(), words[i + matched - 1].end()
            possessive = re.search(r"['’]s$", text[start:end])
            out += [text[position:start], "[REDACTED_NAME]"]
            if found is not None:
                found.add(" ".join(w.group() for w in words[i:i + matched]))
            position = end - (2 if possessive else 0)
            i += matched
        else:
            i += 1
    return "".join(out) + text[position:]


def _mask_name_parts(text: str, names: Iterable[str]) -> str:
    """Once a person is known to be in this answer, their first name or surname alone also identifies them."""
    parts = set()
    for name in names:
        for word in name.split():
            word = re.sub(r"['’]s$", "", word.strip(".,"))
            if len(word) >= 3 and word.isalpha() and word.lower() not in _NOT_NAME_WORDS:
                parts.update((word, word.capitalize(), word.upper()))
    if not parts:
        return text
    alternatives = "|".join(sorted(map(re.escape, parts), key=len, reverse=True))
    return re.sub(rf"\b(?:{alternatives})\b", "[REDACTED_NAME]", text)


def _mask_surnames(text: str) -> str:
    """Surnames of active people on their own ("linking Skilling and Fastow"), capitalised only."""
    text = _TITLED.sub("[REDACTED_NAME]", text)
    if not _known_surnames:
        return text

    def hide(match: re.Match) -> str:
        word = match.group()
        stem = re.sub(r"['’]s$", "", word)
        return "[REDACTED_NAME]" + word[len(stem):] if stem.lower() in _known_surnames else word

    return _CAPITALISED.sub(hide, text)


def _mask_greetings(text: str) -> str:
    def hide(match: re.Match) -> str:
        word = match.group(1)
        if word.lower() in _NOT_GREETED or (_name_words and word.lower() not in _name_words):
            return match.group()
        return match.group().replace(word, "[REDACTED_NAME]", 1)

    def hide_first_name(match: re.Match) -> str:
        word = match.group(1)
        return match.group().replace(word, "[REDACTED_NAME]", 1) if word.lower() in _known_first_names else match.group()

    return _AFTER_PERSON_WORD.sub(hide_first_name, _GREETED_NAME.sub(hide, _LINE_NAME.sub(hide, text)))


def people_in(*texts: str) -> set[str]:
    """Full names from the list that appear in these texts."""
    found: set[str] = set()
    for text in texts:
        _mask_known_names(text, found)
    return found


# ── Names the graph does not hold ────────────────────────────────────────────
@lru_cache(maxsize=1)
def nlp():
    try:
        import spacy
        return spacy.load("en_core_web_sm", exclude=["parser", "tagger", "lemmatizer", "attribute_ruler"])
    except Exception as e:  # masking keeps working on the two other sources of names
        logger.warning(f"spaCy name detection is unavailable: {e}")
        return None


def _is_person(entity) -> bool:
    """The small model calls title-case phrases people ("Meter 989614", "Need Money"), so ask
    for no digits and, once the name list is loaded, at least one word a real name uses."""
    if entity.label_ != "PERSON" or re.search(r"[\[\]\d]", entity.text):
        return False
    return not _name_words or any(_name_key([w]) in _name_words for w in entity.text.split())


def _mask_detected_names(text: str) -> str:
    model = nlp()
    if model is None:
        return text
    for entity in reversed(model(text).ents):
        if _is_person(entity):
            text = text[:entity.start_char] + "[REDACTED_NAME]" + text[entity.end_char:]
    return text


# ── Finding and hiding ───────────────────────────────────────────────────────
def names_from_text(*texts: str) -> set[str]:
    """Person names implied by e-mail addresses, e.g. jeff.dasovich@x.com -> 'jeff dasovich'."""
    names = set()
    for text in texts:
        for address in _EMAIL.findall(text):
            parts = [p for p in re.split(r"[._]", address.split("@")[0]) if p.isalpha() and len(p) > 1]
            if len(parts) >= 2:
                names.add(" ".join(parts))
    return names


def names_from_records(rows) -> set[str]:
    """Person names stored in result rows, e.g. {'sender': 'Kenneth L. Lay'}, also inside nested lists/maps."""
    names = set()
    for row in rows:
        for key, value in row.items():
            for v in value if isinstance(value, list) else [value]:
                if isinstance(v, dict):
                    names |= names_from_records([v])
                elif (any(k in key.lower() for k in _PERSON_KEYS)
                      and isinstance(v, str) and "@" not in v and 2 <= len(v.split()) <= 5):
                    names.add(v)
    return names


def mask_text(text: str, names=()) -> str:
    """Identifiers, plus the given names in any of their written forms."""
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _SSN.sub("[REDACTED_SSN]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    for name in names:
        first, last = re.escape(name.split()[0]), re.escape(name.split()[-1])
        middle = r"(?:[\s,]+[A-Za-z]\.?)?"  # "Kenneth L. Lay", "Lay, Kenneth L."
        pattern = rf"\b{first}{middle}[\s,]+{last}\b|\b{last}[\s,]+{first}{middle}(?!\w)"
        text = re.sub(pattern, "[REDACTED_NAME]", text, flags=re.IGNORECASE)
    return text


def scrub(text: str, names=()) -> str:
    """Everything MASK mode hides: identifiers, money and every name we can find."""
    people = set(names)
    text = mask_text(text, names)
    text = _mask_known_names(text, people)
    text = _mask_name_parts(text, people)
    text = _mask_surnames(text)
    text = _mask_greetings(text)
    text = _mask_detected_names(text)
    return _MONEY.sub("[REDACTED_AMOUNT]", text)


def hidden_counts(*texts: str) -> dict[str, int]:
    """How much was hidden, read from the placeholders, so it cannot carry real text.
    Several texts are versions of one answer, so each kind takes its highest count."""
    counts: dict[str, int] = {}
    for text in texts:
        found: dict[str, int] = {}
        for marker in _MARKERS.findall(text):
            label = _HIDDEN_LABELS[marker]
            found[label] = found.get(label, 0) + 1
        for label, n in found.items():
            counts[label] = max(counts.get(label, 0), n)
    return counts


def mask_graph(graph: dict, names=()) -> dict:
    """Pseudonymize Person nodes consistently and scrub other labels."""
    ids: dict[str, str] = {}
    nodes = []
    for raw in graph.get("nodes", []):
        # Only counts, scores and sensitivity tags survive; any free text could hold a name.
        details = {k: v for k, v in raw.get("details", {}).items() if isinstance(v, (int, float)) or k.lower() == "sensitivity"}
        node = {**raw, "details": details}
        if node["type"] == "Person":
            new_id = ids.setdefault(node["id"], f"person-{sum(i.startswith('person-') for i in ids.values()) + 1}")
            nodes.append({**node, "id": new_id, "label": new_id.replace("-", " ").title()})
        else:
            label = scrub(node["label"], names)
            if node["type"] == "Theme":  # a theme's id is its name, which can hold a person's
                ids[node["id"]] = f"theme:{label}"
                node["id"] = ids[node["id"]]
            nodes.append({**node, "label": label})
    edges = [
        {**e, "source": ids.get(e["source"], e["source"]), "target": ids.get(e["target"], e["target"])}
        for e in graph.get("edges", [])
    ]
    return {"nodes": nodes, "edges": edges}


# ── Counts ───────────────────────────────────────────────────────────────────
MIN_CELL_SIZE = 5  # a smaller group can point at one person
_COUNT_KEY = re.compile(r"count|total|number|emails?|messages|sent|received|contacts|mentions|size|cnt", re.IGNORECASE)


def safe_count(n: int, mask: bool) -> int | str:
    if n < MIN_CELL_SIZE:
        return f"fewer than {MIN_CELL_SIZE}"
    if mask:
        return f"approximately {max(10, round(n, -2 if n >= 100 else -1)):,}"
    return n


def safe_counts(value: Any, mask: bool, key: str = "") -> Any:
    """Apply safe_count to every count column in result rows, however deeply nested."""
    if isinstance(value, dict):
        return {k: safe_counts(v, mask, k) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_counts(v, mask, key) for v in value]
    if isinstance(value, int) and not isinstance(value, bool) and _COUNT_KEY.search(key):
        return safe_count(value, mask)
    return value
