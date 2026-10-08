from sqlalchemy import Column, String, Text, ForeignKey, Table, Integer
from sqlalchemy.orm import relationship
from app.db.postgres import Base

email_topic_association = Table(
    'email_topic', Base.metadata,
    Column('email_id', String, ForeignKey('emails.email_id'), primary_key=True),
    Column('topic_name', String, ForeignKey('topics.name'), primary_key=True)
)

class Person(Base):
    __tablename__ = 'persons'
    email = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)

class Email(Base):
    __tablename__ = 'emails'
    email_id = Column(String, primary_key=True, index=True)
    message_id = Column(String, index=True, nullable=True)
    subject = Column(String, nullable=True)
    sent_at = Column(String, nullable=True) 
    body = Column(Text, nullable=True)
    source_path = Column(String, nullable=True)
    
    sender_email = Column(String, ForeignKey('persons.email'), nullable=True, index=True)
    reply_to_id = Column(String, ForeignKey('emails.email_id'), nullable=True)

class EmailRecipient(Base):
    __tablename__ = 'email_recipients'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String, ForeignKey('emails.email_id'), index=True)
    person_email = Column(String, ForeignKey('persons.email'), index=True)
    recipient_type = Column(String) # to, cc, bcc

class Topic(Base):
    __tablename__ = 'topics'
    name = Column(String, primary_key=True, index=True)
