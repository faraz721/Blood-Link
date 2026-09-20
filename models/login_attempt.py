from datetime import datetime
from models import db


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(100), nullable=False, index=True)  # phone or IP
    attempt_type = db.Column(db.String(20), nullable=False)  # donor / admin
    failed_count = db.Column(db.Integer, default=0)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow)
    blocked_until = db.Column(db.DateTime, nullable=True, index=True)

    def __repr__(self):
        return f"<LoginAttempt {self.identifier}>"