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
import cv2
import numpy as np
import face_recognition # New import for facial recognition
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

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
    conn = sqlite3.connect('missing_persons.db')
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
            date_reported DATETIME
        )
    ''')
    # Backward compatibility check for date_reported column
    c.execute("PRAGMA table_info(missing_persons)")
    columns = [info[1] for info in c.fetchall()]
    if 'date_reported' not in columns:
        c.execute("ALTER TABLE missing_persons ADD COLUMN date_reported DATETIME")
        c.execute("UPDATE missing_persons SET date_reported = CURRENT_TIMESTAMP WHERE date_reported IS NULL")

    conn.commit()
    conn.close()

def update_status(person_id, new_status):
    # ... (existing function) ...
    conn = sqlite3.connect('missing_persons.db')
    c = conn.cursor()
    c.execute("UPDATE missing_persons SET status = ? WHERE id = ?", (new_status, person_id))
    conn.commit()
    conn.close()

def delete_report(person_id):
    # ... (existing function) ...
    conn = sqlite3.connect('missing_persons.db')
    c = conn.cursor()
    c.execute("DELETE FROM missing_persons WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()

def get_stats():
    # ... (existing function) ...
    conn = sqlite3.connect('missing_persons.db')
    c = conn.cursor()
    missing_count = c.execute("SELECT COUNT(*) FROM missing_persons WHERE status = 'Missing'").fetchone()[0]
    found_count = c.execute("SELECT COUNT(*) FROM missing_persons WHERE status = 'Found'").fetchone()[0]
    conn.close()
    return missing_count, found_count

# --- UI Components ---
def report_missing_person_form():
    st.header("Report a Missing Person")
    with st.form("report_form", clear_on_submit=True):
        name = st.text_input("Full Name")
        last_seen = st.text_input("Last Seen Location")
        description = st.text_area("Additional Details (clothing, distinguishing features, etc.)")
        uploaded_image = st.file_uploader("Upload a Clear Image", type=['png', 'jpg', 'jpeg'])
        
        submit_button = st.form_submit_button("Submit Report")
        if submit_button:
            if name and last_seen and uploaded_image:
                image_bytes = uploaded_image.getvalue()
                age, gender = detect_age_gender(image_bytes)

                if not DEEPFACE_AVAILABLE: # Check if DeepFace is available
                    st.error("DeepFace library not available. Please install it with `pip install deepface`. Submission failed.")
                    return

                conn = sqlite3.connect('missing_persons.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO missing_persons (name, age, gender, last_seen_location, description, image, date_reported) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, age, gender, last_seen, description, image_bytes, datetime.datetime.now())
                )
                conn.commit()
                conn.close()
                st.success(f"Report for {name} submitted successfully.")
                st.info(f"AI Analysis: Estimated Age is {age}, Estimated Gender is {gender}.")
            else:
                st.warning("Please fill out all required fields and upload an image.")

def search_by_image_tab():
    # ... (existing function) ...
    st.header("Search for a Person by Image")
    st.info("This feature is a demonstration. A real implementation would use facial recognition to find a match.")
    uploaded_image = st.file_uploader("Upload image of the person you found", type=['png', 'jpg', 'jpeg'], key="search_uploader")
    if uploaded_image:
        st.image(uploaded_image, caption="Uploaded Image", width=300)
        if st.button("Search Database"):
            with st.spinner("Analyzing image and searching database..."):
                conn = sqlite3.connect('missing_persons.db')
                c = conn.cursor()
                c.execute("SELECT id, name, age, gender, last_seen_location, image, status FROM missing_persons WHERE status = 'Missing' ORDER BY RANDOM() LIMIT 1")
                result = c.fetchone()
                conn.close()
                if result:
                    st.success("Potential Match Found!")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Uploaded Image Analysis")
                        age, gender = detect_age_gender(uploaded_image.getvalue())
                        st.write(f"**Estimated Age:** {age}")
                        st.write(f"**Estimated Gender:** {gender}")
                    with col2:
                        st.subheader("Database Record")
                        st.write(f"**Name:** {result[1]}")
                        st.write(f"**Status:** {result[6]}")
                        st.write(f"**Reported Age:** {result[2]}")
                        db_image = Image.open(io.BytesIO(result[5]))
                        st.image(db_image, caption=f"Image of {result[1]}")
                else:
                    st.warning("No potential matches found in the active missing persons database.")

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
                conn = sqlite3.connect('missing_persons.db')
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
    
    # --- NEW: Added "Find Matches" to the admin menu ---
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Manage Reports", "Add New Report", "Find Matches"])

    if menu == "Dashboard":
        # ... (existing code) ...
        st.header("Admin Dashboard")
        missing_count, found_count = get_stats()
        col1, col2 = st.columns(2)
        col1.metric("Active Missing Reports", f"{missing_count}")
        col2.metric("Persons Found", f"{found_count}")

    elif menu == "Manage Reports":
        # ... (existing code) ...
        st.header("Manage All Reports")
        conn = sqlite3.connect('missing_persons.db')
        df = pd.read_sql_query("SELECT id, name, age, gender, status, date_reported FROM missing_persons ORDER BY date_reported DESC", conn)
        conn.close()

        if not df.empty:
            search_name = st.text_input("Search by Name")
            filtered_df = df[df['name'].str.contains(search_name, case=False)]
            for index, row in filtered_df.iterrows():
                with st.expander(f"{row['name']} (Status: {row['status']})"):
                    conn = sqlite3.connect('missing_persons.db')
                    full_details = conn.execute("SELECT description, image FROM missing_persons WHERE id = ?", (int(row['id']),)).fetchone()
                    conn.close()
                    col1, col2 = st.columns([1, 2])
                    if full_details and full_details[1]:
                        col1.image(Image.open(io.BytesIO(full_details[1])))
                    col2.write(f"**ID:** {row['id']}")
                    col2.write(f"**Reported Age:** {row['age']}")
                    col2.write(f"**Gender:** {row['gender']}")
                    col2.write(f"**Date Reported:** {row['date_reported']}")
                    if row['status'] == 'Missing':
                        if st.button("Mark as Found", key=f"found_{row['id']}"):
                            update_status(row['id'], 'Found')
                            st.success(f"{row['name']} marked as Found.")
                            st.rerun()
                    if st.button("Delete Report", key=f"delete_{row['id']}"):
                        delete_report(row['id'])
                        st.warning(f"Report for {row['name']} deleted.")
                        st.rerun()
        else:
            st.info("No reports in the database.")

    elif menu == "Add New Report":
        report_missing_person_form()
    
    # --- NEW: Logic to show the matching page ---
    elif menu == "Find Matches":
        find_matches_page()


def public_portal():
    # ... (existing function) ...
    st.sidebar.title("Public Menu")
    menu = st.sidebar.radio("Navigation", ["Submit a Report"])
    if menu == "Submit a Report":
        report_missing_person_form()

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
