import warnings

# Suppress warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")
warnings.filterwarnings("ignore", category=DeprecationWarning, message="The default datetime adapter is deprecated")

import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import io
import datetime
import configparser
import os
import json
import secrets
import string
from difflib import SequenceMatcher
import numpy as np
import face_recognition  # New import for facial recognition
from streamlit_js_eval import streamlit_js_eval
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

DB_PATH = 'missing_persons.db'
MATCH_TOLERANCE = 0.6
MIN_TEXT_SIMILARITY = 0.72
TRACKING_CODE_LENGTH = 8


def generate_tracking_code(length: int = TRACKING_CODE_LENGTH) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def mask_phone_number(phone: str) -> str:
    if not phone or len(phone) < 4:
        return phone or "N/A"
    return f"{'*' * (len(phone) - 4)}{phone[-4:]}"


def sequence_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_valid_phone(phone: str) -> bool:
    digits = [c for c in phone if c.isdigit()]
    return len(digits) >= 7


def render_location_capture(source: str = "Public"):
    geo_key = f"geo_coords_{source}"
    st.subheader("Live Location Capture")
    st.caption("Share the current GPS location to help investigators respond faster.")
    use_geo = st.checkbox("Use my current device location", key=f"use_geo_toggle_{source}")

    coords_state = st.session_state.get(geo_key)
    if use_geo:
        coords = streamlit_js_eval(
            js_expressions="""
            await new Promise((resolve) => {
                if (!navigator.geolocation) {
                    resolve(["error", "Geolocation not supported on this device."]);
                    return;
                }
                navigator.geolocation.getCurrentPosition(
                    (position) => resolve([position.coords.latitude, position.coords.longitude, position.coords.accuracy]),
                    (error) => resolve(["error", error.message]),
                    { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
                );
            });
            """,
            key=f"geo_eval_{source}"
        )
        if coords:
            if isinstance(coords, list) and coords and coords[0] == "error":
                st.error(f"Unable to capture GPS location: {coords[1]}")
            elif isinstance(coords, list) and len(coords) == 3:
                coords_state = {"lat": coords[0], "lng": coords[1], "accuracy": coords[2]}
                st.session_state[geo_key] = coords_state
            else:
                st.warning("GPS data unavailable. Please enter the location manually.")

    if coords_state:
        st.success(f"Location locked at ({coords_state['lat']:.5f}, {coords_state['lng']:.5f}) ±{coords_state['accuracy']:.0f}m")
        st.map(pd.DataFrame([{"lat": coords_state["lat"], "lon": coords_state["lng"]}]))
    else:
        st.info("Location will rely on the address details unless GPS coordinates are provided.")

    return coords_state


def trigger_alert_effect(note_id: int):
    unique_key = f"alert_fx_{note_id}_{secrets.token_hex(3)}"
    streamlit_js_eval(
        js_expressions="""
const AudioContext = window.AudioContext || window.webkitAudioContext;
if (AudioContext) {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    osc.type = "triangle";
    osc.frequency.value = 880;
    const gain = ctx.createGain();
    gain.gain.value = 0.2;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    setTimeout(() => { osc.stop(); ctx.close(); }, 600);
}
if (navigator.vibrate) {
    navigator.vibrate([250, 150, 250]);
}
alert("🔔 New critical alert received in the Missing Person Finder dashboard.");
        """,
        key=unique_key
    )


def fetch_person_summary(person_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, name, status, last_seen_location, reporter_phone, reporter_email, reporter_tracking_code, report_source
        FROM missing_persons
        WHERE id = ?
    """, (person_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "status": row[2],
        "last_seen_location": row[3],
        "phone": row[4],
        "email": row[5],
        "tracking": row[6],
        "source": row[7]
    }


def emit_admin_toasts():
    pending = get_notifications(include_read=False, limit=5)
    displayed = st.session_state.setdefault("toast_ids", set())
    for note in pending:
        if note['id'] in displayed:
            continue
        trigger_alert_effect(note['id'])
        st.toast(f"{note['title']}: {note['message']}")
        displayed.add(note['id'])

# --- AI Model Integration (Age/Gender) ---
def detect_age_gender(image_bytes):
    if not DEEPFACE_AVAILABLE:
        return "N/A", "N/A"
        
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert('RGB')
        img_np = np.array(image)
        result = DeepFace.analyze(img_np, actions=['age', 'gender'], enforce_detection=False)
        if result:
            age = str(result[0]['age'])
            gender = max(result[0]['gender'], key=result[0]['gender'].get) if isinstance(result[0]['gender'], dict) else str(result[0]['gender'])
            return age, gender
        else:
            return "Not detected", "Not detected"
    except Exception as e:
        return "Error", "Error"

# --- Database Setup and Functions ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS missing_persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age TEXT,
            gender TEXT,
            last_seen_location TEXT,
            description TEXT,
            image BLOB,
            status TEXT DEFAULT 'Missing',
            date_reported DATETIME,
            reporter_phone TEXT,
            reporter_email TEXT,
            reporter_consent INTEGER DEFAULT 0,
            location_lat REAL,
            location_lng REAL,
            location_accuracy REAL,
            reporter_tracking_code TEXT,
            report_source TEXT DEFAULT 'Public'
        )
    ''')

    c.execute("PRAGMA table_info(missing_persons)")
    existing_columns = {info[1] for info in c.fetchall()}
    new_columns = {
        'date_reported': "DATETIME",
        'reporter_phone': "TEXT",
        'reporter_email': "TEXT",
        'reporter_consent': "INTEGER DEFAULT 0",
        'location_lat': "REAL",
        'location_lng': "REAL",
        'location_accuracy': "REAL",
        'reporter_tracking_code': "TEXT",
        'report_source': "TEXT DEFAULT 'Public'"
    }
    for column, definition in new_columns.items():
        if column not in existing_columns:
            c.execute(f"ALTER TABLE missing_persons ADD COLUMN {column} {definition}")
            if column == 'date_reported':
                c.execute("UPDATE missing_persons SET date_reported = CURRENT_TIMESTAMP WHERE date_reported IS NULL")

    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            level TEXT DEFAULT 'info',
            payload TEXT,
            is_read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS match_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_report_id INTEGER NOT NULL,
            candidate_report_id INTEGER,
            similarity REAL,
            match_type TEXT,
            details TEXT,
            status TEXT DEFAULT 'New',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(source_report_id) REFERENCES missing_persons(id),
            FOREIGN KEY(candidate_report_id) REFERENCES missing_persons(id)
        )
    ''')

    c.execute("CREATE INDEX IF NOT EXISTS idx_missing_status ON missing_persons(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_missing_tracking ON missing_persons(reporter_tracking_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_matches_status ON match_results(status)")

    conn.commit()
    conn.close()

def create_notification(title: str, message: str, level: str = 'info', payload: dict | None = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO notifications (title, message, level, payload) VALUES (?, ?, ?, ?)",
        (title, message, level, json.dumps(payload) if payload else None)
    )
    conn.commit()
    conn.close()


def get_notifications(include_read: bool = False, limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if include_read:
        c.execute("SELECT id, title, message, level, payload, is_read, created_at FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,))
    else:
        c.execute("SELECT id, title, message, level, payload, is_read, created_at FROM notifications WHERE is_read = 0 ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "title": row[1],
            "message": row[2],
            "level": row[3],
            "payload": json.loads(row[4]) if row[4] else None,
            "is_read": bool(row[5]),
            "created_at": row[6]
        }
        for row in rows
    ]


def mark_notification_read(notification_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()


def delete_notification(notification_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()


def delete_match(match_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM match_results WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()


def set_status(person_id: int, new_status: str, notify: bool = True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE missing_persons SET status = ? WHERE id = ?", (new_status, person_id))
    conn.commit()
    conn.close()
    if notify:
        create_notification(
            "Report status updated",
            f"Report #{person_id} marked as {new_status}.",
            payload={"person_id": person_id, "status": new_status}
        )


def update_status(person_id, new_status):
    set_status(person_id, new_status, notify=True)


def delete_report(person_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM missing_persons WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()
    create_notification(
        "Report deleted",
        f"Report #{person_id} removed by admin.",
        level="warning",
        payload={"person_id": person_id}
    )


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    missing_count = c.execute("SELECT COUNT(*) FROM missing_persons WHERE status = 'Missing'").fetchone()[0]
    found_count = c.execute("SELECT COUNT(*) FROM missing_persons WHERE status = 'Found'").fetchone()[0]
    alerts = c.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0").fetchone()[0]
    pending_matches = c.execute("SELECT COUNT(*) FROM match_results WHERE status IN ('New','Under Review')").fetchone()[0]
    conn.close()
    return missing_count, found_count, alerts, pending_matches


def record_match_result(source_report_id: int, candidate_report_id: int | None, similarity: float, match_type: str, details: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Avoid duplicate matches for the same pair and type
    c.execute(
        "SELECT id FROM match_results WHERE source_report_id = ? AND candidate_report_id IS ? AND match_type = ?",
        (source_report_id, candidate_report_id, match_type)
    )
    existing = c.fetchone()
    if existing:
        conn.close()
        return

    c.execute(
        '''
        INSERT INTO match_results (source_report_id, candidate_report_id, similarity, match_type, details)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (source_report_id, candidate_report_id, similarity, match_type, json.dumps(details))
    )
    conn.commit()
    conn.close()


def update_match_status(match_id: int, new_status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE match_results SET status = ? WHERE id = ?", (new_status, match_id))
    conn.commit()
    conn.close()


def get_match_results(status_filter: list[str] | None = None, limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status_filter:
        placeholders = ",".join("?" for _ in status_filter)
        query = f'''
            SELECT id, source_report_id, candidate_report_id, similarity, match_type, details, status, created_at
            FROM match_results
            WHERE status IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT ?
        '''
        c.execute(query, (*status_filter, limit))
    else:
        c.execute('''
            SELECT id, source_report_id, candidate_report_id, similarity, match_type, details, status, created_at
            FROM match_results
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "source_report_id": row[1],
            "candidate_report_id": row[2],
            "similarity": row[3],
            "match_type": row[4],
            "details": json.loads(row[5]) if row[5] else {},
            "status": row[6],
            "created_at": row[7]
        } for row in rows
    ]


def get_person_matches(person_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        '''
        SELECT id, source_report_id, candidate_report_id, similarity, match_type, status, created_at
        FROM match_results
        WHERE source_report_id = ? OR candidate_report_id = ?
        ORDER BY created_at DESC
        ''',
        (person_id, person_id)
    )
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "source_report_id": row[1],
            "candidate_report_id": row[2],
            "similarity": row[3],
            "match_type": row[4],
            "status": row[5],
            "created_at": row[6]
        } for row in rows
    ]


def run_matching_pipeline(report_id: int, image_bytes: bytes | None, person_name: str, last_seen_location: str, age: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, name, image, last_seen_location, age
        FROM missing_persons
        WHERE id != ? AND status = 'Missing'
    """, (report_id,))
    candidates = c.fetchall()
    conn.close()

    if not candidates:
        return []

    matches_found = []

    uploaded_encoding = None
    if image_bytes:
        try:
            uploaded_img_np = np.array(Image.open(io.BytesIO(image_bytes)))
            encodings = face_recognition.face_encodings(uploaded_img_np)
            if encodings:
                uploaded_encoding = encodings[0]
        except Exception:
            uploaded_encoding = None

    for candidate in candidates:
        candidate_id, candidate_name, candidate_image_bytes, candidate_location, candidate_age = candidate

        # Face match attempt
        if uploaded_encoding is not None and candidate_image_bytes:
            try:
                db_img_np = np.array(Image.open(io.BytesIO(candidate_image_bytes)))
                db_encodings = face_recognition.face_encodings(db_img_np)
                if db_encodings:
                    db_encoding = db_encodings[0]
                    is_match = face_recognition.compare_faces([uploaded_encoding], db_encoding, tolerance=MATCH_TOLERANCE)[0]
                    if is_match:
                        distance = face_recognition.face_distance([uploaded_encoding], db_encoding)[0]
                        similarity = float((1 - distance) * 100)
                        details = {
                            "match_reason": "Facial recognition",
                            "source_name": person_name,
                            "candidate_name": candidate_name
                        }
                        record_match_result(report_id, candidate_id, similarity, "facial", details)
                        matches_found.append({"id": candidate_id, "name": candidate_name, "score": similarity, "method": "Facial"})
            except Exception:
                pass

        # Text similarity fallback
        name_similarity = sequence_similarity(person_name, candidate_name)
        location_similarity = sequence_similarity(last_seen_location or "", candidate_location or "")
        age_similarity = 1.0 if candidate_age and age and candidate_age == age else 0.0
        combined_score = max(name_similarity, location_similarity, age_similarity)

        if combined_score >= MIN_TEXT_SIMILARITY:
            details = {
                "match_reason": "Contextual similarity",
                "name_similarity": f"{name_similarity:.2f}",
                "location_similarity": f"{location_similarity:.2f}",
                "age_similarity": f"{age_similarity:.2f}"
            }
            record_match_result(report_id, candidate_id, combined_score * 100, "context", details)
            matches_found.append({"id": candidate_id, "name": candidate_name, "score": combined_score * 100, "method": "Context"})

    if matches_found:
        top_match = matches_found[0]
        reporter_summary = fetch_person_summary(report_id)
        reporter_phone = reporter_summary['phone'] if reporter_summary else "N/A"
        create_notification(
            "Potential match detected",
            f"Report #{report_id} has {len(matches_found)} potential match(es). Highest: {top_match['name']} ({top_match['method']}). Reporter Phone: {reporter_phone}",
            level="warning",
            payload={"report_id": report_id, "matches": matches_found}
        )
        set_status(report_id, "Match Found - Await Review", notify=False)
        for match in matches_found:
            set_status(match['id'], "Match Found - Await Review", notify=False)

    return matches_found

# --- UI Components ---
def report_missing_person_form(source: str = "Public"):
    require_contact = source == "Public"
    st.header("Report a Missing Person" if source == "Public" else "Add / Update Missing Person Record")
    st.write("Provide as much detail as possible. Accurate information speeds up investigations.")

    captured_coords = render_location_capture(source=source)

    with st.form(f"report_form_{source.lower()}", clear_on_submit=True):
        st.subheader("Person Details")
        name = st.text_input("Full Name *")
        col1, col2 = st.columns(2)
        with col1:
            last_seen = st.text_input("Last Seen Location *")
        with col2:
            manual_lat = st.text_input(
                "Latitude (optional)",
                value=f"{captured_coords['lat']:.5f}" if captured_coords else ""
            )
            manual_lng = st.text_input(
                "Longitude (optional)",
                value=f"{captured_coords['lng']:.5f}" if captured_coords else ""
            )
        description = st.text_area("Additional Details (clothing, distinguishing features, etc.) *")
        uploaded_image = st.file_uploader("Upload a Clear Image *", type=['png', 'jpg', 'jpeg'])

        st.subheader("Reporter Contact")
        reporter_phone = st.text_input("Phone Number *" if require_contact else "Phone Number")
        reporter_email = st.text_input("Email (optional)")
        reporter_consent = st.checkbox(
            "I consent to being contacted by authorities regarding this report.",
            value=require_contact,
            key=f"consent_{source}"
        )

        st.caption("Fields marked with * are required.")

        submit_button = st.form_submit_button("Submit Report")

        if submit_button:
            missing_fields = []
            if not name:
                missing_fields.append("Full Name")
            if not last_seen:
                missing_fields.append("Last Seen Location")
            if not description:
                missing_fields.append("Description")
            if not uploaded_image:
                missing_fields.append("Image")
            if require_contact and not reporter_phone:
                missing_fields.append("Phone Number")
            if missing_fields:
                st.warning("Please complete the following required fields: " + ", ".join(missing_fields))
                return

            if reporter_phone and not is_valid_phone(reporter_phone):
                st.error("Enter a valid phone number with at least 7 digits.")
                return

            if require_contact and not reporter_consent:
                st.error("Consent is required to submit a public report.")
                return

            image_bytes = uploaded_image.getvalue()
            age_estimate, gender_estimate = detect_age_gender(image_bytes) if uploaded_image else ("N/A", "N/A")

            lat_value = None
            lng_value = None
            accuracy_value = None

            if captured_coords:
                lat_value = captured_coords['lat']
                lng_value = captured_coords['lng']
                accuracy_value = captured_coords['accuracy']
            if manual_lat and manual_lng:
                try:
                    lat_value = float(manual_lat)
                    lng_value = float(manual_lng)
                except ValueError:
                    st.error("Latitude/Longitude must be numeric values.")
                    return

            reporter_phone_clean = reporter_phone.strip() if reporter_phone else None
            reporter_email_clean = reporter_email.strip() if reporter_email else None

            tracking_code = generate_tracking_code()
            reported_at = datetime.datetime.now()

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO missing_persons (
                    name, age, gender, last_seen_location, description, image, date_reported,
                    reporter_phone, reporter_email, reporter_consent, location_lat, location_lng,
                    location_accuracy, reporter_tracking_code, report_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    age_estimate,
                    gender_estimate,
                    last_seen,
                    description,
                    image_bytes,
                    reported_at,
                    reporter_phone_clean,
                    reporter_email_clean,
                    int(reporter_consent),
                    lat_value,
                    lng_value,
                    accuracy_value,
                    tracking_code,
                    source
                )
            )
            person_id = c.lastrowid
            conn.commit()
            conn.close()

            matches = run_matching_pipeline(person_id, image_bytes, name, last_seen, age_estimate)

            st.success(f"Report for {name} submitted successfully.")
            st.info(f"Tracking ID: **{tracking_code}** — share this to follow up on the case.")
            if age_estimate != "N/A" or gender_estimate != "N/A":
                st.info(f"AI Analysis: Estimated Age {age_estimate}, Estimated Gender {gender_estimate}.")
            if matches:
                st.warning(f"{len(matches)} potential match(es) queued for admin review.")

def search_by_image_tab():
    st.header("Found Someone?")
    st.write("If you've found someone who might be missing, provide your contact information and location so authorities can follow up.")

    captured_coords = render_location_capture(source="Found")

    with st.form("found_person_form", clear_on_submit=True):
        st.subheader("Your Contact Information")
        reporter_phone = st.text_input("Phone Number *")
        reporter_email = st.text_input("Email (optional)")

        st.subheader("Sighting Details")
        sighting_location = st.text_input("Where did you find this person? *")
        additional_notes = st.text_area("Additional details about the sighting")

        uploaded_image = st.file_uploader("Upload a photo of the person you found *", type=['png', 'jpg', 'jpeg'], key="found_uploader")

        st.caption("Fields marked with * are required.")

        submit_button = st.form_submit_button("Submit Sighting Report")

        if submit_button:
            missing_fields = []
            if not reporter_phone:
                missing_fields.append("Phone Number")
            if not sighting_location:
                missing_fields.append("Sighting Location")
            if not uploaded_image:
                missing_fields.append("Photo")
            if missing_fields:
                st.warning("Please complete the following required fields: " + ", ".join(missing_fields))
                return

            if not is_valid_phone(reporter_phone):
                st.error("Enter a valid phone number with at least 7 digits.")
                return

            # Process the sighting report
            image_bytes = uploaded_image.getvalue()
            age_estimate, gender_estimate = detect_age_gender(image_bytes)

            lat_value = None
            lng_value = None
            accuracy_value = None

            if captured_coords:
                lat_value = captured_coords['lat']
                lng_value = captured_coords['lng']
                accuracy_value = captured_coords['accuracy']

            # Insert sighting as a report
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO missing_persons (
                    name, age, gender, last_seen_location, description, image, date_reported,
                    reporter_phone, reporter_email, reporter_consent, location_lat, location_lng,
                    location_accuracy, reporter_tracking_code, report_source, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Sighting Report",
                    age_estimate,
                    gender_estimate,
                    sighting_location,
                    additional_notes,
                    image_bytes,
                    datetime.datetime.now(),
                    reporter_phone,
                    reporter_email,
                    1,  # Assume consent for sightings
                    lat_value,
                    lng_value,
                    accuracy_value,
                    None,  # No tracking code for sightings
                    "Sighting",
                    "Sighting Reported"
                )
            )
            sighting_id = c.lastrowid
            conn.commit()
            conn.close()

            # Run matching pipeline on the sighting image with the new report_id
            matches = run_matching_pipeline(sighting_id, image_bytes, "Sighting Report", sighting_location, age_estimate)

            st.success("Sighting report submitted successfully!")
            st.info("🚔 **Police will follow up with you shortly.** Please keep your phone available for contact from local authorities.")
            if age_estimate != "N/A" or gender_estimate != "N/A":
                st.info(f"AI Analysis of photo: Estimated Age {age_estimate}, Estimated Gender {gender_estimate}.")
            st.warning("Do not approach the person directly. Wait for professional assistance.")


def track_report_form():
    st.header("Track an Existing Report")
    st.write("Enter the tracking ID that was shared after you submitted the report.")
    tracking_id_input = st.text_input("Tracking ID")
    if st.button("Fetch Status"):
        tracking_id = (tracking_id_input or "").strip().upper()
        if not tracking_id:
            st.warning("Please enter a valid tracking ID.")
            return

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT id, name, status, last_seen_location, date_reported, reporter_phone, location_lat, location_lng
            FROM missing_persons
            WHERE reporter_tracking_code = ?
        """, (tracking_id,))
        record = c.fetchone()
        conn.close()

        if record:
            st.success("Report located.")
            st.write(f"**Name:** {record[1]}")
            st.write(f"**Status:** {record[2]}")
            st.write(f"**Last Seen:** {record[3]}")
            st.write(f"**Reported On:** {record[4]}")
            st.write("**Investigator Contact:** Provided to authorities.")
            if record[6] is not None and record[7] is not None:
                st.map(pd.DataFrame([{"lat": record[6], "lon": record[7]}]))
            st.caption("If details change, submit an update mentioning this tracking ID.")
        else:
            st.error("No report found for that tracking ID. Double-check the code from your confirmation message.")


def safety_tips_panel():
    st.header("Stay Safe While Helping")
    st.markdown(
        """
        - Always dial local emergency services before approaching someone in distress.
        - Share sightings from a safe distance and avoid confrontations.
        - Provide recent photos or videos only through trusted portals.
        - Never share your full address publicly—only with verified officers.
        - Keep your tracking ID secure; it contains sensitive case information.
        """
    )


def render_alerts_and_matches():
    st.header("Alerts & Matches Center")
    st.write("Review unread alerts from public reports and automated match jobs.")

    notifications = get_notifications(include_read=True, limit=25)
    if notifications:
        for note in notifications:
            if note['level'] == 'warning':
                container = st.warning
            elif note['level'] == 'error':
                container = st.error
            elif note['level'] == 'success':
                container = st.success
            else:
                container = st.info
            with st.container():
                container(f"**{note['title']}** — {note['message']} ({note['created_at']})")
                if note['payload']:
                    with st.expander("Payload details"):
                        st.json(note['payload'])
                if not note['is_read']:
                    if st.button("Mark as Read", key=f"note_{note['id']}"):
                        mark_notification_read(note['id'])
                        st.rerun()
                if st.button("Delete", key=f"delete_note_{note['id']}"):
                    delete_notification(note['id'])
                    st.rerun()
    else:
        st.info("No alerts at the moment.")

    st.subheader("Potential Matches Queue")
    matches = get_match_results(status_filter=['New', 'Under Review'], limit=30)
    if not matches:
        st.success("No pending matches. Great job staying on top of the queue!")
        return

    for match in matches:
        source_summary = fetch_person_summary(match['source_report_id'])
        candidate_summary = fetch_person_summary(match['candidate_report_id']) if match['candidate_report_id'] else None
        st.markdown(f"**Match #{match['id']}** — {match['match_type'].title()} ({match['similarity']:.1f}%) — Status: {match['status']}")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Source Report**")
            if source_summary:
                st.write(f"Name: {source_summary['name']} ({source_summary['status']})")
                st.write(f"Last Seen: {source_summary['last_seen_location']}")
                st.write(f"Contact: {mask_phone_number(source_summary['phone'] or '')}")
            else:
                st.write("Record no longer available.")
        with col2:
            st.write("**Potential Match**")
            if candidate_summary:
                st.write(f"Name: {candidate_summary['name']} ({candidate_summary['status']})")
                st.write(f"Last Seen: {candidate_summary['last_seen_location']}")
            else:
                st.write("Captured via automated search.")

        if match['details']:
            st.json(match['details'])

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button("Mark Under Review", key=f"review_{match['id']}"):
                update_match_status(match['id'], "Under Review")
                st.rerun()
        with action_col2:
            if st.button("Escalate", key=f"escalate_{match['id']}"):
                update_match_status(match['id'], "Escalated")
                create_notification(
                    "Match escalated",
                    f"Match #{match['id']} escalated for field investigation.",
                    level="warning",
                    payload={"match_id": match['id']}
                )
                st.rerun()
        with action_col3:
            if st.button("Dismiss", key=f"dismiss_{match['id']}"):
                update_match_status(match['id'], "Dismissed")
                st.rerun()

        st.divider()
# --- NEW: Facial Recognition Matching Page ---
def find_matches_page():
    st.header("Find Potential Matches by Photo")
    st.info("Upload a photo of a found person. The system will use facial recognition to find potential matches from the active missing persons database.")
    
    uploaded_image = st.file_uploader("Upload a Photo to Compare", type=['png', 'jpg', 'jpeg'], key="matching_uploader")

    if uploaded_image:
        st.image(uploaded_image, caption="Image to Compare", width=300)
        if st.button("Find Matches"):
            with st.spinner("Processing image and comparing against database... This may take a moment."):
                # 1. Load the uploaded image and find its face encoding
                uploaded_bytes = uploaded_image.getvalue()
                uploaded_img_np = np.array(Image.open(io.BytesIO(uploaded_bytes)))
                
                uploaded_face_encodings = face_recognition.face_encodings(uploaded_img_np)

                if not uploaded_face_encodings:
                    st.error("No face could be detected in the uploaded image. Please try a clearer photo.")
                    return

                uploaded_encoding = uploaded_face_encodings[0]

                # 2. Get all missing persons from the database
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id, name, image FROM missing_persons WHERE status = 'Missing'")
                all_missing_persons = c.fetchall()
                conn.close()

                if not all_missing_persons:
                    st.warning("There are no active missing person reports in the database to compare against.")
                    return

                # 3. Compare the uploaded face to all faces in the database
                matches = []
                for person in all_missing_persons:
                    person_id, person_name, person_image_bytes = person
                    
                    try:
                        db_img_np = np.array(Image.open(io.BytesIO(person_image_bytes)))
                        db_face_encodings = face_recognition.face_encodings(db_img_np)
                        
                        if db_face_encodings:
                            db_encoding = db_face_encodings[0]
                            # The compare_faces function returns a list of True/False values
                            is_match = face_recognition.compare_faces([uploaded_encoding], db_encoding, tolerance=0.6)[0]
                            
                            if is_match:
                                distance = face_recognition.face_distance([uploaded_encoding], db_encoding)[0]
                                similarity = (1 - distance) * 100
                                matches.append({
                                    "id": person_id,
                                    "name": person_name,
                                    "image": person_image_bytes,
                                    "similarity": f"{similarity:.2f}%"
                                })
                    except Exception:
                        # Ignore images in the DB that cause processing errors
                        continue
                
                # 4. Display the results
                st.subheader("Matching Results")
                if matches:
                    # Sort matches by similarity, highest first
                    sorted_matches = sorted(matches, key=lambda x: float(x['similarity'][:-1]), reverse=True)
                    st.success(f"Found {len(sorted_matches)} potential match(es).")
                    for match in sorted_matches:
                        with st.container():
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.image(match['image'], caption=f"Match: {match['name']}")
                            with col2:
                                st.write(f"**Name:** {match['name']}")
                                st.write(f"**Match Confidence:** {match['similarity']}")
                                st.write(f"**Database ID:** {match['id']}")
                                st.info("Review this case in the 'Manage Reports' section.")
                            st.markdown("---")
                else:
                    st.warning("No matches found in the database for the uploaded photo.")

# --- Login and Portal Functions ---
def show_login_page():
    # ... (existing function) ...
    st.header("Admin Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            config = configparser.ConfigParser()
            config.read('config.ini')
            admin_user = config['credentials']['username']
            admin_pass = config['credentials']['password']
            if username == admin_user and password == admin_pass:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("Invalid username or password.")

def admin_portal():
    st.sidebar.title("Admin Menu")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    emit_admin_toasts()
    menu = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Manage Reports", "Add New Report", "Alerts & Matches"]
    )

    if menu == "Dashboard":
        st.header("Admin Dashboard")
        missing_count, found_count, alerts, pending_matches = get_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Active Missing Reports", missing_count)
        col2.metric("Persons Found", found_count)
        col3.metric("Unread Alerts", alerts)
        col4.metric("Pending Matches", pending_matches)

        conn = sqlite3.connect(DB_PATH)
        latest = pd.read_sql_query(
            "SELECT id, name, status, date_reported FROM missing_persons ORDER BY date_reported DESC LIMIT 5",
            conn
        )
        map_df = pd.read_sql_query(
            "SELECT location_lat as lat, location_lng as lon FROM missing_persons WHERE status = 'Missing' AND location_lat IS NOT NULL AND location_lng IS NOT NULL",
            conn
        )
        conn.close()

        st.subheader("Recent Activity")
        if not latest.empty:
            st.dataframe(latest)
        else:
            st.info("No reports yet.")

        st.subheader("Active Case Heatmap")
        if not map_df.empty:
            st.map(map_df)
        else:
            st.info("No geolocated reports yet.")

    elif menu == "Manage Reports":
        st.header("Manage All Reports")
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT id, name, age, gender, status, date_reported, reporter_phone, reporter_email,
                   reporter_tracking_code, report_source, last_seen_location, location_lat, location_lng
            FROM missing_persons
            ORDER BY date_reported DESC
        """, conn)
        conn.close()

        if df.empty:
            st.info("No reports in the database.")
        else:
            search_name = st.text_input("Search by Name")
            status_filter = st.multiselect("Filter by Status", options=df['status'].unique(), default=df['status'].unique())
            filtered_df = df[
                df['name'].str.contains(search_name, case=False, na=False) &
                df['status'].isin(status_filter)
            ]
            for _, row in filtered_df.iterrows():
                header = f"{row['name']} | Status: {row['status']} | Source: {row['report_source']}"
                with st.expander(header):
                    conn = sqlite3.connect(DB_PATH)
                    details = conn.execute("SELECT description, image FROM missing_persons WHERE id = ?", (int(row['id']),)).fetchone()
                    conn.close()
                    person_matches = get_person_matches(row['id'])
                    if person_matches:
                        newest_match = person_matches[0]
                        st.warning(
                            f"Match Alert #{newest_match['id']} • {newest_match['match_type'].title()} "
                            f"({newest_match['similarity']:.1f}% similarity) • Status: {newest_match['status']}"
                        )
                        st.caption("Review photos and details before confirming the person as Found.")

                    col1, col2 = st.columns([1, 2])
                    if details and details[1]:
                        col1.image(Image.open(io.BytesIO(details[1])), caption=row['name'])
                    else:
                        col1.info("No image stored.")
                    col2.write(f"**ID:** {row['id']}")
                    col2.write(f"**Reported Age:** {row['age']}")
                    col2.write(f"**Gender:** {row['gender']}")
                    col2.write(f"**Date Reported:** {row['date_reported']}")
                    col2.write(f"**Last Seen:** {row['last_seen_location']}")
                    col2.write(f"**Tracking ID:** {row['reporter_tracking_code']}")
                    col2.write(f"**Reporter Phone:** {row['reporter_phone'] or 'N/A'}")
                    col2.write(f"**Reporter Email:** {row['reporter_email'] or 'N/A'}")

                    if details and details[0]:
                        st.write("**Description:**")
                        st.write(details[0])

                    if row['location_lat'] is not None and row['location_lng'] is not None:
                        st.map(pd.DataFrame([{"lat": row['location_lat'], "lon": row['location_lng']}]))

                    action_cols = st.columns(3)
                    if row['status'] == 'Missing':
                        with action_cols[0]:
                            if st.button("Mark as Found", key=f"found_{row['id']}"):
                                update_status(row['id'], 'Found')
                                st.success(f"{row['name']} marked as Found.")
                                st.rerun()
                        with action_cols[1]:
                            if st.button("Mark Under Investigation", key=f"in_progress_{row['id']}"):
                                update_status(row['id'], 'Under Investigation')
                                st.info(f"{row['name']} flagged for investigation.")
                                st.rerun()
                        with action_cols[2]:
                            if st.button("Delete Report", key=f"delete_{row['id']}"):
                                delete_report(row['id'])
                                st.warning(f"Report for {row['name']} deleted.")
                                st.rerun()
                    elif row['status'] == 'Under Investigation':
                        with action_cols[0]:
                            if st.button("Mark as Found", key=f"found_{row['id']}"):
                                update_status(row['id'], 'Found')
                                st.success(f"{row['name']} marked as Found.")
                                st.rerun()
                        with action_cols[2]:
                            if st.button("Delete Report", key=f"delete_{row['id']}"):
                                delete_report(row['id'])
                                st.warning(f"Report for {row['name']} deleted.")
                                st.rerun()

    elif menu == "Add New Report":
        report_missing_person_form(source="Admin")

    elif menu == "Alerts & Matches":
        render_alerts_and_matches()


def lost_lists_tab():
    st.header("Lost Lists")
    st.write("Browse the list of missing persons. If you have information about any of these individuals, please report it through the 'Found Someone?' section.")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, name, image, last_seen_location, description
        FROM missing_persons
        WHERE status = 'Missing'
        ORDER BY date_reported DESC
    """)
    missing_persons = c.fetchall()
    conn.close()

    if not missing_persons:
        st.info("No missing persons reports at the moment.")
        return

    # Display in a grid format
    cols = st.columns(3)  # 3 columns per row
    for i, person in enumerate(missing_persons):
        person_id, name, image_bytes, last_seen, description = person
        with cols[i % 3]:
            with st.container():
                if image_bytes:
                    st.image(Image.open(io.BytesIO(image_bytes)), caption=name, width=200)
                else:
                    st.image("https://via.placeholder.com/200x200?text=No+Image", caption=name)
                st.write(f"**{name}**")
                st.write(f"Last Seen: {last_seen}")
                if description:
                    st.caption(description[:100] + "..." if len(description) > 100 else description)


def public_portal():
    st.sidebar.title("Public Menu")
    menu = st.sidebar.radio("Navigation", ["Submit a Report", "Found Someone?", "Lost Lists", "Safety Tips"])
    if menu == "Submit a Report":
        report_missing_person_form(source="Public")
    elif menu == "Found Someone?":
        search_by_image_tab()
    elif menu == "Lost Lists":
        lost_lists_tab()
    elif menu == "Safety Tips":
        safety_tips_panel()

# --- Main App Logic ---
def main():
    st.set_page_config(page_title="Missing Person Finder", layout="wide")

    init_db()
    
    st.title("AI-Powered Missing Person Finder")

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    st.sidebar.title("Navigation")
    app_mode = st.sidebar.radio("Choose Portal", ["Public Portal", "Admin Section"])

    if app_mode == "Public Portal":
        public_portal()
    elif app_mode == "Admin Section":
        if st.session_state['logged_in']:
            admin_portal()
        else:
            show_login_page()

if __name__ == '__main__':
    main()
