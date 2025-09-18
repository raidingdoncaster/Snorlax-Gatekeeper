import os
import hashlib
import gspread
import pytesseract
from PIL import Image
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory, flash, jsonify
)
from google.oauth2.service_account import Credentials

# create Flask app instance
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret")

# Campfire related below
from campfire.client import CampfireClient
from campfire.group import get_group_members
from campfire.event import get_group_events, get_event_attendees

from dotenv import load_dotenv

@app.route("/campfire/test")
def campfire_test():
    if not CAMPFIRE_TOKEN:
        return jsonify({"error": "Campfire token missing"}), 400

    client = CampfireClient(token=CAMPFIRE_TOKEN)

    try:
        # Ask Campfire for your own profile (basic check)
        data = client.get("/me")
        return jsonify({"status": "success", "me": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
# Basic test route (checks Flask is working)
@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "message": "Hello from Flask 🚀"})

# Load environment variables (for CAMPFIRE_TOKEN)
load_dotenv()
CAMPFIRE_TOKEN = os.getenv("CAMPFIRE_TOKEN")

#Campfire setup
@app.route("/campfire/<group_id>")
def campfire_dashboard(group_id):
    if not CAMPFIRE_TOKEN:
        flash("Campfire token is missing. Please set CAMPFIRE_TOKEN in your .env file.")
        return redirect(url_for("dashboard"))  # fallback route

    client = CampfireClient(token=CAMPFIRE_TOKEN)

    try:
        members = get_group_members(client, group_id)
        events = get_group_events(client, group_id)

        history = []
        for event in events:
            attendees = get_event_attendees(client, event["id"])
            history.append({"event": event, "attendees": attendees})

        return render_template(
            "dashboard.html",
            members=members,
            history=history,
            group_id=group_id
        )
    except Exception as e:
        flash(f"Error fetching Campfire data: {e}")
        return redirect(url_for("dashboard"))


# Google Sheets setup
import json

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

google_service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
if google_service_account_json:
    service_account_info = json.loads(google_service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
else:
    raise RuntimeError("❌ GOOGLE_SERVICE_ACCOUNT_JSON not set in environment")
    # Fallback to local file for development
    SERVICE_ACCOUNT_FILE = "pogo-passport-key.json"
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

client = gspread.authorize(creds)
sheet = client.open("POGO Passport Sign-Ins").sheet1

# Uploads folder setup
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Serve uploaded files
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Helper: hash values
def hash_value(value):
    return hashlib.sha256(value.encode()).hexdigest()

# Home redirects to login
@app.route("/")
def home():
    return redirect(url_for("login"))

# Step 1: Upload screenshot + OCR name
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if "screenshot" not in request.files:
            return "❌ No file uploaded"

        file = request.files["screenshot"]
        if file.filename == "":
            return "❌ No file selected"

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # OCR extract trainer name
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        print("🔍 OCR detected the following lines:")
        for i, line in enumerate(lines, start=1):
            print(f"{i}: {line}")

        trainer_name = "Unknown"
        for line in lines:
            upper_line = line.upper()
            if any(skip in upper_line for skip in ["FRIENDS", "RIENDS", "PARTY", "STYLE", "SCRAPBOOK", "JOURNAL", "BUDDY", "HISTORY"]):
                continue
            if any(ch in line for ch in [",", "/", ":", "%"]):
                continue
            if line.replace(" ", "").isalnum() and len(line) > 2:
                trainer_name = line
                break

        print(f"✅ Selected trainer name: {trainer_name}")

        session["screenshot_path"] = filepath
        return render_template("confirm.html", trainer_name=trainer_name, title="Confirm Trainer Name")

    return render_template("signup.html", title="Sign Up")

# Step 2: Confirm trainer name + set PIN + reset code
@app.route("/confirm", methods=["POST"])
def confirm():
    trainer_name = request.form["trainer_name"]
    pin = request.form["pin"]
    reset_code = request.form["reset_code"]

    pin_hash = hash_value(pin)
    reset_code_hash = hash_value(reset_code)

    screenshot_path = session.get("screenshot_path", "uploads/placeholder.png")
    screenshot_url = f"/uploads/{os.path.basename(screenshot_path)}"

    # Check if trainer already exists
    rows = sheet.get_all_values()
    for row in rows[1:]:
        if row[0] == trainer_name:
            return render_template(
                "error.html",
                title="Already Registered",
                message=f"Trainer {trainer_name} is already registered. Please log in or reset your PIN."
            )

    # Save new entry (Trainer, PIN hash, Screenshot, Progress, Reset Code, Reset Code Hash)
    sheet.append_row([trainer_name, pin_hash, screenshot_url, "0", reset_code, reset_code_hash])

    session.pop("screenshot_path", None)
    return redirect(url_for("login"))

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        trainer_name = request.form["trainer_name"]
        pin = request.form["pin"]
        pin_hash = hash_value(pin)

        rows = sheet.get_all_values()
        for row in rows[1:]:
            if row[0] == trainer_name and row[1] == pin_hash:
                # Store all useful info in session
                session["trainer_name"] = trainer_name
                session["progress"] = row[3]
                session["screenshot"] = row[2]
                session["reset_code"] = row[4]  # plain text reset code
                return redirect(url_for("dashboard"))

        return render_template("error.html", title="Login Failed", message="Invalid trainer name or PIN.")

    return render_template("login.html", title="Log In")

# Forgot PIN - Step 1: upload screenshot
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        file = request.files["screenshot"]
        if file.filename == "":
            return "❌ No file selected"

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # OCR trainer name
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        trainer_name = "Unknown"
        for line in lines:
            upper_line = line.upper()
            if any(skip in upper_line for skip in ["FRIENDS", "RIENDS", "PARTY", "STYLE", "SCRAPBOOK", "JOURNAL", "BUDDY", "HISTORY"]):
                continue
            if any(ch in line for ch in [",", "/", ":", "%"]):
                continue
            if line.replace(" ", "").isalnum() and len(line) > 2:
                trainer_name = line
                break

        session["reset_trainer"] = trainer_name
        return render_template("reset.html", trainer_name=trainer_name, title="Reset PIN")

    return render_template("forgot.html", title="Forgot PIN")

# Forgot PIN - Step 2: verify reset code + set new PIN
@app.route("/reset", methods=["POST"])
def reset():
    trainer_name = request.form["trainer_name"]
    reset_code = request.form["reset_code"]
    new_pin = request.form["new_pin"]

    reset_code_hash = hash_value(reset_code)
    pin_hash = hash_value(new_pin)

    rows = sheet.get_all_values()
    for i, row in enumerate(rows[1:], start=2):
        if row[0] == trainer_name and row[5] == reset_code_hash:  # col 6 = Reset Code Hash
            sheet.update_cell(i, 2, pin_hash)  # update PIN hash
            break
    else:
        return render_template("error.html", title="Reset Failed", message="Reset code didn’t match. Try again.")

    return redirect(url_for("login"))

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Dashboard
@app.route("/dashboard")
def dashboard():
    if "trainer_name" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        trainer_name=session["trainer_name"],
        progress=session.get("progress", 0),      # matches {{ progress }}
        screenshot=session.get("screenshot"),     # matches {{ screenshot }}
        reset_code=session.get("reset_code"),     # matches {{ reset_code }}
        wide=True # for dashboard layout
    )

# Manage_Account
@app.route("/manage_account", methods=["GET", "POST"])
def manage_account():
    if "trainer_name" not in session:
        return redirect(url_for("login"))

    trainer_name = session["trainer_name"]
    rows = sheet.get_all_values()

    # Find the row for this trainer
    trainer_row = None
    for i, row in enumerate(rows[1:], start=2):
        if row[0] == trainer_name:
            trainer_row = (i, row)
            break

    if not trainer_row:
        flash("Trainer not found in database.", "danger")
        return redirect(url_for("dashboard"))

    row_index, row_data = trainer_row
    stored_pin_hash = row_data[1]
    stored_reset_code = row_data[4]
    stored_reset_hash = row_data[5]

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_pin":
            current_memorable = request.form["current_memorable"]
            if hash_value(current_memorable) != stored_reset_hash:
                flash("Current memorable password is incorrect.", "danger")
                return redirect(url_for("manage_account"))

            new_pin = request.form["new_pin"]
            confirm_pin = request.form["confirm_pin"]

            if new_pin != confirm_pin:
                flash("New PINs do not match.", "danger")
                return redirect(url_for("manage_account"))

            new_pin_hash = hash_value(new_pin)
            sheet.update_cell(row_index, 2, new_pin_hash)  # col 2 = PIN hash
            session["pin_hash"] = new_pin_hash

            flash("✅ PIN updated successfully.", "success")
            return redirect(url_for("dashboard"))

        elif action == "reset_memorable":
            current_pin = request.form["current_pin"]
            if hash_value(current_pin) != stored_pin_hash:
                flash("Current PIN is incorrect.", "danger")
                return redirect(url_for("manage_account"))

            new_memorable = request.form["new_memorable"]
            new_memorable_hash = hash_value(new_memorable)

            sheet.update_cell(row_index, 5, new_memorable)       # col 5 = Reset Code (plain text)
            sheet.update_cell(row_index, 6, new_memorable_hash)  # col 6 = Reset Code Hash

            session["reset_code"] = new_memorable

            flash("✅ Memorable password updated successfully.", "success")
            return redirect(url_for("dashboard"))

    return render_template("manage_account.html", wide=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)