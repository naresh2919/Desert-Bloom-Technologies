
import os
import re
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gspread
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

logging.basicConfig(level=logging.INFO)

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "Enquiries").strip()
CREDENTIALS_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE", "secrets/google-service-account.json"
).strip()

credentials_path = Path(CREDENTIALS_FILE)
if not credentials_path.is_absolute():
    credentials_path = BASE_DIR / credentials_path

HEADERS = [
    "Submitted At (IST)",
    "Name",
    "Email",
    "Phone",
    "Client Type",
    "Category",
    "Budget",
    "Deadline",
    "Description",
]


def get_worksheet():
    if not SHEET_ID:
        raise RuntimeError("Google Sheets is not configured: set GOOGLE_SHEET_ID.")

    if not credentials_path.is_file():
        raise RuntimeError(
            "Google Sheets is not configured: service account credentials were not found."
        )

    client = gspread.service_account(
        filename=str(credentials_path)
    )
    spreadsheet = client.open_by_key(SHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=1000,
            cols=len(HEADERS)
        )

    if not worksheet.row_values(1):
        worksheet.update(
            range_name="A1:I1",
            values=[HEADERS]
        )

    return worksheet


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/Desert Bloom Technologies Logo.png")
def logo():
    return send_from_directory(BASE_DIR, "Desert Bloom Technologies Logo.png")


@app.route("/tech.png")
def favicon():
    return send_from_directory(BASE_DIR, "tech.png")


@app.route("/api/contact", methods=["POST"])
def submit_contact():
    data = (
        request.get_json(silent=True)
        if request.is_json
        else request.form
    )

    if data is None or not hasattr(data, "get"):
        return jsonify(
            success=False,
            message="Invalid form submission."
        ), 400

    fields = {
        "name": str(data.get("name", "")).strip(),
        "email": str(data.get("email", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "clientType": str(data.get("clientType", "")).strip(),
        "category": str(data.get("category", "")).strip(),
        "budget": str(
            data.get("budget", "Not decided")
        ).strip(),
        "deadline": str(
            data.get("deadline", "Flexible")
        ).strip(),
        "description": str(
            data.get("description", "")
        ).strip(),
    }

    required_fields = ("name", "email", "clientType", "category", "description")
    if any(not fields[field] for field in required_fields):
        return jsonify(
            success=False,
            message="Please complete all required fields."
        ), 400

    if (
        len(fields["name"]) > 120
        or len(fields["email"]) > 254
        or len(fields["phone"]) > 30
        or len(fields["clientType"]) > 120
        or len(fields["category"]) > 200
        or len(fields["budget"]) > 120
        or len(fields["deadline"]) > 200
        or len(fields["description"]) > 10000
    ):
        return jsonify(
            success=False,
            message="One or more fields are too long."
        ), 400

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        fields["email"]
    ):
        return jsonify(
            success=False,
            message="Please enter a valid email address."
        ), 400

    # Prevent spreadsheet formula injection from user input.
    values = list(fields.values())
    safe_values = [
        "'" + value if value.startswith(("=", "+", "-", "@"))
        else value
        for value in values
    ]

    row = [
        datetime.now(
            timezone(timedelta(hours=5, minutes=30), name="IST")
        ).strftime("%Y-%m-%d %H:%M:%S"),
        *safe_values,
    ]

    try:
        worksheet = get_worksheet()
        worksheet.append_row(
            row,
            value_input_option="RAW"
        )

        return jsonify(
            success=True,
            saved_to_sheet=True,
            message="Thank you! Your enquiry has been saved to Google Sheets."
        ), 201

    except Exception:
        app.logger.exception("Google Sheets submission failed")
        return jsonify(
            success=False,
            message=(
                "We could not save your enquiry right now. "
                "Please try again later."
            )
        ), 500


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(
        success=False,
        message="The submitted form is too large."
    ), 413


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
