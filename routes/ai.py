from flask import Blueprint, render_template, request, jsonify
from services.ai_service import ask_bloodlink_ai

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/ai-help")
def ai_help():
    return render_template("ai_help.html")


@ai_bp.route("/api/ai/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    answer, error = ask_bloodlink_ai(question)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, "answer": answer})