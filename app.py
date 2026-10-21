import os
import requests

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

load_dotenv(override=True)


# =========================================================
# GLOBAL JOB CACHE
# =========================================================

JOB_CACHE = []

# Interview data is kept server-side instead of inside Flask's
# client-side session cookie. This prevents the session cookie from
# exceeding the browser's ~4 KB cookie limit.
INTERVIEW_DATA = {}


# =========================================================
# API CONFIGURATION
# =========================================================

OPENWEBNINJA_API_KEY = os.getenv(
    "OPENWEBNINJA_API_KEY",
    ""
).strip()

JOB_API_URL = (
    "https://api.openwebninja.com/jsearch/search-v2"
)


# =========================================================
# GEMINI CONFIGURATION
# =========================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
).strip()

# Primary model can be changed in .env.
# If the primary model is temporarily busy, the code
# automatically tries the fallback models below.
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
).strip() or "gemini-3.8-flash"

GEMINI_FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash"
]

# Remove duplicates while preserving order.
GEMINI_FALLBACK_MODELS = list(
    dict.fromkeys(GEMINI_FALLBACK_MODELS)
)

GEMINI_API_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
)

GEMINI_API_URL = (
    f"{GEMINI_API_BASE_URL}/{GEMINI_MODEL}:generateContent"
)


# =========================================================
# API STATUS
# =========================================================

print("=" * 60)
print("API CONFIGURATION")
print("=" * 60)

if OPENWEBNINJA_API_KEY:
    print("OpenWeb Ninja API Key: FOUND")
else:
    print("WARNING: OPENWEBNINJA_API_KEY NOT FOUND")

if GEMINI_API_KEY:
    print("Gemini API Key: FOUND")
else:
    print("WARNING: GEMINI_API_KEY NOT FOUND")

print("Gemini Model:", GEMINI_MODEL)
print("Gemini URL:", GEMINI_API_URL)

print("=" * 60)


# =========================================================
# JOB SEARCH
# =========================================================



def search_jobs(query, country_code=None):
    print("\n========== WORLDWIDE JOB SEARCH ==========")
    print("JOB SEARCH QUERY:", query)
    print("SELECTED COUNTRY:", country_code or "Worldwide")

    if not OPENWEBNINJA_API_KEY:
        print("ERROR: OPENWEBNINJA_API_KEY is missing in .env")
        return []

    # Supported countries
    countries = {
        "India": "in",
        "United Kingdom": "gb",
        "United States": "us",
        "Canada": "ca",
        "Australia": "au",
        "Germany": "de",
        "Singapore": "sg",
        "United Arab Emirates": "ae"
    }

    # If a country is selected, search only that country.
    # If no country is selected, search all configured countries.
    if country_code:
        countries_to_search = {
            name: code
            for name, code in countries.items()
            if code == country_code
        }

        if not countries_to_search:
            print("ERROR: Unsupported country:", country_code)
            return []
    else:
        countries_to_search = countries

    headers = {
        "x-api-key": OPENWEBNINJA_API_KEY,
        "Content-Type": "application/json"
    }

    all_jobs = []
    seen_jobs = set()

    for country_name, current_country_code in countries_to_search.items():

        try:
            params = {
                "query": query,
                "page": 1,
                "num_pages": 1,
                "country": current_country_code,
                "language": "en"
            }

            print(f"Searching jobs in {country_name}...")

            response = requests.get(
                JOB_API_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            print(
                f"{country_name} API STATUS:",
                response.status_code
            )

            if response.status_code != 200:
                print(
                    f"Error for {country_name}:",
                    response.text[:300]
                )
                continue

            result = response.json()
            data = result.get("data", {})

            if isinstance(data, dict):
                jobs = data.get("jobs", [])
            elif isinstance(data, list):
                jobs = data
            else:
                jobs = []

            if not isinstance(jobs, list):
                continue

            for job in jobs:

                if not isinstance(job, dict):
                    continue

                title = job.get("job_title", "")
                company = job.get("employer_name", "")
                location = job.get("job_location", "")

                apply_link = (
                    job.get("job_apply_link", "")
                    or job.get("job_google_link", "")
                )

                job_id = (
                    job.get("job_id")
                    or apply_link
                    or (
                        f"{title}|{company}|{location}|"
                        f"{current_country_code}"
                    )
                )

                if job_id in seen_jobs:
                    continue

                seen_jobs.add(job_id)

                formatted_job = {
                    "job_id": job_id,
                    "title": title or "Job Title Not Available",
                    "company": company or "Company Not Available",
                    "location": location or country_name,
                    "employment_type": job.get(
                        "job_employment_type", ""
                    ),
                    "publisher": job.get("job_publisher", ""),
                    "description": job.get("job_description", ""),
                    "apply_link": apply_link,
                    "posted": job.get(
                        "job_posted_at_datetime_utc", ""
                    ),
                    "salary": job.get("job_salary", ""),
                    "remote": job.get("job_is_remote", False),
                    "city": job.get("job_city", ""),
                    "state": job.get("job_state", ""),
                    "country": (
                        job.get("job_country") or country_name
                    ),
                    "min_salary": job.get(
                        "job_min_salary", ""
                    ),
                    "max_salary": job.get(
                        "job_max_salary", ""
                    ),
                    "salary_period": job.get(
                        "job_salary_period", ""
                    )
                }

                all_jobs.append(formatted_job)

        except requests.exceptions.RequestException as e:
            print(f"Network error for {country_name}: {e}")
            continue

        except (ValueError, TypeError) as e:
            print(f"Response error for {country_name}: {e}")
            continue

        except Exception as e:
            print(f"Unexpected error for {country_name}: {e}")
            continue

    print("TOTAL JOBS FOUND:", len(all_jobs))
    print("==========================================")

    return all_jobs



# =========================================================
# DEFAULT AI FEEDBACK
# =========================================================

def default_feedback(answer):

    return {
        "analysis": (
            "AI analysis is currently unavailable."
        ),

        "grammar": (
            "AI analysis unavailable."
        ),

        "spelling": (
            "AI analysis unavailable."
        ),

        "vocabulary": (
            "AI analysis unavailable."
        ),

        "clarity": (
            "AI analysis unavailable."
        ),

        "technical": (
            "AI analysis unavailable."
        ),

        "missing_points": (
            "AI analysis unavailable."
        ),

        "improvements": (
            "Please check your Gemini API configuration "
            "and try again."
        ),

        "improved_answer": answer
    }


# =========================================================
# GEMINI AI INTERVIEW ANALYSIS
# =========================================================

def analyze_interview_answer(
    question,
    answer,
    role
):

    print("=" * 60)
    print("AI INTERVIEW ANALYSIS")
    print("=" * 60)

    print("ROLE:", role)
    print("QUESTION:", question)
    print("ANSWER:", answer)

    print("=" * 60)

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY NOT FOUND")
        return default_feedback(answer)

    prompt = f"""
You are an AI Interview Coach.

Analyze the candidate's interview answer.

JOB ROLE:
{role}

INTERVIEW QUESTION:
{question}

CANDIDATE ANSWER:
{answer}

IMPORTANT:
Do NOT provide any numerical score.

Analyze the candidate's answer in a helpful,
professional and educational way.

Check the following:

1. Overall analysis
2. Grammar mistakes
3. Spelling mistakes
4. Vocabulary improvements
5. Sentence clarity
6. Technical/content correctness
7. Important missing points
8. How to improve
9. Professional improved answer

Rules:

- Be supportive and educational.
- Do not insult the candidate.
- Do not invent personal experience.
- Use only information provided by the candidate.
- If there are no grammar mistakes, say:
  "No major grammar mistakes found."
- If there are no spelling mistakes, say:
  "No major spelling mistakes found."
- For technical questions, make the explanation technically accurate.
- For "Tell me about yourself", create a professional interview answer.
- Correct grammar, spelling and vocabulary where required.
- Keep the improved answer natural.
- Do NOT provide a numerical score.

Return the response using EXACTLY these headings:

OVERALL ANALYSIS:
<analysis>

GRAMMAR:
<grammar feedback>

SPELLING:
<spelling feedback>

VOCABULARY:
<vocabulary feedback>

CLARITY:
<clarity feedback>

TECHNICAL:
<technical/content feedback>

MISSING POINTS:
<missing points>

IMPROVEMENTS:
<improvements>

IMPROVED ANSWER:
<professional improved answer>
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1800
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    print("Sending request to Gemini...")

    # Try the requested model first, then stable fallback models.
    # 503 means the model is temporarily unavailable/busy.
    # A short retry is used before moving to the next model.
    for model_index, model_name in enumerate(
        GEMINI_FALLBACK_MODELS
    ):

        model_url = (
            f"{GEMINI_API_BASE_URL}/"
            f"{model_name}:generateContent"
        )

        for attempt in range(1, 3):

            try:

                print(
                    f"Trying Gemini model: {model_name} "
                    f"(attempt {attempt}/2)"
                )

                response = requests.post(
                    model_url,
                    headers=headers,
                    json=payload,
                    timeout=60
                )

                print(
                    "GEMINI STATUS:",
                    response.status_code
                )

                # Success
                if response.status_code == 200:

                    data = response.json()

                    candidates = data.get(
                        "candidates",
                        []
                    )

                    if not candidates:
                        print(
                            "Gemini returned no candidates."
                        )
                        break

                    content = candidates[0].get(
                        "content",
                        {}
                    )

                    parts = content.get(
                        "parts",
                        []
                    )

                    if not parts:
                        print(
                            "Gemini returned no text parts."
                        )
                        break

                    ai_text = parts[0].get(
                        "text",
                        ""
                    ).strip()

                    if not ai_text:
                        print(
                            "Gemini returned empty text."
                        )
                        break

                    print("=" * 60)
                    print(
                        "SUCCESSFUL GEMINI MODEL:",
                        model_name
                    )
                    print("AI RESPONSE:")
                    print(ai_text)
                    print("=" * 60)

                    return parse_ai_feedback(
                        ai_text,
                        answer
                    )

                # Temporary server overload / rate limit.
                if response.status_code in (
                    429,
                    500,
                    502,
                    503,
                    504
                ):

                    print(
                        f"Gemini {model_name} is temporarily "
                        "unavailable."
                    )

                    if attempt == 1:
                        import time
                        print(
                            "Waiting 2 seconds before retry..."
                        )
                        time.sleep(2)
                        continue

                    print(
                        f"{model_name} failed after retries; "
                        "trying next model."
                    )
                    break

                # Authentication/configuration error.
                if response.status_code in (
                    400,
                    401,
                    403
                ):

                    print("=" * 60)
                    print("GEMINI AUTH/REQUEST ERROR")
                    print("=" * 60)
                    print(response.text)
                    print(
                        "MODEL USED:",
                        model_name
                    )
                    print("=" * 60)

                    # Do not waste time retrying a bad key.
                    return {
                        "analysis": (
                            "Gemini rejected the API request."
                        ),
                        "grammar": (
                            "AI analysis unavailable."
                        ),
                        "spelling": (
                            "AI analysis unavailable."
                        ),
                        "vocabulary": (
                            "AI analysis unavailable."
                        ),
                        "clarity": (
                            "AI analysis unavailable."
                        ),
                        "technical": (
                            "AI analysis unavailable."
                        ),
                        "missing_points": (
                            "AI analysis unavailable."
                        ),
                        "improvements": (
                            "Please verify your Gemini API key "
                            "and API access."
                        ),
                        "improved_answer": answer
                    }

                print("=" * 60)
                print("GEMINI ERROR")
                print("=" * 60)
                print(response.text)
                print(
                    "MODEL USED:",
                    model_name
                )
                print("=" * 60)

                break

            except requests.exceptions.Timeout:

                print(
                    f"Gemini timeout for {model_name}."
                )

                if attempt == 1:
                    import time
                    time.sleep(2)
                    continue

                break

            except requests.exceptions.RequestException as e:

                print(
                    "GEMINI REQUEST ERROR:",
                    e
                )
                break

            except ValueError as e:

                print(
                    "GEMINI JSON ERROR:",
                    e
                )
                break

            except Exception as e:

                print(
                    "AI ANALYSIS ERROR:",
                    e
                )
                break

    # All available models failed.
    # Return a clean response so the interview page does not break.
    print("=" * 60)
    print(
        "ALL GEMINI MODELS ARE TEMPORARILY UNAVAILABLE."
    )
    print("=" * 60)

    return {
        "analysis": (
            "AI feedback could not be generated because "
            "the Gemini service is temporarily busy. "
            "Your answer was saved successfully."
        ),
        "grammar": (
            "AI analysis is temporarily unavailable."
        ),
        "spelling": (
            "AI analysis is temporarily unavailable."
        ),
        "vocabulary": (
            "AI analysis is temporarily unavailable."
        ),
        "clarity": (
            "AI analysis is temporarily unavailable."
        ),
        "technical": (
            "AI analysis is temporarily unavailable."
        ),
        "missing_points": (
            "AI analysis is temporarily unavailable."
        ),
        "improvements": (
            "Your answer has been saved. Please try "
            "the analysis again when Gemini is available."
        ),
        "improved_answer": answer
    }


# =========================================================
# PARSE GEMINI RESPONSE
# =========================================================

def parse_ai_feedback(
    text,
    original_answer
):

    sections = {

        "analysis": "",

        "grammar": "",

        "spelling": "",

        "vocabulary": "",

        "clarity": "",

        "technical": "",

        "missing_points": "",

        "improvements": "",

        "improved_answer": ""
    }

    markers = {

        "OVERALL ANALYSIS:": "analysis",

        "GRAMMAR:": "grammar",

        "SPELLING:": "spelling",

        "VOCABULARY:": "vocabulary",

        "CLARITY:": "clarity",

        "TECHNICAL:": "technical",

        "MISSING POINTS:": "missing_points",

        "IMPROVEMENTS:": "improvements",

        "IMPROVED ANSWER:": "improved_answer"
    }

    current_key = None

    for line in text.splitlines():

        stripped = line.strip()

        if not stripped:
            continue

        upper_line = stripped.upper()

        matched = False

        for marker, key in markers.items():

            if upper_line.startswith(marker):

                current_key = key

                remaining = stripped[
                    len(marker):
                ].strip()

                if remaining:

                    sections[key] = remaining

                matched = True

                break

        if matched:
            continue

        if current_key is not None:

            if sections[current_key]:

                sections[current_key] += (
                    "\n" + stripped
                )

            else:

                sections[current_key] = stripped

    if not sections["analysis"]:

        sections["analysis"] = (
            "AI analysis was generated, "
            "but the response format was incomplete."
        )

    if not sections["grammar"]:

        sections["grammar"] = (
            "No specific grammar feedback was returned."
        )

    if not sections["spelling"]:

        sections["spelling"] = (
            "No specific spelling feedback was returned."
        )

    if not sections["vocabulary"]:

        sections["vocabulary"] = (
            "No specific vocabulary feedback was returned."
        )

    if not sections["clarity"]:

        sections["clarity"] = (
            "No specific clarity feedback was returned."
        )

    if not sections["technical"]:

        sections["technical"] = (
            "No specific technical feedback was returned."
        )

    if not sections["missing_points"]:

        sections["missing_points"] = (
            "No major missing points identified."
        )

    if not sections["improvements"]:

        sections["improvements"] = (
            "Continue practicing concise and "
            "professional interview answers."
        )

    if not sections["improved_answer"]:

        sections["improved_answer"] = (
            original_answer
        )

    return sections


# =========================================================
# FORMAT FEEDBACK FOR OLD TEMPLATE
# =========================================================

def format_ai_feedback(feedback):

    if not isinstance(feedback, dict):

        return str(feedback)

    sections = [

        (
            "🧠 Overall Analysis",
            feedback.get(
                "analysis",
                ""
            )
        ),

        (
            "✍️ Grammar",
            feedback.get(
                "grammar",
                ""
            )
        ),

        (
            "🔤 Spelling",
            feedback.get(
                "spelling",
                ""
            )
        ),

        (
            "📚 Vocabulary",
            feedback.get(
                "vocabulary",
                ""
            )
        ),

        (
            "💬 Sentence Clarity",
            feedback.get(
                "clarity",
                ""
            )
        ),

        (
            "💻 Technical / Content",
            feedback.get(
                "technical",
                ""
            )
        ),

        (
            "📌 Missing Points",
            feedback.get(
                "missing_points",
                ""
            )
        ),

        (
            "🚀 How to Improve",
            feedback.get(
                "improvements",
                ""
            )
        ),

        (
            "⭐ Improved Answer",
            feedback.get(
                "improved_answer",
                ""
            )
        )
    ]

    output = []

    for title, content in sections:

        output.append(title + ":")

        output.append(
            content or "No information available."
        )

        output.append("")

    return "\n".join(
        output
    ).strip()


# =========================================================
# RESUME PARSER
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

app = Flask(
    __name__
)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "secret123"
)


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

app.config[
    "UPLOAD_FOLDER"
] = UPLOAD_FOLDER

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================================================
# DATABASE
# =========================================================

app.config[
    "SQLALCHEMY_DATABASE_URI"
] = "sqlite:///users.db"

app.config[
    "SQLALCHEMY_TRACK_MODIFICATIONS"
] = False

db = SQLAlchemy(
    app
)


# =========================================================
# USER MODEL
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


# =====================================
# SAVED JOBS DATABASE MODEL
# =====================================

class SavedJob(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    job_id = db.Column(
        db.String(500),
        nullable=False
    )

    title = db.Column(
        db.String(300),
        nullable=False
    )

    company = db.Column(
        db.String(300)
    )

    location = db.Column(
        db.String(300)
    )

    country = db.Column(
        db.String(100)
    )

    employment_type = db.Column(
        db.String(100)
    )

    salary = db.Column(
        db.String(200)
    )

    apply_link = db.Column(
        db.Text
    )

    description = db.Column(
        db.Text
    )

    remote = db.Column(
        db.Boolean,
        default=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "job_id",
            name="unique_saved_job_per_user"
        ),
    )



# =========================================================
# CREATE DATABASE
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# HOME
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

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

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
# DASHBOARD
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
# UPLOAD RESUME
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

        if not file.filename:

            flash(
                "Please choose a file."
            )

            return redirect(
                url_for("upload")
            )

        filename = secure_filename(
            file.filename
        )

        extension = os.path.splitext(
            filename
        )[1].lower()

        allowed_extensions = [
            ".pdf",
            ".docx"
        ]

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
            extension in [".pdf", ".docx"]
            and filename.lower()
            != "enhanced_resume.docx"
        ):

            files.append(
                filename
            )

    if not files:

        return "No Resume Uploaded"

    latest_filename = max(
        files,
        key=lambda filename: os.path.getmtime(
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
            extension in [".pdf", ".docx"]
            and filename.lower()
            != "enhanced_resume.docx"
        ):

            files.append(
                filename
            )

    if not files:

        return "No Resume Uploaded"

    latest_filename = max(
        files,
        key=lambda filename: os.path.getmtime(
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

    try:

        original_score_data = calculate_ats_score(
            name,
            email,
            phone,
            skills,
            education,
            projects,
            resume_text,
            role
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

    enhanced_education = extract_education(
        enhanced_text
    )

    enhanced_projects = extract_projects(
        enhanced_text
    )

    try:

        enhanced_score_data = calculate_ats_score(
            enhanced_name,
            enhanced_email,
            enhanced_phone,
            enhanced_skills,
            enhanced_education,
            enhanced_projects,
            enhanced_text,
            role
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
# JOB SEARCH / CHATBOT
# =========================================================


@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():

    if "user" not in session:
        return redirect(url_for("login"))

    global JOB_CACHE

    jobs = []
    response = ""
    error_message = ""

    if request.method == "POST":

        query = request.form.get("message", "").strip()
        selected_country = request.form.get(
            "country", "worldwide"
        ).strip().lower()

        if not query:
            error_message = "Please enter a job search query."

            return render_template(
                "chatbot.html",
                jobs=[],
                response="",
                error_message=error_message
            )

        print("=" * 50)
        print("JOB SEARCH QUERY:", query)
        print("SELECTED COUNTRY:", selected_country)
        print("=" * 50)

        # Supported countries
        country_names = {
            "in": "India",
            "gb": "United Kingdom",
            "us": "United States",
            "ca": "Canada",
            "au": "Australia",
            "de": "Germany",
            "sg": "Singapore",
            "ae": "United Arab Emirates"
        }

        try:
            if selected_country == "worldwide":
                # Existing function searches all configured countries
                jobs = search_jobs(query)

            elif selected_country in country_names:
                # Search only the selected country
                jobs = search_jobs(
                    query,
                    country_code=selected_country
                )

            else:
                jobs = []
                error_message = "Please select a valid country."

            JOB_CACHE = jobs.copy()

            if jobs:
                country_label = (
                    "Worldwide"
                    if selected_country == "worldwide"
                    else country_names.get(
                        selected_country, "Selected country"
                    )
                )

                response = (
                    f"{len(jobs)} jobs found for: "
                    f"{query} — {country_label}"
                )

            elif not error_message:
                error_message = (
                    "No jobs found. Try another job title "
                    "or select a different country."
                )

        except Exception as e:
            print("JOB SEARCH ERROR:", e)
            jobs = []
            error_message = (
                "Job search failed. Please try again."
            )

    else:
        jobs = JOB_CACHE

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

    if not JOB_CACHE:

        flash(
            "Job results expired. "
            "Please search for jobs again."
        )

        return redirect(
            url_for("chatbot")
        )

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

    job = JOB_CACHE[
        job_index
    ]

    return render_template(
        "job_details.html",
        job=job,
        job_index=job_index
    )


# =========================================================
# INTERVIEW QUESTIONS
# =========================================================

def get_interview_questions(role):

    role = (
        role or "Software Developer"
    ).lower()

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

    role = session.get(
        "role",
        "Software Developer"
    )

    questions = get_interview_questions(
        role
    )

    total_questions = len(
        questions
    )

    # Use the logged-in user as the key for server-side
    # interview data. This keeps large AI feedback out of
    # the browser session cookie.
    user_key = str(
        session.get("user")
    )

    # -----------------------------------------------------
    # START NEW INTERVIEW
    # -----------------------------------------------------

    if request.args.get(
        "new"
    ) == "1":

        INTERVIEW_DATA[user_key] = {
            "answers": [],
            "feedback_history": []
        }

        # Remove old client-side interview data if present.
        session.pop(
            "interview_answers",
            None
        )
        session.pop(
            "interview_feedback_history",
            None
        )
        session.modified = True

        return redirect(
            url_for("interview")
        )

    # -----------------------------------------------------
    # GET SERVER-SIDE INTERVIEW DATA
    # -----------------------------------------------------

    if user_key not in INTERVIEW_DATA:
        INTERVIEW_DATA[user_key] = {
            "answers": [],
            "feedback_history": []
        }

    interview_data = INTERVIEW_DATA[user_key]

    answers = interview_data["answers"]
    feedback_history = interview_data["feedback_history"]

    # -----------------------------------------------------
    # QUESTION NUMBER
    # -----------------------------------------------------

    question_number = request.args.get(
        "question",
        0,
        type=int
    )

    if question_number < 0:

        question_number = 0

    if question_number >= total_questions:

        question_number = 0

    current_question = questions[
        question_number
    ]

    # =====================================================
    # POST ANSWER
    # =====================================================

    if request.method == "POST":

        answer = request.form.get(
            "answer",
            ""
        ).strip()

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
        # AI ANALYSIS
        # -------------------------------------------------

        ai_feedback = analyze_interview_answer(
            current_question,
            answer,
            role
        )

        # Make absolutely sure feedback is a dictionary.
        if not isinstance(
            ai_feedback,
            dict
        ):

            ai_feedback = default_feedback(
                answer
            )

        # -------------------------------------------------
        # SAVE ANSWER SERVER-SIDE
        # -------------------------------------------------

        while len(answers) <= question_number:

            answers.append("")

        while len(feedback_history) <= question_number:

            feedback_history.append({})

        answers[
            question_number
        ] = answer

        feedback_history[
            question_number
        ] = ai_feedback

        # -------------------------------------------------
        # NEXT QUESTION
        # -------------------------------------------------

        next_question = (
            question_number + 1
        )

        # -------------------------------------------------
        # INTERVIEW COMPLETE
        # -------------------------------------------------

        if next_question >= total_questions:

            return render_template(
                "interview_result.html",
                role=role,
                total_questions=total_questions,
                answers=answers,
                feedback_history=feedback_history,
                questions=questions
            )

        # -------------------------------------------------
        # SHOW AI FEEDBACK
        # -------------------------------------------------

        return render_template(
            "interview_feedback.html",

            question=current_question,

            question_number=question_number,

            total_questions=total_questions,

            answer=answer,

            feedback=ai_feedback,

            ai_response=format_ai_feedback(
                ai_feedback
            ),

            next_question=next_question,

            role=role
        )

    # =====================================================
    # GET QUESTION
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


# =====================================
# SAVE A JOB
# =====================================

@app.route("/save-job/<int:job_index>", methods=["POST"])
def save_job(job_index):

    if "user" not in session:
        return redirect(url_for("login"))

    global JOB_CACHE

    if job_index < 0 or job_index >= len(JOB_CACHE):
        return redirect(url_for("chatbot"))

    user = User.query.filter_by(
        fullname=session["user"]
    ).first()

    if not user:
        return redirect(url_for("login"))

    job = JOB_CACHE[job_index]

    job_id = str(
        job.get("job_id")
        or job.get("apply_link")
        or (
            str(job.get("title", ""))
            + "|"
            + str(job.get("company", ""))
            + "|"
            + str(job.get("location", ""))
        )
    )

    existing = SavedJob.query.filter_by(
        user_id=user.id,
        job_id=job_id
    ).first()

    if not existing:
        saved = SavedJob(
            user_id=user.id,
            job_id=job_id,
            title=job.get("title", "Unknown Job"),
            company=job.get("company", ""),
            location=job.get("location", ""),
            country=job.get("country", ""),
            employment_type=job.get("employment_type", ""),
            salary=str(job.get("salary") or ""),
            apply_link=job.get("apply_link", ""),
            description=job.get("description", ""),
            remote=bool(job.get("remote", False))
        )

        db.session.add(saved)
        db.session.commit()

    return redirect(url_for("saved_jobs"))



# =====================================
# VIEW SAVED JOBS
# =====================================

@app.route("/saved-jobs")
def saved_jobs():

    if "user" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(
        fullname=session["user"]
    ).first()

    if not user:
        return redirect(url_for("login"))

    jobs = SavedJob.query.filter_by(
        user_id=user.id
    ).order_by(SavedJob.id.desc()).all()

    return render_template(
        "saved_jobs.html",
        jobs=jobs
    )


# =====================================
# REMOVE A SAVED JOB
# =====================================

@app.route("/remove-saved-job/<int:saved_id>", methods=["POST"])
def remove_saved_job(saved_id):

    if "user" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(
        fullname=session["user"]
    ).first()

    if not user:
        return redirect(url_for("login"))

    saved = SavedJob.query.filter_by(
        id=saved_id,
        user_id=user.id
    ).first()

    if saved:
        db.session.delete(saved)
        db.session.commit()

    return redirect(url_for("saved_jobs"))


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("AI RESUME ANALYZER")
    print("=" * 60)
    print(
        "Gemini Model:",
        GEMINI_MODEL
    )
    print(
        "Gemini Fallback Models:",
        ", ".join(GEMINI_FALLBACK_MODELS)
    )
    print(
        "Gemini API Key:",
        "FOUND" if GEMINI_API_KEY else "NOT FOUND"
    )
    print("=" * 60)

    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug_mode
    )