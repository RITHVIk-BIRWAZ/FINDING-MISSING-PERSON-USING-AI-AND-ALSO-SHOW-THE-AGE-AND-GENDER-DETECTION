# AI-Powered Missing Person Finder

## Project Overview
This is a complete web application built with Streamlit that helps in reporting and finding missing persons. It leverages AI for age and gender detection from images, facial recognition for matching found persons against the database, and uses an SQLite database to manage records. The application features a public portal for submissions and a secure admin dashboard for managing all reports.

## Technologies Used
- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite
- **AI/ML**: OpenCV, DeepFace, Face Recognition
- **Other Libraries**: Pandas, NumPy, Pillow, Requests, Tqdm
- **Deployment**: Local or cloud-based (e.g., Streamlit Cloud)

## Usage
1. Run the application locally using the setup guide below.
2. Access the Public Portal to submit missing person reports or sightings.
3. Use the Admin Dashboard to manage reports, view matches, and monitor alerts.
4. AI features automatically detect age and gender from uploaded images and perform facial matching.

Features
- Admin Dashboard: Secure login, live metrics, geospatial heatmap, and alerts panel for investigators.
- Public Portal: Submit GPS-aware reports, review safety guidance, or upload a sighting photo for matching (tracking is now handled in the admin console).
- AI-Powered Analysis: Automatically estimates age/gender (DeepFace) and runs facial + contextual similarity checks to surface likely matches.
- Notification Center: Every public report or high-confidence match produces a real-time alert with audible/vibration cues plus sidebar badges until an admin reviews it.
- Matching Queue: Automated pipeline stores match evidence with audit logging so admins can mark items Under Review, Escalated, or Dismissed.
- Contact & Consent Handling: Reporters must share a reachable phone number and opt into being contacted, enabling rapid follow-ups.
- Database Management: SQLite schema stores location coordinates, consent flags, and tracking codes; background indexes keep searches fast.
- Report Management: Admins can triage cases, update statuses (Missing, Under Investigation, Found), and view masked contact details.

Step-by-Step Setup and Execution Guide
Follow these instructions carefully to get the application running on your local machine.

Step 1: Prerequisites
Ensure you have Python 3.8 or newer installed on your system. You can download it from the official Python website.

Step 2: Project Structure
Organize your project folder to match the following structure. This is crucial for the application to find all the necessary files.

missing_person_app/
├── app.py
├── config.ini
├── download_models.py
├── missing_persons.db    <-- Created automatically on first run
├── README.md
└── models/              <-- Create this empty folder initially, populated after Step 5
    ├── age_deploy.prototxt
    ├── age_net.caffemodel
    ├── gender_deploy.prototxt
    └── gender_net.caffemodel

app.py: The main Streamlit application code.

config.ini: Configuration file for admin credentials.

download_models.py: A script to automatically download the required AI models.

missing_persons.db: SQLite database file (created automatically).

models/: Directory containing the pre-trained AI models for age and gender detection.

Step 3: Set Up a Virtual Environment
This creates an isolated environment for the project's dependencies.

Open your terminal or command prompt.

Navigate into your main project folder (missing_person_app).

Create the virtual environment:

python -m venv venv

Activate the environment:

On Windows:

.\venv\Scripts\activate

On macOS and Linux:

source venv/bin/activate

You will know it's active when you see (venv) at the start of your terminal prompt.

Step 4: Install Required Libraries
With your virtual environment active, pull in the full dependency set (including the browser geolocation helper) with:

pip install -r requirements.txt

or, if you prefer a manual install:

pip install streamlit pandas opencv-python requests tqdm Pillow numpy face_recognition setuptools<81 deepface streamlit_js_eval

Step 5: Download the AI Models
This is a critical step. Run the downloader script to fetch the pre-trained models.

Make sure you are in the main project folder in your terminal.

Run the script:

python download_models.py

This will populate the models folder with the four required files. You only need to do this once.

Step 6: Configure Admin Credentials (Optional)
You can change the admin login details by editing the config.ini file:

[credentials]
username = new_admin_username
password = new_strong_password

Step 7: Run the Application
You are now ready to launch the web application.

Ensure your virtual environment is still active.

Run the following command in your terminal:

streamlit run app.py

Your default web browser will automatically open a new tab with the application running. You can now use the sidebar to switch between the Public Portal (Submit / Found Someone / Safety Tips) and the Admin Section (Dashboard, Manage Reports, Add Report, Find Matches, Alerts & Matches, Track Reports).

Testing Checklist (recommended before deployment)
- Public form validation: missing required fields, invalid phone number formats, GPS capture denied, consent unchecked.
- Tracking portal (admin only): valid vs invalid tracking IDs, records without coordinates.
- Notification flow: new public report triggers unread alert + audio/vibration popup, marking as read updates counters.
- Matching pipeline: duplicate photos produce facial matches (status auto-shifts to “Match Found - Await Review”), similar names/locations trigger contextual matches, dismissed items stay archived.
- Admin actions: status transitions (Missing → Under Investigation → Found), deletion warnings, map rendering for lat/lng edge cases (0 coordinates).
- Security: invalid admin credentials stay locked out, logout clears session, sensitive contact info only visible after login.