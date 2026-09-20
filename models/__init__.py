from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

from models.user import User
from models.donor import DonorProfile
from models.location import Location
from models.report import Report
from models.admin import AdminUser
from models.login_attempt import LoginAttempt

__all__ = [
    "db",
    "login_manager",
    "User",
    "DonorProfile",
    "Location",
    "Report",
    "AdminUser",
    "LoginAttempt",
]