import json
import os
from datetime import datetime
from urllib.parse import quote

try:
    import gspread
except ImportError:  # pragma: no cover - optional dependency for Google Sheets
    gspread = None

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
WHATSAPP_NUMBER = "916379376791"


def value(data, field, fallback):
    return str(data.get(field, "")).strip()[:1000] or fallback


def build_contact_row(data):
    submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return [
        submitted_at,
        value(data, "name", ""),
        value(data, "email", ""),
        value(data, "phone", "Not provided"),
        value(data, "clientType", ""),
        value(data, "category", ""),
        value(data, "budget", "Not decided"),
        value(data, "deadline", "Flexible"),
        value(data, "description", ""),
    ]


def get_google_sheet_client():
    if gspread is None:
        return None

    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        return None

    credentials_json = os.getenv("GOOGLE_SHEET_CREDENTIALS")
    credentials_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    candidate_paths = [
        credentials_path,
        os.path.join(app.root_path, "google-credentials.json"),
        os.path.join(app.root_path, "..", "google-credentials.json"),
        os.path.join(os.getcwd(), "google-credentials.json"),
    ]

    if credentials_json:
        try:
            parsed = json.loads(credentials_json)
            return gspread.service_account_from_dict(parsed).open_by_key(sheet_id)
        except json.JSONDecodeError:
            pass

    for path in candidate_paths:
        if not path or not os.path.exists(path):
            continue
        return gspread.service_account(filename=path).open_by_key(sheet_id)

    return None


def save_contact_to_google_sheet(data):
    try:
        sheet = get_google_sheet_client()
        if sheet is None:
            return False

        sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
        try:
            worksheet = sheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
            worksheet.append_row([
                "Submitted At",
                "Name",
                "Email",
                "WhatsApp",
                "Client Type",
                "Category",
                "Budget",
                "Deadline",
                "Project Details",
            ])

        worksheet.append_row(build_contact_row(data))
        return True
    except Exception:
        return False


@app.get("/")
def home():
    return send_from_directory(app.root_path, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "Desert Bloom Technologies API"})


@app.post("/api/contact")
def create_contact_message():
    data = request.get_json(silent=True) or {}
    required_fields = ("name", "email", "clientType", "category", "description")
    if any(not str(data.get(field, "")).strip() for field in required_fields):
        return jsonify({"error": "Please complete all required fields."}), 400

    message = "\n".join(
        (
            "Hello Desert Bloom Technologies,",
            "",
            "I'd like to discuss a project.",
            f"Name: {value(data, 'name', '')}",
            f"Email: {value(data, 'email', '')}",
            f"WhatsApp: {value(data, 'phone', 'Not provided')}",
            f"Client type: {value(data, 'clientType', '')}",
            f"Category: {value(data, 'category', '')}",
            f"Budget: {value(data, 'budget', 'Not decided')}",
            f"Deadline: {value(data, 'deadline', 'Flexible')}",
            f"Project details: {value(data, 'description', '')}",
        )
    )
    whatsapp_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(message, safe='')}"
    saved_to_sheet = save_contact_to_google_sheet(data)
    return jsonify({"whatsapp_url": whatsapp_url, "saved_to_sheet": saved_to_sheet})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
