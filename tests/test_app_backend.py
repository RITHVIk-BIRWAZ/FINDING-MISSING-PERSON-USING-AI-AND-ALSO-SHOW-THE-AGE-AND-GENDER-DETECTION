import datetime
import io
import sqlite3

import numpy as np
import pytest
from PIL import Image

import app


def _make_image_bytes(color=(255, 0, 0)):
    """Create a tiny PNG in memory for image-required fields."""
    buffer = io.BytesIO()
    Image.new("RGB", (5, 5), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _insert_person(**overrides):
    defaults = {
        "name": "Case Alpha",
        "age": "34",
        "gender": "Unknown",
        "last_seen_location": "Central Station",
        "description": "Test record",
        "image": _make_image_bytes(),
        "date_reported": datetime.datetime.now().isoformat(),
        "status": "Missing",
        "reporter_phone": "9999999999",
        "reporter_email": "case@example.com",
        "reporter_consent": 1,
        "location_lat": 12.34,
        "location_lng": 56.78,
        "location_accuracy": 5.0,
        "reporter_tracking_code": app.generate_tracking_code(),
        "report_source": "TestSuite",
    }
    defaults.update(overrides)
    columns = ", ".join(defaults.keys())
    placeholders = ", ".join(["?"] * len(defaults))
    conn = sqlite3.connect(app.DB_PATH)
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO missing_persons ({columns}) VALUES ({placeholders})",
        tuple(defaults.values()),
    )
    person_id = cur.lastrowid
    conn.commit()
    conn.close()
    return person_id


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    """Point the app at a temporary DB for each test."""
    db_file = tmp_path / "test_missing_persons.db"
    monkeypatch.setattr(app, "DB_PATH", str(db_file))
    app.init_db()
    yield str(db_file)


def test_init_db_creates_expected_schema(fresh_database):
    conn = sqlite3.connect(app.DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(missing_persons)")
    missing_columns = {row[1] for row in cur.fetchall()}
    for column in (
        "reporter_phone",
        "reporter_email",
        "reporter_tracking_code",
        "location_lat",
        "location_lng",
        "location_accuracy",
        "report_source",
    ):
        assert column in missing_columns

    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
    )
    assert cur.fetchone() is not None
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='match_results'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_notification_lifecycle(fresh_database):
    app.create_notification("Test Alert", "Payload incoming", level="warning")
    unread = app.get_notifications(include_read=False)
    assert len(unread) == 1
    assert unread[0]["title"] == "Test Alert"
    assert unread[0]["level"] == "warning"

    app.mark_notification_read(unread[0]["id"])
    assert app.get_notifications(include_read=False) == []


def test_run_matching_pipeline_records_matches(monkeypatch, fresh_database):
    """Simulate a facial-recognition hit plus contextual similarity backup."""

    def fake_face_encodings(_image_array):
        return [np.array([0.1, 0.2, 0.3])]

    def fake_compare_faces(_known, _candidate, tolerance=0.6):
        return [True]

    def fake_face_distance(_known, _candidate):
        return [0.2]

    monkeypatch.setattr(app.face_recognition, "face_encodings", fake_face_encodings)
    monkeypatch.setattr(app.face_recognition, "compare_faces", fake_compare_faces)
    monkeypatch.setattr(app.face_recognition, "face_distance", fake_face_distance)

    candidate_id = _insert_person(name="Jane Doe", last_seen_location="City Library")
    source_id = _insert_person(
        name="Unknown Person",
        last_seen_location="City Library",
        image=_make_image_bytes(color=(0, 255, 0)),
        reporter_tracking_code="TRACK1234",
    )

    matches = app.run_matching_pipeline(
        report_id=source_id,
        image_bytes=_make_image_bytes(color=(0, 255, 0)),
        person_name="Unknown Person",
        last_seen_location="City Library",
        age="34",
    )

    assert matches, "Expected at least one potential match"
    stored_matches = app.get_match_results()
    assert stored_matches, "Match results table should contain entries"
    facial_matches = [
        match for match in stored_matches if match["match_type"] == "facial"
    ]
    assert facial_matches, "Expected at least one facial match result"
    assert facial_matches[0]["source_report_id"] == source_id
    assert facial_matches[0]["candidate_report_id"] == candidate_id

    notifications = app.get_notifications(include_read=False)
    assert notifications, "Match pipeline should raise an alert"
    assert "Potential match detected" in notifications[0]["title"]


def test_notify_new_submission_creates_admin_alert(fresh_database):
    app.notify_new_submission(
        report_id=42,
        source="Public",
        tracking_code="TRACK1234",
        reporter_phone="9999999999",
    )
    notifications = app.get_notifications(include_read=True)
    assert notifications, "Submission should create a notification for admins"
    note = notifications[0]
    assert note["title"] == "New report received"
    assert "TRACK1234" in note["message"]

