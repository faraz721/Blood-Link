from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import logout_user, current_user
from models import db, User, DonorProfile, Location, Report, AdminUser
from services.auth_service import authenticate_admin
from config.settings import Config

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please log in as admin.", "warning")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        admin, error = authenticate_admin(username, password)
        if error:
            flash(error, "danger")
            return render_template("admin/login.html")

        # Clear donor session if any (prevent mixed sessions)
        if current_user.is_authenticated:
            logout_user()

        session["admin_id"] = admin.id
        session["admin_username"] = admin.username
        flash("Admin logged in.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("index"))


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    total = DonorProfile.query.count()
    talagang = DonorProfile.query.filter_by(district="Talagang").count()
    chakwal = DonorProfile.query.filter_by(district="Chakwal").count()

    available = (
        db.session.query(DonorProfile)
        .join(User)
        .filter(User.is_suspended.is_(False), DonorProfile.is_available.is_(True))
        .count()
    )
    unavailable = (
        db.session.query(DonorProfile)
        .join(User)
        .filter(User.is_suspended.is_(False), DonorProfile.is_available.is_(False))
        .count()
    )
    suspended = User.query.filter_by(role="donor", is_suspended=True).count()

    def district_stats(dist):
        t = DonorProfile.query.filter_by(district=dist).count()
        a = (
            db.session.query(DonorProfile)
            .join(User)
            .filter(
                DonorProfile.district == dist,
                User.is_suspended.is_(False),
                DonorProfile.is_available.is_(True),
            )
            .count()
        )
        u = (
            db.session.query(DonorProfile)
            .join(User)
            .filter(
                DonorProfile.district == dist,
                User.is_suspended.is_(False),
                DonorProfile.is_available.is_(False),
            )
            .count()
        )
        s = (
            db.session.query(User)
            .join(DonorProfile)
            .filter(DonorProfile.district == dist, User.is_suspended.is_(True))
            .count()
        )

        # Blood-group-wise counts for this district (always show all groups)
        bg_counts = {bg: 0 for bg in Config.BLOOD_GROUPS}
        rows = (
            db.session.query(DonorProfile.blood_group, db.func.count(DonorProfile.id))
            .filter(DonorProfile.district == dist)
            .group_by(DonorProfile.blood_group)
            .all()
        )
        for bg, cnt in rows:
            if bg in bg_counts:
                bg_counts[bg] = cnt
        blood_groups = [(bg, bg_counts[bg]) for bg in Config.BLOOD_GROUPS]

        return {
            "total": t,
            "available": a,
            "unavailable": u,
            "suspended": s,
            "blood_groups": blood_groups,
        }

    # Overall blood group counts (kept for summary row)
    bg_counts = {bg: 0 for bg in Config.BLOOD_GROUPS}
    rows = (
        db.session.query(DonorProfile.blood_group, db.func.count(DonorProfile.id))
        .group_by(DonorProfile.blood_group)
        .all()
    )
    for bg, cnt in rows:
        if bg in bg_counts:
            bg_counts[bg] = cnt
    blood_group_stats = [(bg, bg_counts[bg]) for bg in Config.BLOOD_GROUPS]

    return render_template(
        "admin/dashboard.html",
        total=total,
        talagang=talagang,
        chakwal=chakwal,
        available=available,
        unavailable=unavailable,
        suspended=suspended,
        talagang_stats=district_stats("Talagang"),
        chakwal_stats=district_stats("Chakwal"),
        blood_group_stats=blood_group_stats,
    )


@admin_bp.route("/donors")
@admin_required
def donors():
    blood_group = request.args.get("blood_group", "")
    district = request.args.get("district", "")
    village_id = request.args.get("village_id", "")
    availability = request.args.get("availability", "")
    suspension = request.args.get("suspension", "")
    q = request.args.get("q", "").strip()

    query = (
        db.session.query(DonorProfile, User, Location)
        .join(User, DonorProfile.user_id == User.id)
        .join(Location, DonorProfile.village_id == Location.id)
    )

    if blood_group in Config.BLOOD_GROUPS:
        query = query.filter(DonorProfile.blood_group == blood_group)
    if district in Config.DISTRICTS:
        query = query.filter(DonorProfile.district == district)
    if village_id:
        try:
            query = query.filter(DonorProfile.village_id == int(village_id))
        except ValueError:
            pass
    if availability == "available":
        query = query.filter(DonorProfile.is_available.is_(True), User.is_suspended.is_(False))
    elif availability == "unavailable":
        query = query.filter(DonorProfile.is_available.is_(False), User.is_suspended.is_(False))
    if suspension == "suspended":
        query = query.filter(User.is_suspended.is_(True))
    elif suspension == "active":
        query = query.filter(User.is_suspended.is_(False))
    if q:
        query = query.filter(
            db.or_(
                DonorProfile.full_name.ilike(f"%{q}%"),
                User.phone.ilike(f"%{q}%"),
            )
        )

    results = query.order_by(DonorProfile.created_at.desc()).limit(200).all()
    villages = Location.query.filter_by(is_active=True).order_by(Location.village_name).all()

    return render_template(
        "admin/donors.html",
        results=results,
        blood_groups=Config.BLOOD_GROUPS,
        districts=Config.DISTRICTS,
        villages=villages,
        filters=request.args,
    )


@admin_bp.route("/donors/<int:user_id>/suspend", methods=["POST"])
@admin_required
def suspend_donor(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != "donor":
        flash("Invalid donor.", "danger")
        return redirect(url_for("admin.donors"))
    user.is_suspended = True
    db.session.commit()
    flash("Donor suspended.", "success")
    return redirect(url_for("admin.donors"))


@admin_bp.route("/donors/<int:user_id>/unsuspend", methods=["POST"])
@admin_required
def unsuspend_donor(user_id):
    user = User.query.get_or_404(user_id)
    user.is_suspended = False
    db.session.commit()
    flash("Donor unsuspended.", "success")
    return redirect(url_for("admin.donors"))


@admin_bp.route("/donors/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_donor(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != "donor":
        flash("Invalid donor.", "danger")
        return redirect(url_for("admin.donors"))
    db.session.delete(user)
    db.session.commit()
    flash("Donor deleted.", "success")
    return redirect(url_for("admin.donors"))


@admin_bp.route("/reports")
@admin_required
def reports():
    status = request.args.get("status", "")
    q = Report.query
    if status in ("pending", "reviewed"):
        q = q.filter_by(status=status)
    reports_list = q.order_by(Report.created_at.desc()).limit(100).all()
    return render_template("admin/reports.html", reports=reports_list)


@admin_bp.route("/reports/<int:report_id>/reviewed", methods=["POST"])
@admin_required
def mark_reviewed(report_id):
    r = Report.query.get_or_404(report_id)
    r.status = "reviewed"
    db.session.commit()
    flash("Report marked as reviewed.", "success")
    return redirect(url_for("admin.reports"))


@admin_bp.route("/reports/<int:report_id>/delete", methods=["POST"])
@admin_required
def delete_report(report_id):
    r = Report.query.get_or_404(report_id)
    db.session.delete(r)
    db.session.commit()
    flash("Report deleted.", "success")
    return redirect(url_for("admin.reports"))
