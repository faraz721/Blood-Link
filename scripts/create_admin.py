"""
Create or update admin user from environment variables.
Run: python scripts/create_admin.py
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db, AdminUser

app = create_app()

with app.app_context():
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")

    admin = AdminUser.query.filter_by(username=username).first()
    if admin:
        admin.set_password(password)
        print(f"Updated password for existing admin: {username}")
    else:
        admin = AdminUser(username=username)
        admin.set_password(password)
        db.session.add(admin)
        print(f"Created admin: {username}")
    db.session.commit()
    print("Done. Login at /admin/login")