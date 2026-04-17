from .extensions import db, bcrypt
from datetime import datetime
import uuid

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    documents = db.relationship("Document", backref="user", lazy=True)
    chats = db.relationship("Chat", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(512))
    file_size = db.Column(db.Integer)
    status = db.Column(db.String(50), default="pending")
    ocr_text = db.Column(db.Text)
    citation_graph = db.Column(db.JSON)
    internal_analysis = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    citations = db.relationship("Citation", backref="document", lazy=True, cascade="all, delete-orphan")

class Citation(db.Model):
    __tablename__ = "citations"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = db.Column(db.String(36), db.ForeignKey("documents.id"), nullable=False)
    cited_case = db.Column(db.String(512))
    citation_text = db.Column(db.Text)
    relevance_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Chat(db.Model):
    __tablename__ = "chats"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship("Message", backref="chat", lazy=True, cascade="all, delete-orphan")

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = db.Column(db.String(36), db.ForeignKey("chats.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
