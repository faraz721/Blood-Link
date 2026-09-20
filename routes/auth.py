from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, DonorProfile, Location
from services.phone_service import validate_phone, normalize_phone
from services.auth_service import authenticate_donor
from config.settings import Config

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/become-donor")
def become_donor():
    if current_user.is_authenticated and getattr(current_user, "role", None) == "donor":
        return redirect(url_for("donor.dashboard"))
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    return render_template("become_donor.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated and getattr(current_user, "role", None) == "donor":
        return redirect(url_for("donor.dashboard"))
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))

    villages = Location.query.filter_by(is_active=True).order_by(Location.village_name).all()
    districts = Config.DISTRICTS
    blood_groups = Config.BLOOD_GROUPS

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        phone_raw = (request.form.get("phone") or "").strip()
        blood_group = request.form.get("blood_group") or ""
        district = request.form.get("district") or ""
        village_id = request.form.get("village_id") or ""
        whatsapp_same = request.form.get("whatsapp_same") == "on"
        whatsapp_raw = (request.form.get("whatsapp_number") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        errors = []

        if not full_name or len(full_name) < 3:
            errors.append("Full name is required (min 3 characters).")
        ok, phone_or_err = validate_phone(phone_raw)
        if not ok:
            errors.append(phone_or_err)
        else:
            phone = phone_or_err
            if User.query.filter_by(phone=phone).first():
                errors.append("This phone number is already registered.")

        if blood_group not in blood_groups:
            errors.append("Please select a valid blood group.")
        if district not in districts:
            errors.append("Please select a valid district (Talagang or Chakwal only).")
        try:
            village_id = int(village_id)
            village = Location.query.get(village_id)
            if not village or village.district != district:
                errors.append("Please select a valid village for the chosen district.")
        except (ValueError, TypeError):
            errors.append("Village / Area is required.")

        if whatsapp_same:
            whatsapp = phone if ok else None
        else:
            if whatsapp_raw:
                ok_w, whatsapp_or_err = validate_phone(whatsapp_raw)
                if not ok_w:
                    errors.append("WhatsApp: " + whatsapp_or_err)
                else:
                    whatsapp = whatsapp_or_err
            else:
                whatsapp = None

        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "register.html",
                villages=villages,
                districts=districts,
                blood_groups=blood_groups,
                form=request.form,
            )

        # Clear admin session if any
        session.pop("admin_id", None)
        session.pop("admin_username", None)

        user = User(phone=phone, role="donor")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        profile = DonorProfile(
            user_id=user.id,
            full_name=full_name,
            blood_group=blood_group,
            district=district,
            village_id=village_id,
            whatsapp_number=whatsapp,
            is_available=True,
        )
        db.session.add(profile)
        db.session.commit()

        login_user(user, remember=True)
        flash("Registration successful! Welcome to BloodLink.", "success")
        return redirect(url_for("donor.dashboard"))

    return render_template(
        "register.html",
        villages=villages,
        districts=districts,
        blood_groups=blood_groups,
        form={},
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and getattr(current_user, "role", None) == "donor":
        return redirect(url_for("donor.dashboard"))
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        user, error = authenticate_donor(phone, password)
        if error:
            flash(error, "danger")
            return render_template("login.html")

        # Clear admin session if any
        session.pop("admin_id", None)
        session.pop("admin_username", None)

        login_user(user, remember=True)
        flash("Logged in successfully.", "success")
        next_url = request.args.get("next") or url_for("donor.dashboard")
        return redirect(next_url)

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    # Also clear any leftover admin session
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))
