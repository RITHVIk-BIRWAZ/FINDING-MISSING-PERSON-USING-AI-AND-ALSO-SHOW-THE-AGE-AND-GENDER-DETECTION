AI-Powered Missing Person Finder
This is a complete web application built with Streamlit that helps in reporting and finding missing persons. It leverages AI for age and gender detection from images, facial recognition for matching found persons against the database, and uses an SQLite database to manage records. The application features a public portal for submissions and a secure admin dashboard for managing all reports.

Features
Admin Dashboard: Secure login for administrators to manage all missing person reports.

Public Portal: Allows the general public to submit new reports and search by image.

AI-Powered Analysis: Automatically detects estimated age and gender from uploaded images using pre-trained CNN models.

Facial Recognition Matching: Upload a photo of a found person to find potential matches in the missing persons database using advanced facial recognition technology.

Database Management: All records are stored and managed in a local SQLite database (created automatically on first run).

Report Management: Admins can update a person's status to "Found" or delete reports entirely.

Dynamic Search: Admins can search for specific reports by name.

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
With your virtual environment active, install all the necessary Python packages with this single command:

pip install streamlit pandas opencv-python requests tqdm Pillow numpy face_recognition

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

Your default web browser will automatically open a new tab with the application running. You can now use the sidebar to switch between the Public Portal and the Admin Section.