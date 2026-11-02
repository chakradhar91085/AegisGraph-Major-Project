"""
AegisGraph — enrich the Enron graph in place (additive: nothing is deleted).

Phases (run any subset, in this order):
  indexes      range indexes on Person.email and Email.emailId (lookups were full scans)
  names        Person.name from the raw X-From headers (the import kept only addresses);
               address-derived fallback; core-mailbox owners flagged is_core
  activity     Person.sent_count / received_count / contacts and an aggregated
               (Person)-[:COMMUNICATES_WITH {count, first, last}]->(Person)
  content      Email.sensitivity labels, pii, sensitivity_score, is_reply/is_forward,
               recipient_count, sent_on (datetime); (Email)-[:IN_FOLDER]->(Folder)
  roles        Person.title / position / seniority for core employees
               (../data/enron_custodian_titles.csv, EnronData.org, CC BY 3.0)
  themes       ~40 Theme nodes clustered from the email embeddings, (Email)-[:ABOUT]->(Theme)

Usage (from backend/):
  venv/Scripts/python.exe scripts/enrich_graph.py names --mailbox lay-k --dry-run
  venv/Scripts/python.exe scripts/enrich_graph.py indexes names activity

The original graph can be rebuilt from ../neo4j_import/*.csv if needed.
"""
import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict
from email.parser import HeaderParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from neo4j import GraphDatabase  # noqa: E402
from app.core.config import settings  # noqa: E402

MAILDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "enron_mail_20150507", "maildir"))
if os.name == "nt":
    MAILDIR = "\\\\?\\" + MAILDIR  # Enron files are named "1." etc.; Windows drops the trailing dot without this prefix
SENT_FOLDERS = {"sent", "_sent", "sent_items", "_sent_mail"}


def driver():
    return GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD))


def write(session, query: str, rows: list, batch: int = 2000) -> None:
    for i in range(0, len(rows), batch):
        session.run(query, rows=rows[i:i + batch]).consume()


# ── indexes ───────────────────────────────────────────────────────────────

def phase_indexes(session, args) -> None:
    session.run("CREATE INDEX person_email IF NOT EXISTS FOR (p:Person) ON (p.email)").consume()
    session.run("CREATE INDEX email_id IF NOT EXISTS FOR (e:Email) ON (e.emailId)").consume()
    session.run("CALL db.awaitIndexes(600)").consume()
    print("indexes: person_email, email_id online")


# ── names ─────────────────────────────────────────────────────────────────

def clean_display_name(raw: str) -> str | None:
    """'Lay, Kenneth </O=ENRON/...>' -> 'Kenneth Lay'; addresses and junk -> None."""
    name = re.sub(r"<[^>]*>", "", raw or "")
    name = re.sub(r"[\"'()]", "", name).strip()
    if not name or "@" in name or "/" in name or "=" in name:
        return None
    if name.count(",") == 1:
        last, first = (part.strip() for part in name.split(","))
        name = f"{first} {last}"
    name = re.sub(r"\s+", " ", name).strip(" .,-")
    words = name.split()
    if not 2 <= len(words) <= 5 or len(name) > 50 or not all(re.search(r"[A-Za-z]", w) for w in words):
        return None
    return name.title() if name.isupper() or name.islower() else name


def name_from_address(address: str) -> str | None:
    """'kenneth.lay@enron.com' -> 'Kenneth Lay' (only clean first.last style addresses)."""
    parts = re.split(r"[._]", address.split("@")[0])
    if len(parts) < 2 or not all(p.isalpha() for p in parts) or len(parts[0]) < 2 or len(parts[-1]) < 2:
        return None
    return " ".join(p.capitalize() if len(p) > 1 else p.upper() + "." for p in parts)


def read_headers(path: str):
    with open(path, "rb") as f:
        head = f.read(8192).split(b"\r\n\r\n", 1)[0].split(b"\n\n", 1)[0]
    return HeaderParser().parsestr(head.decode("latin-1"))


def scan_mailbox(mb: str):
    """One mailbox -> (display-name votes per address, sender votes, file count)."""
    names: dict[str, Counter] = defaultdict(Counter)
    senders: Counter = Counter()
    files = 0
    for root, _, fnames in os.walk(os.path.join(MAILDIR, mb)):
        weight = 3 if os.path.basename(root).lower() in SENT_FOLDERS else 1
        for fname in fnames:
            files += 1
            try:
                h = read_headers(os.path.join(root, fname))
            except OSError:
                continue
            address = (h.get("From") or "").strip().lower()
            if "@" not in address:
                continue
            if (name := clean_display_name(h.get("X-From"))):
                names[address][name] += 1
            senders[address] += weight
    return mb, names, senders, files


def mailbox_owner(mb: str, senders: Counter) -> str | None:
    """The owner of 'lay-k' is the busiest sender whose address has the surname as a whole
    token (kenneth.lay, not l..nicolay) - not simply the busiest sender, which for
    executives is their assistant (rosalee.fleming sent most of lay-k/sent)."""
    surname, _, initial = mb.rpartition("-")
    surname = surname.replace("-", "")
    for address, _ in senders.most_common():
        tokens = [t for t in re.split(r"[._-]", address.split("@")[0]) if t]
        joined = "".join(tokens)
        if surname in tokens or (joined.endswith(surname) and joined.startswith(initial)):
            return address
    return None


def phase_names(session, args) -> None:
    from concurrent.futures import ProcessPoolExecutor
    mailboxes = [args.mailbox] if args.mailbox else sorted(os.listdir(MAILDIR))
    seen: dict[str, Counter] = defaultdict(Counter)   # address -> display-name votes
    owners, unmatched, files, t0 = [], [], 0, time.time()
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 4)) as pool:
        for mb, names, senders, n in pool.map(scan_mailbox, mailboxes):
            files += n
            for address, votes in names.items():
                seen[address].update(votes)
            if (owner := mailbox_owner(mb, senders)):
                owners.append({"email": owner, "mailbox": mb})
            else:
                unmatched.append(mb)
            print(f"  {mb}: {files} files, {len(seen)} named senders ({time.time() - t0:.0f}s)", flush=True)

    rows = [{"email": a, "name": c.most_common(1)[0][0], "source": "header"} for a, c in seen.items()]
    print(f"names: {len(rows)} from headers; owners for {len(owners)} mailboxes; no owner: {unmatched}")
    for r in rows[:8]:
        print("  e.g.", r["email"], "->", r["name"])
    for o in owners[:5]:
        print("  owner", o["mailbox"], "->", o["email"])
    if args.dry_run:
        return

    write(session, """
        UNWIND $rows AS r MATCH (p:Person {email: r.email})
        SET p.name = r.name, p.name_source = r.source""", rows)
    # Everyone else (mostly recipients who never sent mail): derive from a clean address.
    if not args.mailbox:
        rest = session.run("""
            MATCH (p:Person) WHERE p.name_source IS NULL RETURN p.email AS email""").value()
        derived = [{"email": e, "name": n, "source": "address"} for e in rest if (n := name_from_address(e))]
        write(session, """
            UNWIND $rows AS r MATCH (p:Person {email: r.email})
            SET p.name = r.name, p.name_source = r.source""", derived)
        print(f"names: {len(derived)} derived from addresses")
    if not args.mailbox:
        # The import pinned some mailboxes on assistants; re-derive all of them.
        session.run("MATCH (p:Person) WHERE p.mailbox IS NOT NULL REMOVE p.mailbox").consume()
    write(session, """
        UNWIND $rows AS r MATCH (p:Person {email: r.email})
        SET p.is_core = true, p.mailbox = r.mailbox""", owners)
    session.run("MATCH (p:Person) WHERE p.is_core IS NULL SET p.is_core = false").consume()
    print("names: written")


# ── activity ──────────────────────────────────────────────────────────────

def phase_activity(session, args) -> None:
    t0 = time.time()
    session.run("""
        MATCH (p:Person)
        CALL (p) {
          SET p.sent_count = COUNT { (p)-[:SENT]->(:Email) },
              p.received_count = COUNT { (:Email)-[:SENT_TO|CC_TO]->(p) }
        } IN TRANSACTIONS OF 5000 ROWS""").consume()
    print(f"activity: counts set ({time.time() - t0:.0f}s)", flush=True)
    # BCC_TO duplicates CC_TO in this corpus, so only TO and CC count as contact.
    session.run("""
        MATCH (a:Person) WHERE a.sent_count > 0
        CALL (a) {
          MATCH (a)-[:SENT]->(e:Email)-[:SENT_TO|CC_TO]->(b:Person) WHERE b <> a
          WITH a, b, count(DISTINCT e) AS n, min(e.sent_at) AS first, max(e.sent_at) AS last
          MERGE (a)-[c:COMMUNICATES_WITH]->(b)
          SET c.count = n, c.first = first, c.last = last
        } IN TRANSACTIONS OF 200 ROWS""").consume()
    print(f"activity: COMMUNICATES_WITH built ({time.time() - t0:.0f}s)", flush=True)
    session.run("""
        MATCH (p:Person)
        CALL (p) {
          SET p.contacts = COUNT { MATCH (p)-[:COMMUNICATES_WITH]-(q) RETURN DISTINCT q }
        } IN TRANSACTIONS OF 5000 ROWS""").consume()
    print(f"activity: contacts set ({time.time() - t0:.0f}s)")


# ── content: sensitivity labels, PII, folders, real dates ─────────────────

# ponytail: keyword/regex heuristic, transparent and fast over 251k emails; it will
# miss paraphrases and over-tag some. Upgrade path: a small trained classifier.
CATEGORIES = {  # label -> (weight, pattern on lowercased subject+body)
    "Legal": (0.8, r"attorney[- ]client|\bprivileged\b|litigation|lawsuit|subpoena|deposition|indemnif"
                   r"|legal (?:department|counsel|advice)|settlement agreement|class action"),
    "Financial": (0.7, r"\bearnings\b|quarterly results|\b10-[qk]\b|balance sheet|write[- ]?(?:down|off)"
                       r"|mark[- ]to[- ]market|off[- ]balance|\bljm\b|\braptor\b|credit rating|share price|stock price"),
    "HR": (0.8, r"\bsalary\b|compensation|\bbonus\b|performance review|\bprc\b|termination|severance"
                r"|\blayoffs?\b|\bresume\b|401\(?k\)?|benefits enrollment"),
    "Personal": (0.6, r"\bmy (?:wife|husband|kids|son|daughter|mom|dad|mother|father)\b|birthday|\bdoctor\b"
                      r"|hospital|surgery|wedding|divorce|pregnan|funeral"),
    "Confidential": (0.7, r"\bconfidential\b|do not (?:forward|distribute)|\bproprietary\b|internal use only"
                          r"|not for distribution|strictly private"),
}
PII = {  # type -> (weight, pattern on original text)
    "ssn": (1.0, r"\b\d{3}-\d{2}-\d{4}\b"),
    "card": (1.0, r"\b(?:\d{4}[- ]){3}\d{4}\b"),
    "dob": (0.8, r"(?i)date of birth|\bd\.?o\.?b\.?:"),
    # Mostly office addresses (1400 Smith Street = Enron HQ), so a weak signal.
    "address": (0.3, r"\b\d{2,5} [A-Z][a-z]+(?: [A-Z][a-z]+)? (?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct)\b"),
    "phone": (0.3, r"(?<!\d)\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"),
}
FOLDER_HINTS = {"Personal": r"personal|family|private", "Legal": r"legal|lawsuit|litigation",
                "HR": r"\bhr\b|resume|benefit|personnel"}
# Legal footers (Enron's own and every law firm's: "...privileged and confidential ... intended
# recipient...") sit on thousands of routine mails; paragraphs that read like one are dropped
# so they do not mark everything Legal/Confidential.
_BOILERPLATE = re.compile(
    r"intended (?:only )?(?:for the (?:sole )?use|recipient)|is the property of enron"
    r"|(?:may|might) contain (?:confidential|privileged|proprietary)|privileged and confidential information"
    r"|notify (?:the sender|us) immediately|any (?:review|dissemination|distribution) .{0,40}prohibited", re.I)


class _Disclaimer:
    """Drop boilerplate paragraphs (same .sub interface the callers use)."""
    @staticmethod
    def sub(_repl: str, text: str) -> str:
        return "\n\n".join(p for p in re.split(r"\n\s*\n", text) if not _BOILERPLATE.search(p))


DISCLAIMER = _Disclaimer()
_CAT = {k: (w, re.compile(p)) for k, (w, p) in CATEGORIES.items()}
_PII = {k: (w, re.compile(p)) for k, (w, p) in PII.items()}
_FOLD = {k: re.compile(p) for k, p in FOLDER_HINTS.items()}


def luhn(number: str) -> bool:
    """Card-number checksum; rejects tracking/certified-mail numbers of the same shape."""
    digits = [int(c) for c in number if c.isdigit()][::-1]
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2) for i, d in enumerate(digits)) % 10 == 0


def classify(subject: str, body: str, folders: list[str]) -> tuple[list[str], list[str], float]:
    text = DISCLAIMER.sub(" ", f"{subject}\n{body}")
    low = text.lower()
    labels = {k for k, (_, rx) in _CAT.items() if rx.search(low)}
    labels |= {k for k, rx in _FOLD.items() if any(rx.search(f.split("/", 1)[-1].lower()) for f in folders)}
    pii = [k for k, (_, rx) in _PII.items()
           if (any(luhn(m.group(0)) for m in rx.finditer(text)) if k == "card" else rx.search(text))]
    score = max([_CAT[k][0] for k in labels] + [_PII[k][0] for k in pii] + [0.0])
    return sorted(labels), pii, score


def parse_date(value):
    from datetime import datetime
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def phase_content(session, args) -> None:
    session.run("CREATE INDEX folder_path IF NOT EXISTS FOR (f:Folder) ON (f.path)").consume()
    where = "AND e.mailbox_owner = $mailbox" if args.mailbox else ""
    after, done, t0 = "", 0, time.time()
    stats: Counter = Counter()
    examples: dict[str, str] = {}
    while True:
        batch = session.run(f"""
            MATCH (e:Email) WHERE e.emailId > $after {where}
            RETURN e.emailId AS id, coalesce(e.subject, '') AS subject, left(coalesce(e.body, ''), 20000) AS body,
                   coalesce(e.source_folders, '') AS folders, e.sent_at AS sent_at,
                   COUNT {{ (e)-[:SENT_TO|CC_TO]->(:Person) }} AS recipients
            ORDER BY e.emailId LIMIT 5000""", after=after, mailbox=args.mailbox).data()
        if not batch:
            break
        rows = []
        for r in batch:
            folders = [f for f in r["folders"].split(";") if f]
            labels, pii, score = classify(r["subject"], r["body"], folders)
            stats.update(labels)
            stats.update(f"pii:{p}" for p in pii)
            for label in labels:
                examples.setdefault(label, r["subject"][:70])
            subject = r["subject"].strip().lower()
            rows.append({
                "id": r["id"], "labels": labels, "pii": pii, "score": score,
                "is_reply": subject.startswith("re:"), "is_forward": subject.startswith(("fw:", "fwd:")),
                "recipients": r["recipients"], "sent_on": parse_date(r["sent_at"]),
                "folders": [{"path": f, "mailbox": f.split("/")[0],
                             "name": f.split("/", 1)[-1].replace("___", "/")} for f in folders],
            })
        if not args.dry_run:
            write(session, """
                UNWIND $rows AS r MATCH (e:Email {emailId: r.id})
                SET e.sensitivity = r.labels, e.pii = r.pii, e.sensitivity_score = r.score,
                    e.is_reply = r.is_reply, e.is_forward = r.is_forward,
                    e.recipient_count = r.recipients, e.sent_on = r.sent_on
                WITH e, r UNWIND r.folders AS f
                MERGE (fo:Folder {path: f.path}) ON CREATE SET fo.mailbox = f.mailbox, fo.name = f.name
                MERGE (e)-[:IN_FOLDER]->(fo)""", rows, batch=1000)
        done += len(batch)
        after = batch[-1]["id"]
        print(f"  content: {done} emails ({time.time() - t0:.0f}s)", flush=True)
    print(f"content: {done} emails; label counts: {dict(stats.most_common())}")
    for label, subject in examples.items():
        print(f"  e.g. {label}: {subject!r}")


# ── roles: job titles of the 150 core employees ──────────────────────────

TITLES_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "data", "enron_custodian_titles.csv")
SENIORITY = {"CEO": 1.0, "President": 1.0, "Managing Director": 0.85, "Vice President": 0.8,
             "In House Lawyer": 0.8, "Director": 0.6, "Manager": 0.5, "Trader": 0.4, "Employee": 0.3}


# The source's rank column is coarse (Sally Beck: rank "Employee", position "Chief Operating
# Officer"), so the position text can raise seniority too.
POSITION_SENIORITY = [(r"\bchief\b|\bpresident\b|\bceo\b|\bcoo\b|\bcfo\b", 0.9), (r"vice president|\bvp\b", 0.8),
                      (r"lawyer|counsel|attorney", 0.8), (r"director", 0.6), (r"\bhead\b|manager", 0.5)]


def seniority(title: str, position: str) -> float | None:
    found = [SENIORITY[title]] if title in SENIORITY else []
    found += [w for rx, w in POSITION_SENIORITY if re.search(rx, position or "", re.I)]
    return max(found) if found else None


def phase_roles(session, args) -> None:
    import csv
    with open(TITLES_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(line for line in f if not line.startswith("#")))
    data = [{"mailbox": r["mailbox"], "title": r["title"] or None, "position": r["position"] or None,
             "seniority": seniority(r["title"], r["position"])} for r in rows]
    matched = session.run("""
        UNWIND $rows AS r MATCH (p:Person {mailbox: r.mailbox})
        SET p.title = r.title, p.position = r.position, p.seniority = r.seniority
        RETURN count(p) AS n""", rows=data).single()["n"]
    print(f"roles: {matched} of {len(data)} titled employees matched to a Person (via mailbox)")


# ── themes: real topics from the email embeddings ─────────────────────────

THEME_STOPWORDS = ["re", "fw", "fwd", "enron", "ect", "hou", "cc", "pm", "am", "com", "message", "original",
                   "forwarded", "subject", "thanks", "hi", "update", "new", "meeting", "need", "question"]


def name_themes(themes: list[dict]) -> None:
    """One LLM call names every cluster; falls back to its top keywords."""
    import json
    import httpx
    for t in themes:
        t["name"] = " / ".join(t["keywords"][:3])
    if not settings.AGENT_API_KEY:
        return
    listing = "\n".join(f'{t["id"]}: keywords={t["keywords"]}; subjects={t["samples"]}' for t in themes)
    prompt = ("Name each cluster of Enron emails with a short business theme (2-4 words, Title Case). "
              'Reply with JSON only: {"<id>": "<name>", ...}.\n\n' + listing)
    try:
        r = httpx.post(f"{settings.AGENT_BASE_URL.rstrip('/')}/chat/completions", timeout=180,
                       headers={"Authorization": f"Bearer {settings.AGENT_API_KEY}"},
                       json={"model": settings.AGENT_MODEL, "messages": [{"role": "user", "content": prompt}],
                             "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}})
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        names = json.loads(text[text.find("{"):text.rfind("}") + 1])
        for t in themes:
            if isinstance(names.get(str(t["id"])), str) and names[str(t["id"])].strip():
                t["name"] = names[str(t["id"])].strip()[:60]
    except Exception as e:
        print(f"themes: LLM naming failed ({e}); using keywords")


def phase_themes(session, args) -> None:
    import numpy as np
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

    ids, subjects, vectors, after, t0 = [], [], [], "", time.time()
    while True:
        batch = session.run("""
            MATCH (e:Email) WHERE e.emailId > $after AND e.embedding IS NOT NULL
            RETURN e.emailId AS id, coalesce(e.subject, '') AS subject, e.embedding AS v
            ORDER BY e.emailId LIMIT 10000""", after=after).data()
        if not batch:
            break
        ids += [r["id"] for r in batch]
        subjects += [r["subject"] for r in batch]
        vectors.append(np.asarray([r["v"] for r in batch], dtype=np.float32))
        after = batch[-1]["id"]
        print(f"  themes: loaded {len(ids)} embeddings ({time.time() - t0:.0f}s)", flush=True)
    X = np.vstack(vectors)
    X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9

    k = args.themes
    km = MiniBatchKMeans(n_clusters=k, random_state=0, batch_size=4096, n_init=3).fit(X)
    labels = km.labels_
    clean = [re.sub(r"^\s*((re|fw|fwd)\s*:\s*)+", "", s, flags=re.I) for s in subjects]
    tfidf = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS.union(THEME_STOPWORDS)),
                            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]{2,}\b", max_features=20000, min_df=5)
    T = tfidf.fit_transform(clean)
    vocab = np.array(tfidf.get_feature_names_out())
    themes = []
    for c in range(k):
        members = np.where(labels == c)[0]
        top = np.asarray(T[members].mean(axis=0)).ravel().argsort()[::-1][:8]
        samples = [clean[i][:60] for i in members[:400:80] if clean[i].strip()][:4]
        themes.append({"id": c, "size": int(len(members)), "keywords": vocab[top].tolist(), "samples": samples})
    name_themes(themes)
    for t in sorted(themes, key=lambda t: -t["size"]):
        print(f"  theme {t['id']:>2} {t['size']:>6}  {t['name']!r:40} {t['keywords'][:5]}")
    if args.dry_run:
        return

    session.run("CREATE INDEX theme_id IF NOT EXISTS FOR (t:Theme) ON (t.themeId)").consume()
    session.run("MATCH (t:Theme) DETACH DELETE t").consume()  # re-runs replace the previous clustering
    write(session, """
        UNWIND $rows AS r CREATE (:Theme {themeId: r.id, name: r.name, keywords: r.keywords, size: r.size})""",
          [{"id": t["id"], "name": t["name"], "keywords": t["keywords"], "size": t["size"]} for t in themes])
    write(session, """
        UNWIND $rows AS r MATCH (e:Email {emailId: r.e}) MATCH (t:Theme {themeId: r.t})
        MERGE (e)-[:ABOUT]->(t)""", [{"e": i, "t": int(c)} for i, c in zip(ids, labels)], batch=5000)
    print(f"themes: {k} themes written, {len(ids)} emails linked ({time.time() - t0:.0f}s)")


PHASES = {"indexes": phase_indexes, "names": phase_names, "activity": phase_activity, "content": phase_content,
          "roles": phase_roles, "themes": phase_themes}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phases", nargs="+", choices=list(PHASES))
    ap.add_argument("--mailbox", help="names phase: read only this mailbox (for a test run)")
    ap.add_argument("--dry-run", action="store_true", help="print what would be written, write nothing")
    ap.add_argument("--themes", type=int, default=40, help="themes phase: number of clusters")
    args = ap.parse_args()
    with driver() as d, d.session(database=settings.NEO4J_DATABASE) as s:
        for phase in args.phases:
            PHASES[phase](s, args)
