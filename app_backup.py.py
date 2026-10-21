import os
import sqlite3
import requests
import re

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from dotenv import load_dotenv


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# GLOBAL JOB CACHE
# =========================================================

JOB_CACHE = []


# =========================================================
# OPENWEB NINJA JOB API CONFIGURATION
# =========================================================

OPENWEBNINJA_API_KEY = os.getenv(
    "OPENWEBNINJA_API_KEY",
    ""
).strip()

JOB_API_URL = (
    "https://api.openwebninja.com/jsearch/search-v2"
)


# =========================================================
# CHECK API KEY
# =========================================================

if OPENWEBNINJA_API_KEY:
    print("OpenWeb Ninja API Key: FOUND")
else:
    print("WARNING: OPENWEBNINJA_API_KEY NOT FOUND")


# =========================================================
# JOB SEARCH FUNCTION
# =========================================================

def search_jobs(query):

    print("=" * 50)
    print("OPENWEB NINJA JOB SEARCH")
    print("QUERY:", query)
    print("URL:", JOB_API_URL)
    print("=" * 50)

    if not OPENWEBNINJA_API_KEY:

        print("ERROR: API KEY NOT FOUND")

        return []

    headers = {
        "x-api-key": OPENWEBNINJA_API_KEY,
        "Content-Type": "application/json"
    }

    params = {
        "query": query,
        "page": 1,
        "num_pages": 1,
        "country": "in",
        "language": "en"
    }

    try:

        response = requests.get(
            JOB_API_URL,
            headers=headers,
            params=params,
            timeout=30
        )

        print("STATUS:", response.status_code)

        # -------------------------------------------------
        # API ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print("API ERROR:")
            print(response.text)

            return []

        # -------------------------------------------------
        # JSON RESPONSE
        # -------------------------------------------------

        result = response.json()

        print(
            "API STATUS:",
            result.get("status")
        )

        # -------------------------------------------------
        # GET DATA
        # -------------------------------------------------

        data = result.get(
            "data",
            {}
        )

        if isinstance(data, dict):

            jobs = data.get(
                "jobs",
                []
            )

        else:

            jobs = []

        if not isinstance(jobs, list):

            jobs = []

        print(
            "NUMBER OF JOBS:",
            len(jobs)
        )

        # -------------------------------------------------
        # FORMAT JOBS
        # -------------------------------------------------

        formatted_jobs = []

        for job in jobs:

            if not isinstance(job, dict):
                continue

            formatted_job = {

                "job_id": job.get(
                    "job_id",
                    ""
                ),

                "title": job.get(
                    "job_title",
                    "N/A"
                ),

                "company": job.get(
                    "employer_name",
                    "N/A"
                ),

                "location": job.get(
                    "job_location",
                    "N/A"
                ),

                "employment_type": job.get(
                    "job_employment_type",
                    "N/A"
                ),

                "publisher": job.get(
                    "job_publisher",
                    "N/A"
                ),

                "description": job.get(
                    "job_description",
                    "No description available"
                ),

                "apply_link": job.get(
                    "job_apply_link",
                    "#"
                ) or "#",

                "posted": job.get(
                    "job_posted_at",
                    "N/A"
                ),

                "salary": job.get(
                    "job_salary_string",
                    "Not specified"
                ) or "Not specified",

                "remote": job.get(
                    "job_is_remote",
                    False
                ),

                "city": job.get(
                    "job_city",
                    ""
                ),

                "state": job.get(
                    "job_state",
                    ""
                ),

                "country": job.get(
                    "job_country",
                    "India"
                ),

                "min_salary": job.get(
                    "job_min_salary",
                    None
                ),

                "max_salary": job.get(
                    "job_max_salary",
                    None
                ),

                "salary_period": job.get(
                    "job_salary_period",
                    ""
                )

            }

            formatted_jobs.append(
                formatted_job
            )

        print("=" * 50)
        print(
            "FORMATTED JOBS:",
            len(formatted_jobs)
        )
        print("=" * 50)

        return formatted_jobs

    except requests.exceptions.RequestException as e:

        print(
            "REQUEST ERROR:",
            e
        )

        return []

    except ValueError as e:

        print(
            "JSON ERROR:",
            e
        )

        return []

    except Exception as e:

        print(
            "UNEXPECTED ERROR:",
            e
        )

        return []


# =========================================================
# RESUME PARSER IMPORTS
# =========================================================

from resume_parser import (
    extract_text,
    extract_name,
    extract_email,
    extract_phone,
    extract_skills,
    extract_education,
    extract_projects,
    calculate_ats_score,
    generate_suggestions,
    find_missing_skills,
    generate_enhanced_resume
)


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = "secret123"


# =========================================================
# UPLOAD FOLDER
# =========================================================

BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================================================
# SQLITE DATABASE
# =========================================================

app.config[
    "SQLALCHEMY_DATABASE_URI"
] = "sqlite:///users.db"

app.config[
    "SQLALCHEMY_TRACK_MODIFICATIONS"
] = False

db = SQLAlchemy(app)


# =========================================================
# DATABASE MODEL
# =========================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    fullname = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )


# =========================================================
# CREATE DATABASE
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# HOME / INDEX
# =========================================================

@app.route("/")
def index():

    return redirect(
        url_for("login")
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        fullname = request.form.get(
            "fullname",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            not fullname
            or not email
            or not password
        ):

            flash(
                "Please fill all fields."
            )

            return redirect(
                url_for("register")
            )

        user = User.query.filter_by(
            email=email
        ).first()

        if user:

            flash(
                "Email already registered."
            )

            return redirect(
                url_for("register")
            )

        new_user = User(
            fullname=fullname,
            email=email,
            password=password
        )

        db.session.add(
            new_user
        )

        db.session.commit()

        flash(
            "Registration Successful!"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:

            session["user"] = (
                user.fullname
            )

            session["user_id"] = (
                user.id
            )

            return redirect(
                url_for("home")
            )

        flash(
            "Invalid Email or Password."
        )

    return render_template(
        "login.html"
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot_password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        user = User.query.filter_by(
            email=email
        ).first()

        if user:

            session["reset_email"] = email

            return redirect(
                url_for("reset_password")
            )

        flash(
            "Email not registered."
        )

    return render_template(
        "forgot_password.html"
    )


# =========================================================
# RESET PASSWORD
# =========================================================

@app.route(
    "/reset_password",
    methods=["GET", "POST"]
)
def reset_password():

    if "reset_email" not in session:

        return redirect(
            url_for("forgot_password")
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if password != confirm_password:

            flash(
                "Passwords do not match."
            )

            return redirect(
                url_for("reset_password")
            )

        email = session[
            "reset_email"
        ]

        user = User.query.filter_by(
            email=email
        ).first()

        if user:

            user.password = password

            db.session.commit()

            session.pop(
                "reset_email",
                None
            )

            flash(
                "Password reset successfully."
            )

            return redirect(
                url_for("login")
            )

    return render_template(
        "reset_password.html"
    )


# =========================================================
# DASHBOARD / HOME
# =========================================================

@app.route("/home")
def home():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "dashboard.html",
        name=session["user"]
    )


# =========================================================
# RESUME UPLOAD
# =========================================================

@app.route(
    "/upload",
    methods=["GET", "POST"]
)
def upload():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        if "resume" not in request.files:

            flash(
                "No file selected."
            )

            return redirect(
                url_for("upload")
            )

        file = request.files[
            "resume"
        ]

        if file.filename == "":

            flash(
                "Please choose a file."
            )

            return redirect(
                url_for("upload")
            )

        filename = secure_filename(
            file.filename
        )

        allowed_extensions = [
            ".pdf",
            ".docx"
        ]

        extension = os.path.splitext(
            filename
        )[1].lower()

        if extension not in allowed_extensions:

            flash(
                "Only PDF and DOCX files are allowed."
            )

            return redirect(
                url_for("upload")
            )

        save_path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        file.save(
            save_path
        )

        print(
            "Resume saved at:",
            save_path
        )

        flash(
            "Resume Uploaded Successfully!"
        )

        return redirect(
            url_for("upload")
        )

    return render_template(
        "upload.html"
    )


# =========================================================
# RESUME ANALYSIS
# =========================================================

@app.route("/analyze")
def analyze():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    role = request.args.get(
        "role",
        "Software Developer"
    ).strip()

    if not role:

        role = "Software Developer"

    session["role"] = role

    files = []

    for filename in os.listdir(
        UPLOAD_FOLDER
    ):

        extension = os.path.splitext(
            filename
        )[1].lower()

        if (
            extension in [
                ".pdf",
                ".docx"
            ]
            and filename.lower()
            != "enhanced_resume.docx"
        ):

            files.append(
                filename
            )

    if len(files) == 0:

        return "No Resume Uploaded"

    latest_filename = max(
        files,
        key=lambda filename:
        os.path.getmtime(
            os.path.join(
                UPLOAD_FOLDER,
                filename
            )
        )
    )

    latest_file = os.path.join(
        UPLOAD_FOLDER,
        latest_filename
    )

    print(
        "Analyzing Resume:",
        latest_file
    )

    resume_text = extract_text(
        latest_file
    )

    name = extract_name(
        resume_text
    )

    email = extract_email(
        resume_text
    )

    phone = extract_phone(
        resume_text
    )

    skills = extract_skills(
        resume_text
    )

    education = extract_education(
        resume_text
    )

    projects = extract_projects(
        resume_text
    )

    missing_skills = find_missing_skills(
        role,
        skills
    )

    ats_score = calculate_ats_score(
        name,
        email,
        phone,
        skills,
        education,
        projects,
        resume_text,
        role
    )

    suggestions = generate_suggestions(
        email,
        phone,
        skills,
        education,
        projects
    )

    print("=" * 40)
    print("RESUME ANALYSIS")
    print("=" * 40)
    print("Name:", name)
    print("Email:", email)
    print("Phone:", phone)
    print("Skills:", skills)
    print("Education:", education)
    print("Projects:", projects)
    print("Role:", role)
    print(
        "Missing Skills:",
        missing_skills
    )
    print(
        "ATS Score:",
        ats_score
    )
    print("=" * 40)

    return render_template(
        "analyze.html",
        name=name,
        email=email,
        phone=phone,
        skills=skills,
        education=education,
        projects=projects,
        ats_score=ats_score,
        suggestions=suggestions,
        role=role,
        resume_text=resume_text,
        missing_skills=missing_skills
    )


# =========================================================
# ENHANCE RESUME
# =========================================================

@app.route("/enhance")
def enhance_resume():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    files = []

    for filename in os.listdir(
        UPLOAD_FOLDER
    ):

        extension = os.path.splitext(
            filename
        )[1].lower()

        if (
            extension in [
                ".pdf",
                ".docx"
            ]
            and filename.lower()
            != "enhanced_resume.docx"
        ):

            files.append(
                filename
            )

    if len(files) == 0:

        return "No Resume Uploaded"

    latest_filename = max(
        files,
        key=lambda filename:
        os.path.getmtime(
            os.path.join(
                UPLOAD_FOLDER,
                filename
            )
        )
    )

    latest_file = os.path.join(
        UPLOAD_FOLDER,
        latest_filename
    )

    print("=" * 40)
    print(
        "ENHANCING RESUME:",
        latest_file
    )
    print("=" * 40)

    resume_text = extract_text(
        latest_file
    )

    name = extract_name(
        resume_text
    )

    email = extract_email(
        resume_text
    )

    phone = extract_phone(
        resume_text
    )

    skills = extract_skills(
        resume_text
    )

    education = extract_education(
        resume_text
    )

    projects = extract_projects(
        resume_text
    )

    role = session.get(
        "role",
        "Software Developer"
    )

    # -----------------------------------------------------
    # ORIGINAL ATS SCORE
    # -----------------------------------------------------

    try:

        original_score_data = (
            calculate_ats_score(
                name,
                email,
                phone,
                skills,
                education,
                projects,
                resume_text,
                role
            )
        )

        if isinstance(
            original_score_data,
            dict
        ):

            original_ats_score = (
                original_score_data.get(
                    "total",
                    0
                )
            )

        else:

            original_ats_score = (
                original_score_data
            )

    except Exception as e:

        print(
            "Original ATS Score Error:",
            e
        )

        original_ats_score = 0

    # -----------------------------------------------------
    # ENHANCED RESUME
    # -----------------------------------------------------

    enhanced_filename = (
        "enhanced_resume.docx"
    )

    enhanced_path = os.path.join(
        UPLOAD_FOLDER,
        enhanced_filename
    )

    generate_enhanced_resume(
        enhanced_path,
        name,
        email,
        phone,
        skills,
        education,
        projects,
        role
    )

    print(
        "Enhanced Resume Created:",
        enhanced_path
    )

    # -----------------------------------------------------
    # EXTRACT ENHANCED RESUME
    # -----------------------------------------------------

    enhanced_text = extract_text(
        enhanced_path
    )

    enhanced_name = extract_name(
        enhanced_text
    )

    enhanced_email = extract_email(
        enhanced_text
    )

    enhanced_phone = extract_phone(
        enhanced_text
    )

    enhanced_skills = extract_skills(
        enhanced_text
    )

    enhanced_education = (
        extract_education(
            enhanced_text
        )
    )

    enhanced_projects = (
        extract_projects(
            enhanced_text
        )
    )

    # -----------------------------------------------------
    # ENHANCED ATS SCORE
    # -----------------------------------------------------

    try:

        enhanced_score_data = (
            calculate_ats_score(
                enhanced_name,
                enhanced_email,
                enhanced_phone,
                enhanced_skills,
                enhanced_education,
                enhanced_projects,
                enhanced_text,
                role
            )
        )

        if isinstance(
            enhanced_score_data,
            dict
        ):

            enhanced_ats_score = (
                enhanced_score_data.get(
                    "total",
                    0
                )
            )

        else:

            enhanced_ats_score = (
                enhanced_score_data
            )

    except Exception as e:

        print(
            "Enhanced ATS Score Error:",
            e
        )

        enhanced_ats_score = (
            original_ats_score
        )

    print("--------------------------------")
    print(
        "Original ATS Score:",
        original_ats_score
    )
    print(
        "Enhanced ATS Score:",
        enhanced_ats_score
    )
    print("--------------------------------")

    return render_template(
        "enhance.html",
        name=name,
        email=email,
        phone=phone,
        skills=skills,
        education=education,
        projects=projects,
        role=role,
        original_ats_score=original_ats_score,
        enhanced_ats_score=enhanced_ats_score,
        enhanced_filename=enhanced_filename
    )


# =========================================================
# DOWNLOAD ENHANCED RESUME
# =========================================================

@app.route("/download-enhanced")
def download_enhanced():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    enhanced_path = os.path.join(
        UPLOAD_FOLDER,
        "enhanced_resume.docx"
    )

    if not os.path.exists(
        enhanced_path
    ):

        return "Enhanced Resume not found."

    return send_file(
        enhanced_path,
        as_attachment=True,
        download_name="Enhanced_Resume.docx"
    )


# =========================================================
# AI JOB SEARCH / CHATBOT
# =========================================================

@app.route(
    "/chatbot",
    methods=["GET", "POST"]
)
def chatbot():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    global JOB_CACHE

    jobs = []

    response = ""

    error_message = ""

    # -----------------------------------------------------
    # POST REQUEST
    # -----------------------------------------------------

    if request.method == "POST":

        query = request.form.get(
            "message",
            ""
        ).strip()

        if not query:

            error_message = (
                "Please enter a job search query."
            )

            return render_template(
                "chatbot.html",
                jobs=[],
                response="",
                error_message=error_message
            )

        print("=" * 50)
        print(
            "JOB SEARCH QUERY:",
            query
        )
        print("=" * 50)

        # -------------------------------------------------
        # SEARCH JOBS
        # -------------------------------------------------

        jobs = search_jobs(
            query
        )

        # -------------------------------------------------
        # SAVE JOBS
        # -------------------------------------------------

        JOB_CACHE = jobs.copy()

        print("=" * 50)
        print(
            "FINAL JOB COUNT:",
            len(JOB_CACHE)
        )
        print("=" * 50)

        # -------------------------------------------------
        # JOBS FOUND
        # -------------------------------------------------

        if jobs:

            response = (
                f"{len(jobs)} jobs found "
                f"for: {query}"
            )

        # -------------------------------------------------
        # NO JOBS
        # -------------------------------------------------

        else:

            error_message = (
                "No jobs found. Try searches like "
                "'Python Developer in Hyderabad', "
                "'Data Analyst in Bangalore', "
                "'AI Engineer in Pune'."
            )

    # -----------------------------------------------------
    # GET REQUEST
    # -----------------------------------------------------

    else:

        jobs = JOB_CACHE

    # -----------------------------------------------------
    # RENDER CHATBOT
    # -----------------------------------------------------

    return render_template(
        "chatbot.html",
        jobs=jobs,
        response=response,
        error_message=error_message
    )


# =========================================================
# JOB DETAILS
# =========================================================

@app.route(
    "/job/<int:job_index>"
)
def job_details(job_index):

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    global JOB_CACHE

    print("=" * 50)
    print("JOB DETAILS REQUEST")
    print(
        "JOB INDEX:",
        job_index
    )
    print(
        "CACHE SIZE:",
        len(JOB_CACHE)
    )
    print("=" * 50)

    # -----------------------------------------------------
    # NO JOBS
    # -----------------------------------------------------

    if not JOB_CACHE:

        flash(
            "Job results expired. "
            "Please search for jobs again."
        )

        return redirect(
            url_for("chatbot")
        )

    # -----------------------------------------------------
    # INVALID JOB
    # -----------------------------------------------------

    if (
        job_index < 0
        or job_index >= len(JOB_CACHE)
    ):

        flash(
            "Invalid job selected."
        )

        return redirect(
            url_for("chatbot")
        )

    # -----------------------------------------------------
    # SELECT JOB
    # -----------------------------------------------------

    job = JOB_CACHE[
        job_index
    ]

    print("SELECTED JOB:")
    print(
        "TITLE:",
        job.get("title")
    )
    print(
        "COMPANY:",
        job.get("company")
    )
    print(
        "LOCATION:",
        job.get("location")
    )
    print(
        "APPLY LINK:",
        job.get("apply_link")
    )
    print("=" * 50)

    return render_template(
        "job_details.html",
        job=job
    )


# =========================================================
# ROLE BASED INTERVIEW QUESTIONS
# =========================================================

def get_interview_questions(role):

    role = role.lower()

    # -----------------------------------------------------
    # PYTHON DEVELOPER
    # -----------------------------------------------------

    if "python" in role:

        return [

            "Tell me about yourself.",

            "What are your strongest Python skills?",

            "What is the difference between a list and a tuple in Python?",

            "What are functions in Python?",

            "What is exception handling in Python?",

            "What is OOP in Python?",

            "What is Flask and why is it used?",

            "Explain one Python project you have worked on.",

            "How is Python used in Machine Learning?",

            "Where do you see yourself in the next five years?"

        ]

    # -----------------------------------------------------
    # AI ENGINEER
    # -----------------------------------------------------

    elif "ai" in role:

        return [

            "Tell me about yourself.",

            "Why are you interested in Artificial Intelligence?",

            "What is Machine Learning?",

            "What is the difference between supervised and unsupervised learning?",

            "What is overfitting?",

            "What is a classification algorithm?",

            "What is the difference between AI and Machine Learning?",

            "Explain one AI or Machine Learning project you have worked on.",

            "Which Python libraries are commonly used in Machine Learning?",

            "Where do you see yourself in the next five years?"

        ]

    # -----------------------------------------------------
    # DATA ANALYST
    # -----------------------------------------------------

    elif "data" in role:

        return [

            "Tell me about yourself.",

            "What are your strongest data analysis skills?",

            "What is SQL and why is it important?",

            "What is the difference between SQL and NoSQL?",

            "What is data preprocessing?",

            "What is the difference between mean, median and mode?",

            "What is Pandas in Python?",

            "Explain one data-related project you have worked on.",

            "What is data visualization?",

            "Where do you see yourself in the next five years?"

        ]

    # -----------------------------------------------------
    # FULL STACK DEVELOPER
    # -----------------------------------------------------

    elif "full stack" in role:

        return [

            "Tell me about yourself.",

            "What are your strongest web development skills?",

            "What is HTML and why is it used?",

            "What is CSS?",

            "What is JavaScript?",

            "What is React?",

            "What is Node.js?",

            "Explain one web development project you have worked on.",

            "What is the difference between frontend and backend development?",

            "Where do you see yourself in the next five years?"

        ]

    # -----------------------------------------------------
    # SOFTWARE DEVELOPER
    # -----------------------------------------------------

    else:

        return [

            "Tell me about yourself.",

            "Why do you want to become a Software Developer?",

            "What are your strongest technical skills?",

            "Explain one project you have worked on.",

            "What is the difference between SQL and NoSQL?",

            "What is OOP? Explain its main concepts.",

            "What is the difference between a list and a tuple in Python?",

            "What is Flask and why is it used?",

            "What is Machine Learning?",

            "Where do you see yourself in the next five years?"

        ]


# =========================================================
# AI INTERVIEW COACH
# =========================================================

@app.route(
    "/interview",
    methods=["GET", "POST"]
)
def interview():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    # -----------------------------------------------------
    # GET SELECTED ROLE
    # -----------------------------------------------------

    role = session.get(
        "role",
        "Software Developer"
    )

    # -----------------------------------------------------
    # GET QUESTIONS
    # -----------------------------------------------------

    questions = get_interview_questions(
        role
    )

    total_questions = len(
        questions
    )

    # -----------------------------------------------------
    # START NEW INTERVIEW
    # -----------------------------------------------------

    if request.args.get("new") == "1":

        session["interview_scores"] = []

        session["interview_answers"] = []

        session["interview_completed"] = False

        session.modified = True

        return redirect(
            url_for("interview")
        )

    # -----------------------------------------------------
    # AUTOMATICALLY START NEW INTERVIEW
    # AFTER PREVIOUS INTERVIEW COMPLETED
    # -----------------------------------------------------

    if (
        request.method == "GET"
        and "question" not in request.args
        and session.get(
            "interview_completed",
            False
        )
    ):

        session["interview_scores"] = []

        session["interview_answers"] = []

        session["interview_completed"] = False

        session.modified = True

    # -----------------------------------------------------
    # INITIALIZE SESSION
    # -----------------------------------------------------

    if "interview_scores" not in session:

        session["interview_scores"] = []

    if "interview_answers" not in session:

        session["interview_answers"] = []

    # -----------------------------------------------------
    # QUESTION NUMBER
    # -----------------------------------------------------

    question_number = request.args.get(
        "question",
        0,
        type=int
    )

    # -----------------------------------------------------
    # SAFETY CHECK
    # -----------------------------------------------------

    if question_number < 0:

        question_number = 0

    if question_number >= total_questions:

        question_number = 0

    # -----------------------------------------------------
    # CURRENT QUESTION
    # -----------------------------------------------------

    current_question = questions[
        question_number
    ]

    # =====================================================
    # POST - USER SUBMITS ANSWER
    # =====================================================

    if request.method == "POST":

        answer = request.form.get(
            "answer",
            ""
        ).strip()

        # -------------------------------------------------
        # EMPTY ANSWER
        # -------------------------------------------------

        if not answer:

            return render_template(
                "interview.html",
                question=current_question,
                question_number=question_number,
                total_questions=total_questions,
                error="Please enter your answer.",
                role=role
            )

        # -------------------------------------------------
        # ANSWER EVALUATION
        # -------------------------------------------------

        answer_length = len(
            answer.split()
        )

        if answer_length >= 50:

            score = 9

            feedback = (
                "Excellent answer. Your response is detailed "
                "and demonstrates good understanding."
            )

        elif answer_length >= 25:

            score = 7

            feedback = (
                "Good answer. Try adding more technical details "
                "and a practical example."
            )

        elif answer_length >= 10:

            score = 5

            feedback = (
                "Your answer is understandable, but it needs "
                "more explanation and examples."
            )

        else:

            score = 3

            feedback = (
                "Your answer is too short. Try explaining the "
                "concept clearly with an example."
            )

        # -------------------------------------------------
        # GET EXISTING SESSION DATA
        # -------------------------------------------------

        scores = session.get(
            "interview_scores",
            []
        )

        answers = session.get(
            "interview_answers",
            []
        )

        # -------------------------------------------------
        # MAKE SCORES LIST CORRECT SIZE
        # -------------------------------------------------

        while len(scores) < total_questions:

            scores.append(0)

        while len(answers) < total_questions:

            answers.append("")

        # -------------------------------------------------
        # SAVE CURRENT QUESTION SCORE
        # -------------------------------------------------

        scores[
            question_number
        ] = score

        answers[
            question_number
        ] = answer

        # -------------------------------------------------
        # SAVE SESSION
        # -------------------------------------------------

        session[
            "interview_scores"
        ] = scores

        session[
            "interview_answers"
        ] = answers

        session.modified = True

        # -------------------------------------------------
        # NEXT QUESTION
        # -------------------------------------------------

        next_question = (
            question_number + 1
        )

        # =================================================
        # INTERVIEW COMPLETE
        # =================================================

        if next_question >= total_questions:

            # ---------------------------------------------
            # GET ALL CURRENT SCORES
            # ---------------------------------------------

            final_scores = scores[
                :total_questions
            ]

            # ---------------------------------------------
            # SAFETY:
            # ONLY SCORES 1-10
            # ---------------------------------------------

            cleaned_scores = []

            for score_value in final_scores:

                try:

                    numeric_score = int(
                        score_value
                    )

                except (
                    ValueError,
                    TypeError
                ):

                    numeric_score = 0

                numeric_score = max(
                    0,
                    min(
                        numeric_score,
                        10
                    )
                )

                cleaned_scores.append(
                    numeric_score
                )

            # ---------------------------------------------
            # TOTAL SCORE
            # ---------------------------------------------

            total_score = sum(
                cleaned_scores
            )

            # ---------------------------------------------
            # MAXIMUM SCORE
            # ---------------------------------------------

            maximum_score = (
                total_questions * 10
            )

            # ---------------------------------------------
            # FINAL PERCENTAGE
            # ---------------------------------------------

            if maximum_score > 0:

                final_score = round(
                    (
                        total_score
                        / maximum_score
                    ) * 100
                )

            else:

                final_score = 0

            # ---------------------------------------------
            # FINAL SAFETY CHECK
            # ---------------------------------------------

            final_score = max(
                0,
                min(
                    final_score,
                    100
                )
            )

            # ---------------------------------------------
            # SAVE FINAL SCORES
            # ---------------------------------------------

            session[
                "interview_scores"
            ] = cleaned_scores

            session[
                "interview_completed"
            ] = True

            session.modified = True

            # ---------------------------------------------
            # PRINT RESULT
            # ---------------------------------------------

            print("--------------------------------")
            print("INTERVIEW COMPLETED")
            print(
                "TOTAL QUESTIONS:",
                total_questions
            )
            print(
                "SCORES:",
                cleaned_scores
            )
            print(
                "TOTAL SCORE:",
                total_score
            )
            print(
                "MAXIMUM SCORE:",
                maximum_score
            )
            print(
                "FINAL SCORE:",
                final_score
            )
            print("--------------------------------")

            # ---------------------------------------------
            # PERFORMANCE
            # ---------------------------------------------

            if final_score >= 90:

                performance = "Excellent"

                final_feedback = (
                    "Excellent interview performance. "
                    "You demonstrated strong technical "
                    "knowledge and good communication."
                )

            elif final_score >= 75:

                performance = "Good"

                final_feedback = (
                    "Good interview performance. "
                    "You have a solid technical foundation. "
                    "Try to provide more practical examples."
                )

            elif final_score >= 60:

                performance = "Average"

                final_feedback = (
                    "Your performance is average. "
                    "Improve your technical explanations "
                    "and practice more interview questions."
                )

            else:

                performance = "Needs Improvement"

                final_feedback = (
                    "You need more interview practice. "
                    "Focus on technical concepts and "
                    "provide clearer, detailed answers."
                )

            # ---------------------------------------------
            # FINAL RESULT PAGE
            # ---------------------------------------------

            return render_template(
                "interview_result.html",
                final_score=final_score,
                performance=performance,
                feedback=final_feedback,
                scores=cleaned_scores,
                total_questions=total_questions,
                role=role
            )

        # =================================================
        # SHOW FEEDBACK
        # =================================================

        return render_template(
            "interview_feedback.html",
            score=score,
            feedback=feedback,
            next_question=next_question,
            question_number=question_number,
            total_questions=total_questions,
            role=role
        )

    # =====================================================
    # GET - SHOW CURRENT QUESTION
    # =====================================================

    return render_template(
        "interview.html",
        question=current_question,
        question_number=question_number,
        total_questions=total_questions,
        error="",
        role=role
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )