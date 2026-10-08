import os
import re
import hashlib
import sys
import asyncio
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, getaddresses
import spacy

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.postgres import engine, AsyncSessionLocal
from app.db.enron_models import Base, Person, Email, EmailRecipient, Topic, email_topic_association
from sqlalchemy.dialects.postgresql import insert as pg_insert


def clean_address(addr: str) -> str:
    """Strip stray quote/punctuation characters a few malformed Enron headers
    leave on the parsed address, e.g. "'richard.sanders@enron.com"."""
    return re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", addr.strip().lower()) if addr else addr

class PostgresPipeline:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm", disable=["tagger", "parser", "attribute_ruler", "lemmatizer"])

    def get_fingerprint(self, sender, recipients, subject, body):
        sender = (sender or "").strip().lower()
        recipients = sorted([r.strip().lower() for r in (recipients or []) if r.strip()])
        subject = (subject or "").strip()
        body = (body or "").strip()
        fingerprint_data = f"{sender}|{','.join(recipients)}|{subject}|{body}"
        return f"enron_{hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()[:16]}"

    def strip_quoted_text(self, text):
        markers = [
            r"-----Original Message-----",
            r"___+ Forwarded by",
            r"From: .+\nSent:",
            r"On .+ wrote:"
        ]
        pattern = re.compile("|".join(markers), re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return text[:match.start()].strip()
        return text.strip()

    def parse_email(self, filepath):
        with open(filepath, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)
            
        message_id = msg.get('Message-ID', '').strip()
        
        sender_hdr = msg.get('From', '')
        sender_name, sender_email = parseaddr(sender_hdr)
        sender_email = clean_address(sender_email)

        to_hdr = msg.get('To', '')
        cc_hdr = msg.get('Cc', '')
        bcc_hdr = msg.get('Bcc', '')

        recipients = {'to': [], 'cc': [], 'bcc': []}
        if to_hdr:
            recipients['to'] = [{'name': name, 'email': clean_address(email)} for name, email in getaddresses([to_hdr]) if email.strip()]
        if cc_hdr:
            recipients['cc'] = [{'name': name, 'email': clean_address(email)} for name, email in getaddresses([cc_hdr]) if email.strip()]
        if bcc_hdr:
            recipients['bcc'] = [{'name': name, 'email': clean_address(email)} for name, email in getaddresses([bcc_hdr]) if email.strip()]
                
        subject = msg.get('Subject', '')
        date_str = msg.get('Date', '')
        
        body = msg.get_body(preferencelist=('plain'))
        body_text = body.get_content() if body else ""
        body_text = self.strip_quoted_text(body_text)
        
        flat_recips = [r['email'] for r in recipients['to'] + recipients['cc'] + recipients['bcc']]
        canonical_id = f"enron_{hashlib.sha256(message_id.encode('utf-8')).hexdigest()[:16]}" if message_id else self.get_fingerprint(sender_email, flat_recips, subject, body_text)
        
        return {
            'email_id': canonical_id,
            'message_id': message_id,
            'sender': {'name': sender_name, 'email': sender_email},
            'recipients': recipients,
            'subject': subject,
            'sent_at': date_str,
            'body': body_text,
            'filepath': filepath
        }

    def extract_topics(self, text):
        doc = self.nlp(text[:5000])
        topics = set()
        for ent in doc.ents:
            if ent.label_ in ['ORG', 'LOC', 'PRODUCT', 'EVENT', 'WORK_OF_ART']:
                name = re.sub(r'\s+', ' ', ent.text.strip().strip("'\"`.,:;()[]{}*&#@!?-/\\"))
                if name and len(name) > 2:
                    topics.add(name.title())
        return list(topics)

    def normalize_subject(self, subject):
        return re.sub(r'(?i)^(re:|fw:|fwd:)\s*', '', subject).strip()

    async def init_db(self):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def write_batch_to_postgres(self, batch, subject_to_email_id) -> int:
        """Bulk upsert in strict dependency order (persons -> topics -> emails ->
        recipients/email_topic), using INSERT ... ON CONFLICT DO NOTHING throughout.

        The original version used session.get()-then-add() "upsert" per row with a
        single flush/commit at the end of the batch. With autoflush disabled
        (app/db/postgres.py), that let an Email INSERT reach the database before its
        sender's Person row did whenever the same sender appeared twice in one batch
        (the common case — a mailbox owner emailing themselves many times) producing a
        foreign-key error that rolled back the WHOLE 500-email batch, silently, while
        the caller's progress counter kept counting as if it had succeeded.
        """
        persons: dict[str, str | None] = {}
        for email_data in batch:
            sender_email = email_data['sender']['email']
            if sender_email:
                persons.setdefault(sender_email, email_data['sender']['name'] or None)
            for recips in email_data['recipients'].values():
                for rec in recips:
                    if rec['email']:
                        persons.setdefault(rec['email'], rec['name'] or None)

        topics_by_email: dict[str, list[str]] = {
            e['email_id']: self.extract_topics(e['body']) for e in batch
        }
        all_topics = {t for topics in topics_by_email.values() for t in topics}

        async with AsyncSessionLocal() as session:
            try:
                if persons:
                    await session.execute(
                        pg_insert(Person)
                        .values([{"email": e, "name": n} for e, n in persons.items()])
                        .on_conflict_do_nothing(index_elements=["email"])
                    )
                if all_topics:
                    await session.execute(
                        pg_insert(Topic)
                        .values([{"name": t} for t in all_topics])
                        .on_conflict_do_nothing(index_elements=["name"])
                    )

                email_rows = []
                for email_data in batch:
                    norm_subj = self.normalize_subject(email_data['subject'])
                    is_reply = bool(re.match(r'(?i)^(re:)\s*', email_data['subject']))
                    reply_to_id = subject_to_email_id.get(norm_subj) if is_reply else None
                    email_rows.append({
                        "email_id": email_data['email_id'],
                        "message_id": email_data['message_id'],
                        "subject": email_data['subject'],
                        "sent_at": email_data['sent_at'],
                        "body": email_data['body'],
                        "source_path": email_data['filepath'],
                        "sender_email": email_data['sender']['email'] or None,
                        "reply_to_id": reply_to_id,
                    })
                    if norm_subj:
                        subject_to_email_id[norm_subj] = email_data['email_id']
                if email_rows:
                    await session.execute(
                        pg_insert(Email).values(email_rows).on_conflict_do_nothing(index_elements=["email_id"])
                    )

                recipient_rows = [
                    {"email_id": e['email_id'], "person_email": rec['email'], "recipient_type": r_type}
                    for e in batch
                    for r_type, recips in e['recipients'].items()
                    for rec in recips if rec['email']
                ]
                if recipient_rows:
                    await session.execute(EmailRecipient.__table__.insert(), recipient_rows)

                topic_rows = [
                    {"email_id": email_id, "topic_name": t}
                    for email_id, topics in topics_by_email.items() for t in topics
                ]
                if topic_rows:
                    await session.execute(
                        pg_insert(email_topic_association).values(topic_rows).on_conflict_do_nothing()
                    )

                await session.commit()
                return len(batch)
            except Exception as e:
                await session.rollback()
                print(f"Batch insert failed: {e}")
                return 0

    async def ingest_emails(self, base_maildir_path):
        await self.init_db()
        
        target_mailboxes = [
            "sanders-r", "haedicke-m", "derrick-j", "kitchen-l", 
            "lavorato-j", "skilling-j", "lay-k", "kaminski-v", "kean-s"
        ]
        
        print(f"Starting Ingestion to PostgreSQL for {len(target_mailboxes)} mailboxes.", flush=True)
        selected_filepaths = []
        for mbx in target_mailboxes:
            mbx_path = os.path.join(base_maildir_path, mbx)
            if not os.path.exists(mbx_path):
                continue
            for root, _, files in os.walk(mbx_path):
                for file in files:
                    filepath = os.path.abspath(os.path.join(root, file))
                    if file.endswith('.') and not filepath.endswith('.'):
                        filepath += '.'
                    if os.name == 'nt' and not filepath.startswith('\\\\?\\'):
                        filepath = '\\\\?\\' + filepath
                    selected_filepaths.append(filepath)

        print(f"Total files: {len(selected_filepaths)}", flush=True)
        
        subject_to_email_id = {}
        batch = []
        batch_size = 500
        emails_ingested = 0
        seen_ids = set()
        
        for idx, filepath in enumerate(selected_filepaths):
            if idx > 0 and idx % 2000 == 0:
                print(f"Processed {idx}/{len(selected_filepaths)} files. Ingested: {emails_ingested}", flush=True)
                
            try:
                parsed = self.parse_email(filepath)
            except Exception:
                continue
                
            if parsed['email_id'] in seen_ids:
                continue
            seen_ids.add(parsed['email_id'])
            batch.append(parsed)
            
            if len(batch) >= batch_size:
                emails_ingested += await self.write_batch_to_postgres(batch, subject_to_email_id)
                batch = []

        if batch:
            emails_ingested += await self.write_batch_to_postgres(batch, subject_to_email_id)

        print(f"Ingestion complete. Total committed: {emails_ingested}", flush=True)

if __name__ == '__main__':
    pipeline = PostgresPipeline()
    asyncio.run(pipeline.ingest_emails(r"C:\Major Project\Project\data\raw\enron_mail_20150507\maildir"))
