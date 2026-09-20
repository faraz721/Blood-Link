from models import db


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    district = db.Column(db.String(20), nullable=False, index=True)
    village_name = db.Column(db.String(150), nullable=False)
    source = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("district", "village_name", name="uq_district_village"),
    )

    def __repr__(self):
        return f"<Location {self.district} / {self.village_name}>"