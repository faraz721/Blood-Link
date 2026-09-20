from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, DonorProfile, Location
from services.phone_service import validate_phone
from config.settings import Config

donor_bp = Blueprint("donor", __name__, url_prefix="/donor")


def donor_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, "role", None) != "donor":
            flash("Please log in as a donor.", "warning")
            return redirect(url_for("auth.login"))
        if current_user.is_suspended:
            flash("Your account is suspended.", "danger")
            return redirect(url_for("auth.logout"))
        return f(*args, **kwargs)
    return decorated


@donor_bp.route("/dashboard")
@login_required
@donor_required
def dashboard():
    profile = current_user.profile
    return render_template("donor/dashboard.html", profile=profile)


@donor_bp.route("/profile", methods=["GET", "POST"])
@login_required
@donor_required
def profile():
    profile = current_user.profile
    villages = Location.query.filter_by(is_active=True).order_by(Location.village_name).all()
    districts = Config.DISTRICTS
    blood_groups = Config.BLOOD_GROUPS

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        phone_raw = (request.form.get("phone") or "").strip()
        blood_group = request.form.get("blood_group") or profile.blood_group
        district = request.form.get("district") or profile.district
        village_id = request.form.get("village_id") or ""
        whatsapp_same = request.form.get("whatsapp_same") == "on"
        whatsapp_raw = (request.form.get("whatsapp_number") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        is_available = request.form.get("is_available") == "on"

        errors = []

        if not full_name or len(full_name) < 3:
            errors.append("Full name is required.")

        ok, phone_or_err = validate_phone(phone_raw)
        if not ok:
            errors.append(phone_or_err)
        else:
            phone = phone_or_err
            existing = User.query.filter(User.phone == phone, User.id != current_user.id).first()
            if existing:
                errors.append("This phone number is already used by another account.")

        if blood_group not in blood_groups:
            errors.append("Invalid blood group.")
        if district not in districts:
            errors.append("Invalid district.")
        try:
            village_id = int(village_id)
            village = Location.query.get(village_id)
            if not village or village.district != district:
                errors.append("Please select a valid village for the district.")
        except (ValueError, TypeError):
            errors.append("Village is required.")

        if whatsapp_same:
            whatsapp = phone if ok else None
        else:
            if whatsapp_raw:
                ok_w, w = validate_phone(whatsapp_raw)
                if not ok_w:
                    errors.append("WhatsApp: " + w)
                else:
                    whatsapp = w
            else:
                whatsapp = None

        if password:
            if len(password) < 8:
                errors.append("New password must be at least 8 characters.")
            if password != confirm:
                errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "donor/profile.html",
                profile=profile,
                villages=villages,
                districts=districts,
                blood_groups=blood_groups,
            )

        # Apply updates
        current_user.phone = phone
        if password:
            current_user.set_password(password)

        profile.full_name = full_name
        profile.blood_group = blood_group
        profile.district = district
        profile.village_id = village_id
        profile.whatsapp_number = whatsapp
        profile.is_available = is_available

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("donor.profile"))

    return render_template(
        "donor/profile.html",
        profile=profile,
        villages=villages,
        districts=districts,
        blood_groups=blood_groups,
    )


@donor_bp.route("/availability", methods=["POST"])
@login_required
@donor_required
def toggle_availability():
    profile = current_user.profile
    profile.is_available = not profile.is_available
    db.session.commit()
    status = "Available" if profile.is_available else "Unavailable"
    flash(f"You are now marked as {status}.", "success")
    return redirect(url_for("donor.dashboard"))