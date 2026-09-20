from flask import Blueprint, render_template, request, jsonify
from models import db, User, DonorProfile, Location
from config.settings import Config

search_bp = Blueprint("search", __name__)


@search_bp.route("/find-donor")
def find_donor():
    villages = Location.query.filter_by(is_active=True).order_by(Location.village_name).all()
    return render_template(
        "find_donor.html",
        blood_groups=Config.BLOOD_GROUPS,
        districts=Config.DISTRICTS,
        villages=villages,
    )


@search_bp.route("/api/locations")
def api_locations():
    district = request.args.get("district", "")
    q = Location.query.filter_by(is_active=True)
    if district in Config.DISTRICTS:
        q = q.filter_by(district=district)
    villages = q.order_by(Location.village_name).all()
    return jsonify([{"id": v.id, "name": v.village_name, "district": v.district} for v in villages])


@search_bp.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(silent=True) or {}
    blood_group = (data.get("blood_group") or "").strip()
    district = (data.get("district") or "").strip()
    village_id = data.get("village_id")
    mode = (data.get("mode") or "normal").strip()  # normal | all_districts | all_available | this_district | this_village

    if not blood_group or blood_group not in Config.BLOOD_GROUPS:
        return jsonify({"count": 0, "donors": [], "error": "Blood group is required."}), 400

    query = (
        db.session.query(DonorProfile, User, Location)
        .join(User, DonorProfile.user_id == User.id)
        .join(Location, DonorProfile.village_id == Location.id)
        .filter(
            User.is_active.is_(True),
            User.is_suspended.is_(False),
            DonorProfile.is_available.is_(True),
        )
    )

    if blood_group and blood_group in Config.BLOOD_GROUPS:
        query = query.filter(DonorProfile.blood_group == blood_group)

    if mode == "all_districts" or mode == "all_available":
        # Both districts, available only (already filtered)
        pass
    elif mode == "this_district" and district in Config.DISTRICTS:
        query = query.filter(DonorProfile.district == district)
    elif mode == "this_village" and village_id:
        try:
            vid = int(village_id)
            query = query.filter(DonorProfile.village_id == vid)
        except (ValueError, TypeError):
            pass
    else:
        # normal filters
        if district in Config.DISTRICTS:
            query = query.filter(DonorProfile.district == district)
        if village_id:
            try:
                vid = int(village_id)
                query = query.filter(DonorProfile.village_id == vid)
            except (ValueError, TypeError):
                pass

    results = query.order_by(DonorProfile.full_name).limit(100).all()

    donors = []
    for profile, user, loc in results:
        whatsapp = profile.whatsapp_number or user.phone
        donors.append({
            "name": profile.full_name,
            "blood_group": profile.blood_group,
            "district": profile.district,
            "village": loc.village_name,
            "availability": "Available" if profile.is_available else "Unavailable",
            "phone": user.phone,
            "whatsapp": whatsapp,
        })

    return jsonify({"count": len(donors), "donors": donors})