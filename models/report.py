from datetime import datetime
from models import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    whatsapp_number = db.Column(db.String(20), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    district = db.Column(db.String(20), nullable=False)
    village_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending / reviewed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    village = db.relationship("Location", backref="reports")

    def __repr__(self):
        return f"<Report {self.id} by {self.name}>"