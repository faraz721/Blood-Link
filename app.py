import os
from flask import Flask, render_template, redirect, url_for, session
from flask_login import current_user, logout_user
from config.settings import Config
from models import db, login_manager, User
from routes.auth import auth_bp
from routes.donor import donor_bp
from routes.search import search_bp
from routes.reports import reports_bp
from routes.ai import ai_bp
from routes.admin import admin_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Fix for Supabase / Heroku-style postgres:// URLs
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = uri.replace("postgres://", "postgresql://", 1)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(donor_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def index():
        # Logged-in users stay in their area until logout
        if session.get("admin_id"):
            return redirect(url_for("admin.dashboard"))
        if (
            current_user.is_authenticated
            and getattr(current_user, "role", None) == "donor"
        ):
            return redirect(url_for("donor.dashboard"))
        return render_template("index.html")
        
    @app.route("/health")
    def health():
        return "OK", 200
    
    @app.context_processor 
    def inject_globals():
        is_admin = bool(session.get("admin_id"))
        is_donor = (
            not is_admin
            and current_user.is_authenticated
            and getattr(current_user, "role", None) == "donor"
        )
        return {
            "current_user": current_user,
            "is_donor": is_donor,
            "is_admin": is_admin,
        }


    @app.route("/download/blood-donation-guide")
    def download_knowledge_pdf():
        from flask import send_from_directory
        kb_dir = os.path.join(app.root_path, "knowledge_base")
        return send_from_directory(
            kb_dir,
            "blood_donation_guide.pdf",
            as_attachment=True,
            download_name="BloodLink_Blood_Donation_Guide.pdf",
        )

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("404.html"), 403

    # Create tables on first run (simple; use migrations for production)
    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")