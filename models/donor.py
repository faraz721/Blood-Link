from datetime import datetime
from models import db


class DonorProfile(db.Model):
    __tablename__ = "donor_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False, index=True)
    district = db.Column(db.String(20), nullable=False, index=True)
    village_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False, index=True)
    whatsapp_number = db.Column(db.String(20), nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    village = db.relationship("Location", backref="donors")

    def __repr__(self):
        return f"<DonorProfile {self.full_name} ({self.blood_group})>"