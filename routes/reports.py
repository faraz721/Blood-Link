from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Report, Location
from services.phone_service import validate_phone
from config.settings import Config

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/report", methods=["GET", "POST"])
def report():
    villages = Location.query.filter_by(is_active=True).order_by(Location.village_name).all()
    districts = Config.DISTRICTS

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        whatsapp_raw = (request.form.get("whatsapp_number") or "").strip()
        phone_raw = (request.form.get("phone_number") or "").strip()
        district = request.form.get("district") or ""
        village_id = request.form.get("village_id") or ""
        message = (request.form.get("message") or "").strip()

        errors = []
        if not name or len(name) < 2:
            errors.append("Full name is required.")
        ok_w, whatsapp_or_err = validate_phone(whatsapp_raw)
        if not ok_w:
            errors.append("WhatsApp: " + whatsapp_or_err)
        else:
            whatsapp = whatsapp_or_err
        ok_p, phone_or_err = validate_phone(phone_raw)
        if not ok_p:
            errors.append("Phone: " + phone_or_err)
        else:
            phone = phone_or_err
        if district not in districts:
            errors.append("Please select a valid district.")
        try:
            village_id = int(village_id) if village_id else None
            if village_id:
                v = Location.query.get(village_id)
                if not v or v.district != district:
                    errors.append("Please select a valid village for the district.")
        except (ValueError, TypeError):
            village_id = None
        if not message or len(message) < 10:
            errors.append("Please describe the problem (at least 10 characters).")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "report.html",
                villages=villages,
                districts=districts,
                form=request.form,
            )

        r = Report(
            name=name,
            whatsapp_number=whatsapp,
            phone_number=phone,
            district=district,
            village_id=village_id,
            message=message,
            status="pending",
        )
        db.session.add(r)
        db.session.commit()
        flash("Your report has been submitted successfully.", "success")
        return redirect(url_for("reports.report"))

    return render_template("report.html", villages=villages, districts=districts, form={})