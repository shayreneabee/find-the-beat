import hashlib
import base64
import hmac
import json
import os
import secrets
import sqlite3
import smtplib
import time
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode, urlparse

from authlib.integrations.flask_client import OAuth
from authlib.jose import jwt
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.getenv("INSTANCE_DIR", BASE_DIR / "instance"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "static" / "uploads"))
PHOTO_DIR = UPLOAD_DIR / "photos"
VIDEO_DIR = UPLOAD_DIR / "videos"
AUDIO_DIR = UPLOAD_DIR / "audio"
DB_PATH = Path(os.getenv("DATABASE_PATH", INSTANCE_DIR / "find_the_beat_v2.db"))

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "m4v", "webm"}
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "aac", "ogg", "webm"}
BRENT_CO_URL = os.getenv("BRENT_CO_URL", "https://brentandco.org/")
FIND_THE_BEAT_URL = os.getenv("FIND_THE_BEAT_URL", "https://findthebeatmusic.com")
SECOND_CHANCE_URL = os.getenv(
    "SECOND_CHANCE_URL",
    "https://secondchancecareers.org/",
)
LETS_COOK_URL = os.getenv("LETS_COOK_URL", "https://letscookyall.com/")
BEU_URL = os.getenv("BEU_URL", "https://beutravel.org/")
SSO_SHARED_SECRET = os.getenv("SSO_SHARED_SECRET", "dev-sso-change-me")
SSO_TOKEN_TTL_SECONDS = int(os.getenv("SSO_TOKEN_TTL_SECONDS", "300") or "300")
AUTH_PROVIDER = os.getenv("BRENT_AUTH_PROVIDER", "local")
OWNER_AUTH_PROVIDER = os.getenv("BRENT_OWNER_AUTH_PROVIDER", "brent-core")
OWNER_INITIAL_PASSWORD = os.getenv("BRENT_OWNER_INITIAL_PASSWORD", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "")
APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY", "")
FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID", "")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET", "")
GOOGLE_OAUTH_READY = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
APPLE_OAUTH_READY = bool(APPLE_CLIENT_ID and APPLE_TEAM_ID and APPLE_KEY_ID and APPLE_PRIVATE_KEY)
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()
PLAUSIBLE_DOMAIN = os.getenv("PLAUSIBLE_DOMAIN", "").strip()
ADMIN_EMAIL = os.getenv("BRENT_ADMIN_EMAIL", "shalanda.brent@gmail.com").strip().lower()
SIGNUP_NOTIFY_EMAIL = os.getenv("SIGNUP_NOTIFY_EMAIL", ADMIN_EMAIL).strip()
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME or SIGNUP_NOTIFY_EMAIL).strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") != "0"
FOUNDER_PROFILES = [
    {
        "email": os.getenv("BRENT_OWNER_EMAIL", "shalanda.brent@gmail.com").strip().lower(),
        "full_name": os.getenv("BRENT_OWNER_FULL_NAME", "Shalanda Brent"),
        "display_name": os.getenv("BRENT_OWNER_DISPLAY_NAME", "Shay"),
    },
]
LEGACY_REMOVED_FOUNDER_EMAILS = {
    "jerod.l.cotton@gmail.com",
}
OWNER_BIO = (
    "Official Brent & Co founder profile for ecosystem updates, creator support, "
    "and community connection."
)

SECOND_CHANCE_CATEGORIES = [
    {
        "slug": "educational",
        "title": "Educational",
        "search_label": "College Courses",
        "image": "educational-crop.png",
        "hero": "educational-crop.png",
        "resources": ["GED prep", "College applications", "Transcript help"],
    },
    {
        "slug": "trade",
        "title": "Trade",
        "search_label": "Trade Search",
        "image": "trade-crop.png",
        "hero": "truck-crop.png",
        "resources": ["CDL programs", "Welding", "Electrical apprenticeships"],
    },
    {
        "slug": "life-skills",
        "title": "Life Skills",
        "search_label": "Life Skills",
        "image": "life-crop.png",
        "hero": "classroom-crop.png",
        "resources": ["GED prep", "Interview skills", "Job prep"],
    },
    {
        "slug": "occupational-license",
        "title": "Occupational License",
        "search_label": "Occupation Search",
        "image": "occupational-crop.png",
        "hero": "occupational-crop.png",
        "resources": ["Healthcare licensing", "CDL support", "State board steps"],
    },
    {
        "slug": "jobs",
        "title": "Job Search",
        "search_label": "Job Search",
        "image": "jobs-crop.png",
        "hero": "road-crop.png",
        "resources": ["Remote work", "Local openings", "Resume-ready roles"],
    },
]

SECOND_CHANCE_SEARCH_ITEMS = [
    "Educational Search",
    "Job Search",
    "Trade Search",
    "Remote Work",
    "Life Skills",
    "Occupational License",
    "Apprenticeships",
    "College Courses",
]

SECOND_CHANCE_SKILLS = [
    "Active Listening",
    "Communication",
    "Computer Skills",
    "Interpersonal Skills",
    "Leadership",
    "Management Skills",
    "Problem Solving",
    "Time Management",
]

SECOND_CHANCE_FEATURES = [
    {
        "title": "My Path Dashboard",
        "body": "A simple step-by-step plan so each person can see what is done, what is next, and where they are gaining momentum.",
    },
    {
        "title": "Resume Help",
        "body": "Guidance for building a clean resume packet, explaining gaps, and presenting experience with confidence.",
    },
    {
        "title": "Documents & ID Help",
        "body": "A checklist for IDs, records, certificates, and work documents that can hold someone back if they are missing.",
    },
    {
        "title": "Interview Prep",
        "body": "Practice prompts, confidence builders, and language that helps people tell their story without shame.",
    },
    {
        "title": "Career Services",
        "body": "Connections to training, trade programs, occupational licensing help, and supportive career resources.",
    },
    {
        "title": "Jobs & Opportunities",
        "body": "Search paths for jobs, remote work, apprenticeships, college courses, and second-chance-friendly options.",
    },
]

SECOND_CHANCE_CHECKLIST = [
    {
        "title": "Create your career profile",
        "detail": "Tell us your goals, strengths, location, and what kind of support you need first.",
    },
    {
        "title": "Choose your job path",
        "detail": "Pick a direction: immediate work, training, trade, license support, or school.",
    },
    {
        "title": "Build or update your resume",
        "detail": "Create a resume packet that explains your experience clearly and confidently.",
    },
    {
        "title": "Gather documents and ID",
        "detail": "Track IDs, certificates, records, and work documents before applications slow down.",
    },
    {
        "title": "Practice interview answers",
        "detail": "Prepare honest, steady answers that help you tell your story without shame.",
    },
    {
        "title": "Apply to ready-fit opportunities",
        "detail": "Use the job finder to focus on roles, training, and employers that match your next step.",
    },
]

SECOND_CHANCE_JOB_HELP = [
    {
        "title": "Second-chance-friendly jobs",
        "type": "Job Search",
        "body": "Search local roles where reliability, readiness, and a strong resume packet can help open the door.",
        "cta": "Find Jobs",
        "resource_slug": "job-search",
    },
    {
        "title": "Remote work path",
        "type": "Remote Work",
        "body": "Explore entry-friendly remote roles, digital skills, and application steps for work-from-home options.",
        "cta": "Search Remote",
        "resource_slug": "job-search",
    },
    {
        "title": "Trade and apprenticeship path",
        "type": "Trade Search",
        "body": "Look for CDL, construction, electrical, welding, manufacturing, and paid apprenticeship routes.",
        "cta": "Find Training",
        "resource_slug": "career-workforce",
    },
    {
        "title": "Occupational license support",
        "type": "Occupational License",
        "body": "Get organized around license requirements, board steps, and documents needed for regulated careers.",
        "cta": "Review Steps",
        "resource_slug": "career-workforce",
    },
]

SECOND_CHANCE_RESOURCE_GROUPS = [
    {
        "slug": "job-search",
        "title": "Job Search",
        "intro": "Start with familiar job boards, then bring promising roles back into your path dashboard.",
        "items": [
            {
                "label": "Indeed",
                "url": "https://www.indeed.com",
                "note": "Search broad local and remote job listings.",
                "icon": "⌕",
            },
            {
                "label": "LinkedIn Jobs",
                "url": "https://www.linkedin.com/jobs",
                "note": "Search roles and follow companies that fit your next step.",
                "icon": "in",
            },
            {
                "label": "ZipRecruiter",
                "url": "https://www.ziprecruiter.com",
                "note": "Browse jobs and set alerts for new openings.",
                "icon": "Z",
            },
            {
                "label": "Glassdoor",
                "url": "https://www.glassdoor.com/Job/index.htm",
                "note": "Research job openings, companies, and salary ranges.",
                "icon": "G",
            },
            {
                "label": "Snagajob",
                "url": "https://www.snagajob.com",
                "note": "Find hourly, service, retail, and local opportunities.",
                "icon": "S",
            },
        ],
    },
    {
        "slug": "career-workforce",
        "title": "Career & Workforce Resources",
        "intro": "Use these when someone needs training, local workforce support, clothing, veteran services, or career counseling.",
        "items": [
            {
                "label": "CareerOneStop",
                "url": "https://www.careeronestop.org",
                "note": "Official career, training, and job-search resources from the U.S. Department of Labor.",
                "icon": "★",
            },
            {
                "label": "American Job Center Finder",
                "url": "https://www.careeronestop.org/LocalHelp/AmericanJobCenters/american-job-centers.aspx",
                "note": "Find local workforce offices and employment support near you.",
                "icon": "⌂",
            },
            {
                "label": "Dress for Success",
                "url": "https://dressforsuccess.org",
                "note": "Career clothing, confidence support, and workforce development for women.",
                "icon": "✓",
            },
            {
                "label": "VA VR&E",
                "url": "https://www.va.gov/careers-employment/vocational-rehabilitation/",
                "note": "Veteran Readiness and Employment resources for eligible veterans and service members.",
                "icon": "VA",
            },
        ],
    },
    {
        "slug": "documents-id",
        "title": "Documents & Identification",
        "intro": "Documents can be the hidden barrier. These resources help people replace or track what they need.",
        "items": [
            {
                "label": "Replace Social Security Card",
                "url": "https://www.ssa.gov/number-card/replace-card",
                "note": "Official Social Security Administration replacement card resource.",
                "icon": "ID",
            },
            {
                "label": "State DMV / ID Services",
                "url": "https://www.usa.gov/state-motor-vehicle-services",
                "note": "Find state motor vehicle agencies for IDs, licenses, and related records.",
                "icon": "▣",
            },
            {
                "label": "Birth Certificate Records",
                "url": "https://www.cdc.gov/nchs/w2w/index.htm",
                "note": "CDC directory for vital records offices by state and territory.",
                "icon": "◎",
            },
            {
                "label": "Replace Vital Documents",
                "url": "https://www.usa.gov/replace-vital-documents",
                "note": "USA.gov guide for replacing IDs, vital records, and federal documents.",
                "icon": "☑",
            },
        ],
    },
    {
        "slug": "resume-interview",
        "title": "Interview & Resume Help",
        "intro": "Use these to build the resume packet, prepare answers, and walk into interviews with more confidence.",
        "items": [
            {
                "label": "CareerOneStop Resume Guide",
                "url": "https://www.careeronestop.org/JobSearch/Resumes/resumes.aspx",
                "note": "Resume guidance, examples, and practical job-search support.",
                "icon": "R",
            },
            {
                "label": "CareerOneStop Interview Tips",
                "url": "https://www.careeronestop.org/JobSearch/Interview/interview.aspx",
                "note": "Interview preparation, questions, and follow-up help.",
                "icon": "Q",
            },
            {
                "label": "Canva Resume Templates",
                "url": "https://www.canva.com/resumes/templates/",
                "note": "Clean resume templates for building a polished resume packet.",
                "icon": "C",
            },
            {
                "label": "Indeed Career Guide",
                "url": "https://www.indeed.com/career-advice",
                "note": "Resume, interview, and job-search articles for applicants.",
                "icon": "i",
            },
        ],
    },
    {
        "slug": "transport-support",
        "title": "Transportation & Support",
        "intro": "Transportation, food, clothing, and local assistance can decide whether someone can accept a job.",
        "items": [
            {
                "label": "211",
                "url": "https://www.211.org",
                "note": "Local help for transportation, housing, food, utilities, and crisis support.",
                "icon": "211",
            },
            {
                "label": "FindHelp",
                "url": "https://www.findhelp.org",
                "note": "Search community assistance by ZIP code.",
                "icon": "♥",
            },
            {
                "label": "Lyft Up",
                "url": "https://www.lyft.com/lyftup",
                "note": "Lyft programs focused on access to transportation and opportunity.",
                "icon": "L",
            },
            {
                "label": "Public Transit Directions",
                "url": "https://www.google.com/maps/dir/",
                "note": "Plan public transit, walking, or driving routes to interviews and work.",
                "icon": "↗",
            },
        ],
    },
]


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "100")) * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

SSO_APP_TARGETS = {
    "brent": BRENT_CO_URL.rstrip("/"),
    "find-the-beat": FIND_THE_BEAT_URL.rstrip("/"),
    "lets-cook": LETS_COOK_URL.rstrip("/"),
    "second-chance": SECOND_CHANCE_URL.rstrip("/"),
    "beu": BEU_URL.rstrip("/"),
}

oauth = OAuth(app)

if GOOGLE_OAUTH_READY:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def apple_private_key():
    return APPLE_PRIVATE_KEY.replace("\\n", "\n")


def apple_client_secret():
    now = int(time.time())
    payload = {
        "iss": APPLE_TEAM_ID,
        "iat": now,
        "exp": now + 86400 * 180,
        "aud": "https://appleid.apple.com",
        "sub": APPLE_CLIENT_ID,
    }
    header = {"alg": "ES256", "kid": APPLE_KEY_ID}
    encoded = jwt.encode(header, payload, apple_private_key())
    return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded


if APPLE_OAUTH_READY:
    oauth.register(
        name="apple",
        client_id=APPLE_CLIENT_ID,
        client_secret=apple_client_secret(),
        authorize_url="https://appleid.apple.com/auth/authorize",
        access_token_url="https://appleid.apple.com/auth/token",
        jwks_uri="https://appleid.apple.com/auth/keys",
        client_kwargs={"scope": "email name"},
        token_endpoint_auth_method="client_secret_post",
    )

if os.getenv("TRUST_PROXY", "1") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


for folder in (INSTANCE_DIR, UPLOAD_DIR, PHOTO_DIR, VIDEO_DIR, AUDIO_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT DEFAULT '',
                display_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                role TEXT DEFAULT '',
                genre TEXT DEFAULT '',
                city TEXT DEFAULT '',
                state TEXT DEFAULT '',
                country TEXT DEFAULT '',
                bio TEXT DEFAULT '',
                previous_work TEXT DEFAULT '',
                availability TEXT DEFAULT '',
                tags_csv TEXT DEFAULT '',
                instrument TEXT DEFAULT '',
                services_csv TEXT DEFAULT '',
                avatar_url TEXT DEFAULT '',
                profile_pic TEXT DEFAULT '',
                profile_video TEXT DEFAULT '',
                instagram_url TEXT DEFAULT '',
                tiktok_url TEXT DEFAULT '',
                youtube_url TEXT DEFAULT '',
                spotify_url TEXT DEFAULT '',
                linkedin_url TEXT DEFAULT '',
                brent_account_id TEXT DEFAULT '',
                provider TEXT DEFAULT 'local',
                provider_id TEXT DEFAULT '',
                auth_provider TEXT DEFAULT 'local',
                is_admin INTEGER DEFAULT 0,
                is_founder INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS performances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                video_filename TEXT DEFAULT '',
                audio_filename TEXT DEFAULT '',
                image_filename TEXT DEFAULT '',
                thumb_filename TEXT DEFAULT '',
                external_url TEXT DEFAULT '',
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                is_featured INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(profile_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                body TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                visitor_hash TEXT DEFAULT '',
                app_key TEXT DEFAULT 'find-the-beat',
                event_type TEXT NOT NULL,
                path TEXT DEFAULT '',
                feature TEXT DEFAULT '',
                state TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS music_profiles (
                user_id INTEGER PRIMARY KEY,
                role TEXT DEFAULT '',
                instruments_csv TEXT DEFAULT '',
                genres_csv TEXT DEFAULT '',
                services_csv TEXT DEFAULT '',
                settings_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cook_profiles (
                user_id INTEGER PRIMARY KEY,
                skill_level TEXT DEFAULT '',
                cooking_interests TEXT DEFAULT '',
                settings_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS career_profiles (
                user_id INTEGER PRIMARY KEY,
                checklist_json TEXT DEFAULT '{}',
                job_interests TEXT DEFAULT '',
                settings_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_profiles (
                user_id INTEGER PRIMARY KEY,
                travel_interests TEXT DEFAULT '',
                preferences_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        for table, columns in {
            "music_profiles": {
                "instruments": "TEXT DEFAULT ''",
                "genres": "TEXT DEFAULT ''",
                "city": "TEXT DEFAULT ''",
                "state": "TEXT DEFAULT ''",
                "bio": "TEXT DEFAULT ''",
                "services": "TEXT DEFAULT ''",
                "availability": "TEXT DEFAULT ''",
            },
            "cook_profiles": {
                "favorite_cuisines": "TEXT DEFAULT ''",
                "saved_recipes": "TEXT DEFAULT ''",
                "hosting_interests": "TEXT DEFAULT ''",
                "meal_plans": "TEXT DEFAULT ''",
            },
            "career_profiles": {
                "career_goal": "TEXT DEFAULT ''",
                "certifications": "TEXT DEFAULT ''",
                "resume_status": "TEXT DEFAULT ''",
                "applications": "TEXT DEFAULT ''",
                "checklist_progress": "TEXT DEFAULT ''",
            },
            "travel_profiles": {
                "saved_places": "TEXT DEFAULT ''",
                "cities_visited": "TEXT DEFAULT ''",
                "recommendations": "TEXT DEFAULT ''",
            },
        }.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        for column, definition in {
            "full_name": "TEXT DEFAULT ''",
            "username": "TEXT DEFAULT ''",
            "state": "TEXT DEFAULT ''",
            "country": "TEXT DEFAULT ''",
            "avatar_url": "TEXT DEFAULT ''",
            "previous_work": "TEXT DEFAULT ''",
            "availability": "TEXT DEFAULT ''",
            "tags_csv": "TEXT DEFAULT ''",
            "instrument": "TEXT DEFAULT ''",
            "services_csv": "TEXT DEFAULT ''",
            "profile_video": "TEXT DEFAULT ''",
            "instagram_url": "TEXT DEFAULT ''",
            "tiktok_url": "TEXT DEFAULT ''",
            "youtube_url": "TEXT DEFAULT ''",
            "spotify_url": "TEXT DEFAULT ''",
            "linkedin_url": "TEXT DEFAULT ''",
            "brent_account_id": "TEXT DEFAULT ''",
            "provider": "TEXT DEFAULT 'local'",
            "provider_id": "TEXT DEFAULT ''",
            "auth_provider": "TEXT DEFAULT 'local'",
            "authentication_provider": "TEXT DEFAULT 'local'",
            "profile_photo": "TEXT DEFAULT ''",
            "is_admin": "INTEGER DEFAULT 0",
            "is_founder": "INTEGER DEFAULT 0",
            "is_verified": "INTEGER DEFAULT 0",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            "last_login_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        }.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

        performance_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(performances)").fetchall()
        }
        for column, definition in {
            "audio_filename": "TEXT DEFAULT ''",
            "image_filename": "TEXT DEFAULT ''",
            "media_type": "TEXT DEFAULT ''",
            "media_url": "TEXT DEFAULT ''",
            "thumbnail_url": "TEXT DEFAULT ''",
            "genre": "TEXT DEFAULT ''",
            "city": "TEXT DEFAULT ''",
            "tags_csv": "TEXT DEFAULT ''",
            "category": "TEXT DEFAULT ''",
            "external_url": "TEXT DEFAULT ''",
            "views": "INTEGER DEFAULT 0",
            "likes": "INTEGER DEFAULT 0",
            "is_featured": "INTEGER DEFAULT 0",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        }.items():
            if column not in performance_columns:
                conn.execute(f"ALTER TABLE performances ADD COLUMN {column} {definition}")


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def first_uploaded_file(*field_names):
    for field_name in field_names:
        file_storage = request.files.get(field_name)
        if file_storage and file_storage.filename:
            return file_storage
    return None


def save_upload(file_storage, allowed_extensions, destination):
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_file(file_storage.filename, allowed_extensions):
        raise ValueError("That file type is not supported.")

    destination.mkdir(parents=True, exist_ok=True)
    original = secure_filename(file_storage.filename)
    extension = original.rsplit(".", 1)[1].lower()
    filename = f"{secrets.token_hex(12)}.{extension}"
    file_storage.save(destination / filename)
    return filename


def remove_upload(filename):
    if not filename:
        return
    filename = Path(filename).name
    for folder in (UPLOAD_DIR, PHOTO_DIR, VIDEO_DIR, AUDIO_DIR):
        path = folder / filename
        if path.exists() and path.is_file():
            path.unlink()


def brent_account_id(email):
    normalized = (email or "").strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"brent-local-{digest}"


def sso_b64encode(data):
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def sso_b64decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def sign_sso_payload(payload):
    body = sso_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        SSO_SHARED_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{sso_b64encode(signature)}"


def verify_sso_token(token):
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(
            SSO_SHARED_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(sso_b64decode(signature), expected):
            return None
        payload = json.loads(sso_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, TypeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def ensure_app_profile(conn, user_id, app_key="find-the-beat"):
    table_by_app = {
        "find-the-beat": "music_profiles",
        "lets-cook": "cook_profiles",
        "second-chance": "career_profiles",
        "beu": "travel_profiles",
    }
    table = table_by_app.get(app_key)
    if not table:
        return
    conn.execute(
        f"INSERT OR IGNORE INTO {table} (user_id, updated_at) VALUES (?, CURRENT_TIMESTAMP)",
        (user_id,),
    )


def sso_user_payload(user, target_app):
    display_name = user["display_name"] or user["full_name"] or user["email"].split("@")[0]
    provider = user["authentication_provider"] if "authentication_provider" in user.keys() else ""
    provider = provider or user["auth_provider"] or user["provider"] or AUTH_PROVIDER
    profile_photo = user["profile_photo"] if "profile_photo" in user.keys() else ""
    profile_photo = profile_photo or user["avatar_url"] or user["profile_pic"] or ""
    return {
        "iss": "brent-co-sso",
        "aud": target_app,
        "sub": user["brent_account_id"] or brent_account_id(user["email"]),
        "user_id": user["id"],
        "email": user["email"],
        "authentication_provider": provider,
        "display_name": display_name,
        "profile_photo": profile_photo,
        "is_admin": bool(user["is_admin"]),
        "is_founder": bool(user["is_founder"]),
        "iat": int(time.time()),
        "exp": int(time.time()) + SSO_TOKEN_TTL_SECONDS,
    }


def log_activity(user_id, event_type, description="", metadata=None):
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO activity_log (user_id, event_type, description, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    event_type,
                    description or "",
                    json.dumps(metadata or {}, separators=(",", ":")),
                ),
            )
    except Exception as exc:
        app.logger.warning("Activity log skipped: %s", exc)


def log_analytics_event(event_type="page_visit", feature="", metadata=None):
    if request.endpoint in {"uploaded_photo", "uploaded_video", "uploaded_audio", "static"}:
        return
    if request.path.startswith(("/static/", "/uploads/", "/favicon")):
        return
    try:
        visitor_id = session.setdefault("visitor_id", secrets.token_urlsafe(18))
        visitor_hash = hashlib.sha256(visitor_id.encode("utf-8")).hexdigest()[:24]
        user_id = session.get("user_id")
        state = ""
        if user_id:
            with get_db() as conn:
                row = conn.execute("SELECT state FROM users WHERE id = ?", (user_id,)).fetchone()
                state = row["state"] if row else ""
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO analytics_events
                    (user_id, visitor_hash, app_key, event_type, path, feature, state, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    visitor_hash,
                    "find-the-beat",
                    event_type,
                    request.path,
                    feature or request.endpoint or "",
                    state or "",
                    json.dumps(metadata or {}, separators=(",", ":")),
                ),
            )
    except Exception as exc:
        app.logger.debug("Analytics event skipped: %s", exc)


@app.before_request
def track_request_analytics():
    if request.method == "GET":
        log_analytics_event("page_visit")


def send_signup_notification(email, fields, provider="email/password"):
    if not SMTP_HOST or not SIGNUP_NOTIFY_EMAIL:
        app.logger.info("Signup notification skipped because SMTP is not configured.")
        return False

    display_name = fields.get("display_name") or fields.get("full_name") or "New user"
    role = fields.get("role") or "Not selected"
    city = fields.get("city") or ""
    state = fields.get("state") or ""
    location = ", ".join(part for part in (city, state) if part) or "Not provided"
    signup_time = time.strftime("%Y-%m-%d %H:%M:%S %Z")

    message = EmailMessage()
    message["Subject"] = f"New Find The Beat signup: {display_name}"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = SIGNUP_NOTIFY_EMAIL
    message.set_content(
        "\n".join(
            [
                "A new user registered in the Brent & Co ecosystem.",
                "",
                f"Name: {display_name}",
                f"Email: {email}",
                f"Role: {role}",
                f"City/State: {location}",
                f"Provider: {provider}",
                f"Signup time: {signup_time}",
            ]
        )
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception as exc:
        app.logger.warning("Signup notification failed: %s", exc)
        return False


def normalize_profile_role(role):
    role_key = (role or "").strip().lower()
    role_map = {
        "production": "Producer",
        "producer": "Producer",
        "composition": "Composer",
        "composer": "Composer",
        "artist": "Artist",
        "musician": "Musician",
    }
    return role_map.get(role_key, (role or "").strip())


def profile_form_fields():
    social_fields = {
        key: normalize_social_url(request.form.get(key, "").strip())
        for key in SOCIAL_FIELDS
    }
    selected_instruments = [
        item.strip()
        for item in request.form.getlist("instruments")
        if item.strip()
    ]
    manual_instrument = request.form.get("instrument", "").strip()
    instruments = [*selected_instruments, *split_csv(manual_instrument)]
    return {
        "display_name": request.form.get("display_name", "").strip(),
        "role": normalize_profile_role(request.form.get("role", "")),
        "genre": request.form.get("genre", "").strip(),
        "city": request.form.get("city", "").strip(),
        "state": request.form.get("state", "").strip(),
        "country": request.form.get("country", "").strip(),
        "bio": request.form.get("bio", "").strip(),
        "previous_work": request.form.get("previous_work", "").strip(),
        "availability": request.form.get("availability", "").strip(),
        "tags_csv": request.form.get("tags_csv", "").strip(),
        "instrument": ", ".join(dict.fromkeys(instruments)),
        "services_csv": request.form.get("services_csv", "").strip(),
        **social_fields,
    }


def uploaded_profile_media(current_pic="", current_video=""):
    profile_pic = current_pic or ""
    profile_video = current_video or ""
    new_pic = save_upload(
        first_uploaded_file("profile_pic", "photo"),
        ALLOWED_IMAGE_EXTENSIONS,
        PHOTO_DIR,
    )
    new_video = save_upload(
        first_uploaded_file("profile_video", "video"),
        ALLOWED_VIDEO_EXTENSIONS,
        VIDEO_DIR,
    )
    if new_pic:
        remove_upload(profile_pic)
        profile_pic = new_pic
    if new_video:
        remove_upload(profile_video)
        profile_video = new_video
    return profile_pic, profile_video


def create_user(email, password, fields, profile_pic):
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (
                email, password_hash, full_name, display_name, role, genre, city, state, country, bio,
                previous_work, availability,
                tags_csv, instrument, services_csv, profile_pic,
                instagram_url, tiktok_url, youtube_url, spotify_url, linkedin_url,
                brent_account_id, provider, auth_provider, authentication_provider, profile_photo, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                email,
                generate_password_hash(password),
                fields["display_name"],
                fields["display_name"],
                fields["role"],
                fields["genre"],
                fields["city"],
                fields["state"],
                fields["country"],
                fields["bio"],
                fields.get("previous_work", ""),
                fields.get("availability", ""),
                fields.get("tags_csv", ""),
                fields.get("instrument", ""),
                fields.get("services_csv", ""),
                profile_pic,
                fields.get("instagram_url", ""),
                fields.get("tiktok_url", ""),
                fields.get("youtube_url", ""),
                fields.get("spotify_url", ""),
                fields.get("linkedin_url", ""),
                brent_account_id(email),
                AUTH_PROVIDER,
                AUTH_PROVIDER,
                AUTH_PROVIDER,
                profile_pic,
            ),
        )
        user_id = cursor.lastrowid
        ensure_app_profile(conn, user_id, "find-the-beat")
    log_activity(
        user_id,
        "user_signed_up",
        "User signed up",
        {"role": fields.get("role", ""), "city": fields.get("city", ""), "state": fields.get("state", "")},
    )
    log_activity(user_id, "profile_created", "Initial profile created")
    send_signup_notification(email, fields, "email/password")
    return user_id


def update_user_profile(user_id, fields, profile_pic, profile_video):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE users
            SET full_name = COALESCE(NULLIF(full_name, ''), ?),
                display_name = ?, role = ?, genre = ?, city = ?, state = ?, country = ?, bio = ?,
                previous_work = ?, availability = ?, tags_csv = ?, instrument = ?, services_csv = ?,
                avatar_url = ?, profile_pic = ?, profile_video = ?,
                instagram_url = ?, tiktok_url = ?, youtube_url = ?,
                spotify_url = ?, linkedin_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                fields["display_name"],
                fields["display_name"],
                fields["role"],
                fields["genre"],
                fields["city"],
                fields["state"],
                fields["country"],
                fields["bio"],
                fields["previous_work"],
                fields["availability"],
                fields["tags_csv"],
                fields["instrument"],
                fields["services_csv"],
                profile_pic,
                profile_pic,
                profile_video,
                fields.get("instagram_url", ""),
                fields.get("tiktok_url", ""),
                fields.get("youtube_url", ""),
                fields.get("spotify_url", ""),
                fields.get("linkedin_url", ""),
                user_id,
            ),
        )


def upsert_oauth_user(provider, email, display_name="", avatar_url="", provider_id=""):
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip() or email.split("@")[0] or "Find The Beat Creator"
    if not email:
        raise ValueError("The sign-in provider did not return an email address.")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE users
                SET display_name = COALESCE(NULLIF(display_name, ''), ?),
                    full_name = COALESCE(NULLIF(full_name, ''), ?),
                    avatar_url = COALESCE(NULLIF(avatar_url, ''), ?),
                    profile_photo = COALESCE(NULLIF(profile_photo, ''), ?),
                    provider = ?, provider_id = ?, auth_provider = ?, authentication_provider = ?,
                    brent_account_id = COALESCE(NULLIF(brent_account_id, ''), ?),
                    last_login_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    display_name,
                    display_name,
                    avatar_url,
                    avatar_url,
                    provider,
                    provider_id,
                    provider,
                    provider,
                    brent_account_id(email),
                    row["id"],
                ),
            )
            ensure_app_profile(conn, row["id"], "find-the-beat")
            log_activity(row["id"], "user_logged_in", f"{provider.title()} login")
            return row["id"]
        cursor = conn.execute(
            """
            INSERT INTO users (
                email, password_hash, full_name, display_name, avatar_url,
                brent_account_id, provider, provider_id, auth_provider, authentication_provider,
                profile_photo, last_login_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                email,
                generate_password_hash(secrets.token_urlsafe(32)),
                display_name,
                display_name,
                avatar_url,
                brent_account_id(email),
                provider,
                provider_id,
                provider,
                provider,
                avatar_url,
            ),
        )
        user_id = cursor.lastrowid
        ensure_app_profile(conn, user_id, "find-the-beat")
    fields = {
        "display_name": display_name,
        "full_name": display_name,
        "role": "",
        "city": "",
        "state": "",
    }
    log_activity(user_id, "user_signed_up", f"User signed up with {provider}")
    log_activity(user_id, "profile_created", "OAuth profile created")
    log_activity(user_id, "user_logged_in", f"{provider.title()} login")
    send_signup_notification(email, fields, provider)
    return user_id


def create_performance(profile_id, title, description, video_filename, audio_filename, image_filename, thumb_filename, external_url=""):
    profile = get_profile(profile_id)
    media_type = (
        "video" if video_filename else
        "audio" if audio_filename else
        "image" if image_filename or thumb_filename else
        "link" if external_url else
        ""
    )
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO performances
                (profile_id, title, description, video_filename, audio_filename, image_filename,
                 thumb_filename, external_url, media_type, media_url, thumbnail_url, genre, city, tags_csv, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                title,
                description,
                video_filename,
                audio_filename,
                image_filename,
                thumb_filename,
                external_url,
                media_type,
                external_url,
                thumb_filename or image_filename,
                profile.genre if profile else "",
                profile.city if profile else "",
                profile.tags_csv if profile else "",
                profile.role if profile else "",
            ),
        )
        return cursor.lastrowid


def create_message(sender_id, recipient_id, body):
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (sender_id, recipient_id, body)
            VALUES (?, ?, ?)
            """,
            (sender_id, recipient_id, body),
        )
        message_id = cursor.lastrowid
    log_activity(
        sender_id,
        "message_sent",
        "Message sent",
        {"recipient_id": recipient_id, "message_id": message_id},
    )
    return message_id


def split_csv(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def valid_media_url(value):
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


SOCIAL_FIELDS = [
    "instagram_url",
    "tiktok_url",
    "youtube_url",
    "spotify_url",
    "linkedin_url",
]
INSTRUMENT_OPTIONS = [
    "Guitar",
    "Bass",
    "Drums",
    "Piano",
    "Keyboard",
    "Violin",
    "Viola",
    "Cello",
    "Banjo",
    "Mandolin",
    "Harmonica",
    "Saxophone",
    "Trumpet",
    "Trombone",
    "Clarinet",
    "Flute",
    "Percussion",
    "Tambourine",
    "DJ",
    "Other",
]
SEARCH_CATEGORIES = [
    {"slug": "production", "title": "Production", "terms": ["producer", "production", "beats", "beat production", "engineer", "mixing", "mastering"]},
    {"slug": "composers", "title": "Composers", "terms": ["composer", "composition", "score", "arrangement"]},
    {"slug": "artists", "title": "Artists", "terms": ["artist", "rapper", "performer"]},
    {"slug": "singers", "title": "Singers", "terms": ["singer", "vocalist", "vocals", "voice", "hooks", "background vocals"]},
    {"slug": "musicians", "title": "Musicians", "terms": ["musician", "instrumentalist", "band", "live", "guitar", "bass", "drums", "piano", "keyboard", "violin", "tambourine"]},
    {"slug": "showcases", "title": "Showcases", "terms": []},
]
INSTRUMENT_CATEGORY_REDIRECTS = {
    "guitar-players": "Guitar",
    "drummers": "Drums",
    "pianists": "Piano",
    "bassists": "Bass",
    "tambourine-players": "Tambourine",
}
STATE_ALIASES = {
    "ms": "mississippi",
    "mississippi": "ms",
    "ga": "georgia",
    "georgia": "ga",
    "il": "illinois",
    "illinois": "il",
    "tx": "texas",
    "texas": "tx",
    "tn": "tennessee",
    "tennessee": "tn",
    "la": "louisiana",
    "louisiana": "la",
}
STATE_COORDS = {
    "ms": (32.7416, -89.6787),
    "mississippi": (32.7416, -89.6787),
    "ga": (33.0406, -83.6431),
    "georgia": (33.0406, -83.6431),
    "il": (40.3495, -88.9861),
    "illinois": (40.3495, -88.9861),
    "tx": (31.0545, -97.5635),
    "texas": (31.0545, -97.5635),
    "tn": (35.7478, -86.6923),
    "tennessee": (35.7478, -86.6923),
    "la": (31.1695, -91.8678),
    "louisiana": (31.1695, -91.8678),
}
CITY_COORDS = {
    "atlanta, ga": (33.7490, -84.3880),
    "atlanta, georgia": (33.7490, -84.3880),
    "brookhaven, ms": (31.5791, -90.4407),
    "brookhaven, mississippi": (31.5791, -90.4407),
    "chicago, il": (41.8781, -87.6298),
    "chicago, illinois": (41.8781, -87.6298),
    "dallas, tx": (32.7767, -96.7970),
    "dallas, texas": (32.7767, -96.7970),
    "houston, tx": (29.7604, -95.3698),
    "houston, texas": (29.7604, -95.3698),
    "jackson, ms": (32.2988, -90.1848),
    "jackson, mississippi": (32.2988, -90.1848),
    "mccomb, ms": (31.2438, -90.4532),
    "mccomb, mississippi": (31.2438, -90.4532),
    "memphis, tn": (35.1495, -90.0490),
    "memphis, tennessee": (35.1495, -90.0490),
    "new orleans, la": (29.9511, -90.0715),
    "new orleans, louisiana": (29.9511, -90.0715),
}


def category_by_slug(slug):
    return next((category for category in SEARCH_CATEGORIES if category["slug"] == slug), None)


def location_terms(value):
    value = (value or "").strip()
    if not value:
        return []
    alias = STATE_ALIASES.get(value.lower())
    return [value, alias] if alias else [value]


def profile_coordinates(profile):
    city = (profile.city or "").strip().lower()
    state = (profile.state or "").strip().lower()
    if city and state:
        direct = CITY_COORDS.get(f"{city}, {state}")
        if direct:
            return direct
        alias = STATE_ALIASES.get(state)
        if alias:
            direct = CITY_COORDS.get(f"{city}, {alias}")
            if direct:
                return direct
    if state:
        return STATE_COORDS.get(state) or STATE_COORDS.get(STATE_ALIASES.get(state, ""))
    return None


def normalize_social_url(value):
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Social links need to be valid web links.")
    return value


def row_to_profile(row):
    if row is None:
        return None
    data = dict(row)
    data.setdefault("full_name", "")
    data.setdefault("username", "")
    data.setdefault("state", "")
    data.setdefault("country", "")
    data.setdefault("avatar_url", "")
    data.setdefault("profile_pic", "")
    data.setdefault("profile_video", "")
    data.setdefault("previous_work", "")
    data.setdefault("availability", "")
    data.setdefault("tags_csv", "")
    data.setdefault("instrument", "")
    data.setdefault("services_csv", "")
    data.setdefault("brent_account_id", "")
    data.setdefault("provider", AUTH_PROVIDER)
    data.setdefault("provider_id", "")
    data.setdefault("auth_provider", AUTH_PROVIDER)
    data.setdefault("is_admin", 0)
    data.setdefault("is_founder", 0)
    data.setdefault("is_verified", 0)
    data.setdefault("created_at", "")
    data.setdefault("last_login_at", "")
    data.setdefault("updated_at", "")
    data["brent_account_id"] = data["brent_account_id"] or brent_account_id(data.get("email", ""))
    data["provider"] = data["provider"] or data["auth_provider"] or AUTH_PROVIDER
    data["auth_provider"] = data["auth_provider"] or data["provider"] or AUTH_PROVIDER
    data["is_admin"] = bool(data.get("is_admin"))
    data["is_founder"] = bool(data.get("is_founder"))
    data["is_verified"] = bool(data.get("is_verified"))
    data["photo_filename"] = data.get("profile_pic") or ""
    data["avatar_url"] = data.get("avatar_url") or data["photo_filename"] or ""
    data["video_filename"] = data.get("profile_video") or ""
    data["name"] = data.get("display_name") or ""
    data["fullName"] = data.get("full_name") or data["name"]
    data["displayName"] = data["name"]
    data["username"] = data.get("username") or ""
    data["providerId"] = data.get("provider_id") or ""
    data["initials"] = "".join(part[:1] for part in (data["name"] or data["email"] or "SB").replace("/", " ").split()[:2]).upper() or "SB"
    data["tags"] = split_csv(data.get("tags_csv", ""))
    data["instruments"] = split_csv(data.get("instrument", ""))
    data["services"] = split_csv(data.get("services_csv", ""))
    for field in SOCIAL_FIELDS:
        data.setdefault(field, "")
    data["social_links"] = [
        ("Instagram", data["instagram_url"]),
        ("TikTok", data["tiktok_url"]),
        ("YouTube", data["youtube_url"]),
        ("Spotify", data["spotify_url"]),
        ("LinkedIn", data["linkedin_url"]),
    ]
    data["social_links"] = [(label, url) for label, url in data["social_links"] if url]
    official_badges = []
    if data["is_founder"]:
        official_badges.extend(["Founder", "Brent & Co"])
    if data["is_verified"]:
        official_badges.append("Verified")
    profile_badges = [
        item
        for item in [data.get("role"), data.get("instrument"), *data["tags"][:3]]
        if item
    ]
    data["official_badges"] = list(dict.fromkeys(official_badges))
    data["badges"] = list(dict.fromkeys([*official_badges, *profile_badges]))
    return SimpleNamespace(**data)


def row_to_performance(row, profile=None):
    if row is None:
        return None
    data = dict(row)
    data.setdefault("video_filename", "")
    data.setdefault("audio_filename", "")
    data.setdefault("image_filename", "")
    data.setdefault("thumb_filename", "")
    data.setdefault("media_type", "")
    data.setdefault("media_url", "")
    data.setdefault("thumbnail_url", "")
    data.setdefault("genre", "")
    data.setdefault("city", "")
    data.setdefault("tags_csv", "")
    data.setdefault("category", "")
    data.setdefault("external_url", "")
    data.setdefault("views", 0)
    data.setdefault("likes", 0)
    data.setdefault("is_featured", 0)
    data["views"] = int(data.get("views") or 0)
    data["likes"] = int(data.get("likes") or 0)
    data["is_featured"] = bool(data.get("is_featured"))
    data["thumbnail_filename"] = data.get("thumbnail_url") or data.get("thumb_filename") or data.get("image_filename") or ""
    data["media_type"] = data.get("media_type") or ("video" if data.get("video_filename") else "audio" if data.get("audio_filename") else "image" if data.get("image_filename") or data.get("thumb_filename") else "link" if data.get("external_url") else "empty")
    if profile:
        data["genre"] = data.get("genre") or profile.genre
        data["city"] = data.get("city") or profile.city
        data["tags_csv"] = data.get("tags_csv") or profile.tags_csv
        data["category"] = data.get("category") or profile.role
    data["profile"] = profile
    return SimpleNamespace(**data)


def row_to_message(row, sender=None, recipient=None, other=None):
    if row is None:
        return None
    data = dict(row)
    data["sender"] = sender
    data["recipient"] = recipient
    data["other"] = other
    created_at = data.get("created_at") or ""
    data["created_label"] = created_at[:16].replace("T", " ")
    return SimpleNamespace(**data)


def unread_message_count(user_id):
    if not user_id:
        return 0
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE recipient_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
    return int(row["count"] or 0)


def profile_completion(user):
    if not user:
        return {"percent": 0, "items": []}
    try:
        has_performance = bool(get_performances(profile_id=user.id))
    except Exception:
        app.logger.exception("Profile completion performance check failed")
        has_performance = False
    checks = [
        ("Add profile photo", bool(getattr(user, "profile_pic", ""))),
        ("Add talent", bool(getattr(user, "role", "") or getattr(user, "instrument", "") or getattr(user, "services_csv", ""))),
        ("Add genre", bool(getattr(user, "genre", ""))),
        ("Add city", bool(getattr(user, "city", ""))),
        ("Add bio", bool(getattr(user, "bio", ""))),
        ("Add previous work", bool(getattr(user, "previous_work", ""))),
        ("Add availability", bool(getattr(user, "availability", ""))),
        ("Add social links", bool(getattr(user, "social_links", []))),
        ("Add first performance", has_performance),
    ]
    complete = sum(1 for _, done in checks if done)
    return {
        "percent": round((complete / len(checks)) * 100),
        "items": checks,
    }


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.OperationalError:
        app.logger.exception("Current user lookup failed; retrying after schema init")
        init_db()
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_profile(row)


@app.context_processor
def inject_user_context():
    try:
        user = current_user()
        unread = unread_message_count(user.id) if user else 0
    except Exception:
        app.logger.exception("Template user context failed")
        user = None
        unread = 0
    return {
        "user": user,
        "unread_count": unread,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please log in first.")
            return redirect(url_for("login"))
        if (user.email or "").strip().lower() != ADMIN_EMAIL:
            flash("That area is only available to the Brent & Co founder account.")
            return redirect(url_for("home"))
        return view(*args, **kwargs)

    return wrapped


ADMIN_APP_TABLES = {
    "find-the-beat": ("Find The Beat", "music_profiles"),
    "lets-cook": ("Let's Cook Y'all", "cook_profiles"),
    "second-chance": ("Second Chance Careers", "career_profiles"),
    "beu": ("BEU", "travel_profiles"),
}


def admin_user_apps(conn, user_id):
    apps = []
    for key, (label, table) in ADMIN_APP_TABLES.items():
        row = conn.execute(f"SELECT user_id FROM {table} WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            apps.append({"key": key, "label": label})
    return apps


def admin_profile_completion(row, apps=None):
    fields = [
        row["display_name"],
        row["role"],
        row["genre"],
        row["city"],
        row["state"],
        row["bio"],
        row["instrument"],
        row["services_csv"],
        row["avatar_url"] or row["profile_pic"] or row["profile_photo"],
    ]
    completed = sum(1 for value in fields if (value or "").strip())
    if apps:
        completed += 1
    total = len(fields) + 1
    percent = int(round((completed / total) * 100))
    return {
        "percent": percent,
        "label": "Complete" if percent >= 80 else "In progress" if percent >= 40 else "Needs info",
    }


def admin_is_online(row):
    return bool(row["last_login_at"] and "0000" not in str(row["last_login_at"]))


def admin_user_card(conn, row):
    apps = admin_user_apps(conn, row["id"])
    data = dict(row)
    data["apps"] = apps
    data["app_labels"] = ", ".join(app["label"] for app in apps) or "Not linked yet"
    data["status"] = "online" if admin_is_online(row) else "offline"
    data["completion"] = admin_profile_completion(row, apps)
    return data


def admin_user_directory(conn, filters):
    clauses = []
    params = []
    search = filters.get("q", "").strip()
    if search:
        like = f"%{search}%"
        clauses.append(
            "(u.display_name LIKE ? OR u.full_name LIKE ? OR u.email LIKE ? OR u.city LIKE ? OR u.state LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    for field in ("role", "state", "city"):
        value = filters.get(field, "").strip()
        if value:
            clauses.append(f"lower(u.{field}) = lower(?)")
            params.append(value)
    if filters.get("active"):
        clauses.append("u.last_login_at IS NOT NULL AND u.last_login_at != ''")
    signup_date = filters.get("signup_date", "").strip()
    if signup_date:
        clauses.append("date(u.created_at) = date(?)")
        params.append(signup_date)

    app_key = filters.get("app", "").strip()
    join_sql = ""
    if app_key in ADMIN_APP_TABLES:
        join_sql = f"INNER JOIN {ADMIN_APP_TABLES[app_key][1]} ap ON ap.user_id = u.id"

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT DISTINCT u.*
        FROM users u
        {join_sql}
        {where_sql}
        ORDER BY datetime(u.created_at) DESC, u.id DESC
        LIMIT 200
        """,
        tuple(params),
    ).fetchall()
    users = [admin_user_card(conn, row) for row in rows]
    if filters.get("incomplete"):
        users = [user for user in users if user["completion"]["percent"] < 80]
    return users


def admin_distinct_options(conn, column):
    return [
        row[column]
        for row in conn.execute(
            f"SELECT DISTINCT {column} FROM users WHERE COALESCE({column}, '') != '' ORDER BY {column}"
        ).fetchall()
    ]


def admin_analytics_summary(conn):
    return {
        "page_visits": conn.execute("SELECT COUNT(*) FROM analytics_events WHERE event_type = 'page_visit'").fetchone()[0],
        "unique_visitors": conn.execute("SELECT COUNT(DISTINCT visitor_hash) FROM analytics_events").fetchone()[0],
        "most_active_app": conn.execute(
            """
            SELECT app_key, COUNT(*) AS count
            FROM analytics_events
            GROUP BY app_key
            ORDER BY count DESC
            LIMIT 1
            """
        ).fetchone(),
        "most_active_state": conn.execute(
            """
            SELECT state, COUNT(*) AS count
            FROM analytics_events
            WHERE COALESCE(state, '') != ''
            GROUP BY state
            ORDER BY count DESC
            LIMIT 1
            """
        ).fetchone(),
        "top_features": conn.execute(
            """
            SELECT feature, COUNT(*) AS count
            FROM analytics_events
            WHERE COALESCE(feature, '') != ''
            GROUP BY feature
            ORDER BY count DESC
            LIMIT 5
            """
        ).fetchall(),
    }


def admin_app_profile_context(conn, user_id):
    return {
        "find_the_beat": conn.execute("SELECT * FROM music_profiles WHERE user_id = ?", (user_id,)).fetchone(),
        "lets_cook": conn.execute("SELECT * FROM cook_profiles WHERE user_id = ?", (user_id,)).fetchone(),
        "second_chance": conn.execute("SELECT * FROM career_profiles WHERE user_id = ?", (user_id,)).fetchone(),
        "beu": conn.execute("SELECT * FROM travel_profiles WHERE user_id = ?", (user_id,)).fetchone(),
    }


@app.context_processor
def inject_user():
    try:
        user = current_user()
    except Exception:
        app.logger.exception("Template app context user lookup failed")
        user = None
    return {
        "user": user,
        "brent_co_url": BRENT_CO_URL,
        "find_the_beat_url": FIND_THE_BEAT_URL,
        "second_chance_url": SECOND_CHANCE_URL,
        "ga_measurement_id": GA_MEASUREMENT_ID,
        "plausible_domain": PLAUSIBLE_DOMAIN,
        "admin_email": ADMIN_EMAIL,
    }


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    return response


def get_profile(profile_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (profile_id,)).fetchone()
    return row_to_profile(row)


def search_profiles(q="", role="", genre="", city="", state="", country="", instrument="", services="", tags=""):
    clauses = []
    params = []
    if q:
        needle = f"%{q}%"
        clauses.append(
            """
            (display_name LIKE ? OR role LIKE ? OR genre LIKE ? OR city LIKE ? OR state LIKE ? OR country LIKE ?
             OR bio LIKE ? OR tags_csv LIKE ? OR instrument LIKE ? OR services_csv LIKE ?)
            """
        )
        params.extend([needle] * 10)
    if role:
        clauses.append("role LIKE ?")
        params.append(f"%{role}%")
    if genre:
        clauses.append("genre LIKE ?")
        params.append(f"%{genre}%")
    if city:
        clauses.append("(city LIKE ? OR state LIKE ? OR country LIKE ?)")
        params.extend([f"%{city}%", f"%{city}%", f"%{city}%"])
    if state:
        terms = location_terms(state)
        state_clauses = []
        for term in terms:
            state_clauses.append("(state LIKE ? OR city LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])
        clauses.append("(" + " OR ".join(state_clauses) + ")")
    if country:
        clauses.append("country LIKE ?")
        params.append(f"%{country}%")
    if instrument:
        clauses.append("(instrument LIKE ? OR services_csv LIKE ?)")
        params.extend([f"%{instrument}%", f"%{instrument}%"])
    if services:
        clauses.append("services_csv LIKE ?")
        params.append(f"%{services}%")
    if tags:
        clauses.append("(tags_csv LIKE ? OR services_csv LIKE ? OR role LIKE ?)")
        params.extend([f"%{tags}%", f"%{tags}%", f"%{tags}%"])

    sql = "SELECT * FROM users"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY is_founder DESC, is_verified DESC, id DESC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_profile(row) for row in rows]


def profile_matches_category(profile, category):
    haystack = " ".join(
        [
            profile.role or "",
            profile.instrument or "",
            profile.services_csv or "",
            profile.tags_csv or "",
            profile.genre or "",
            profile.bio or "",
        ]
    ).lower()
    return any(term.lower() in haystack for term in category["terms"])


def search_category_profiles(category, filters):
    profiles = search_profiles(
        q=filters.get("q", ""),
        role=filters.get("role", ""),
        genre=filters.get("genre", ""),
        city=filters.get("city", ""),
        state=filters.get("state", ""),
        country=filters.get("country", ""),
        instrument=filters.get("instrument", ""),
        services=filters.get("services", ""),
    )
    return [profile for profile in profiles if profile_matches_category(profile, category)]


def seed_demo_profiles_if_empty():
    demo_profiles = [
        {
            "email": "sample.producer.dallas@example.com",
            "display_name": "Sample Dallas Producer",
            "role": "Producer",
            "genre": "Hip-Hop, R&B",
            "city": "Dallas, TX",
            "bio": "Sample profile only: a Dallas producer looking for artists, songwriters, and engineers to build polished records.",
            "tags_csv": "Sample Data, Available for Collabs, Producer",
            "instrument": "Keys, Beat Production",
            "services_csv": "Production, Arrangement, Mixing Prep",
        },
        {
            "email": "sample.vocalist.atlanta@example.com",
            "display_name": "Sample Atlanta Vocalist",
            "role": "Vocalist",
            "genre": "Soul, Pop, Gospel",
            "city": "Atlanta, GA",
            "bio": "Sample profile only: a vocalist with warm tone, harmony skills, and interest in studio sessions or live features.",
            "tags_csv": "Sample Data, Vocalist, Available for Collabs",
            "instrument": "Voice",
            "services_csv": "Hooks, Background Vocals, Live Performance",
        },
        {
            "email": "sample.drummer.houston@example.com",
            "display_name": "Sample Houston Drummer",
            "role": "Musician",
            "genre": "Funk, Gospel, Live Band",
            "city": "Houston, TX",
            "bio": "Sample profile only: a drummer available for live shows, rehearsals, and studio tracking.",
            "tags_csv": "Sample Data, Drummer, Live Ready",
            "instrument": "Drums",
            "services_csv": "Live Drums, Studio Tracking, Rehearsals",
        },
        {
            "email": "sample.songwriter.memphis@example.com",
            "display_name": "Sample Memphis Songwriter",
            "role": "Songwriter",
            "genre": "Country Soul, R&B",
            "city": "Memphis, TN",
            "bio": "Sample profile only: a songwriter focused on hooks, storytelling, and artist development sessions.",
            "tags_csv": "Sample Data, Songwriter, Available for Collabs",
            "instrument": "Lyrics, Melody",
            "services_csv": "Topline Writing, Lyrics, Song Concepts",
        },
    ]
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count:
            return
        for profile in demo_profiles:
            conn.execute(
                """
                INSERT INTO users (
                    email, password_hash, display_name, role, genre, city, bio,
                    tags_csv, instrument, services_csv
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile["email"],
                    generate_password_hash(secrets.token_urlsafe(24)),
                    profile["display_name"],
                    profile["role"],
                    profile["genre"],
                    profile["city"],
                    profile["bio"],
                    profile["tags_csv"],
                    profile["instrument"],
                    profile["services_csv"],
                ),
            )


def seed_founder_profile():
    with get_db() as conn:
        for email in LEGACY_REMOVED_FOUNDER_EMAILS:
            conn.execute(
                """
                UPDATE users
                SET is_admin = 0,
                    is_founder = 0,
                    is_verified = 0,
                    role = CASE WHEN lower(role) = 'admin' THEN 'user' ELSE role END,
                    tags_csv = REPLACE(REPLACE(REPLACE(tags_csv, 'Founder, ', ''), ', Founder', ''), 'Founder', ''),
                    updated_at = CURRENT_TIMESTAMP
                WHERE lower(email) = lower(?)
                """,
                (email,),
            )

        for founder in FOUNDER_PROFILES:
            email = founder["email"]
            if not email:
                continue
            owner_values = {
                "email": email,
                "full_name": founder.get("full_name") or founder["display_name"],
                "display_name": founder["display_name"],
                "role": "admin",
                "genre": "Brent & Co Ecosystem",
                "city": "Brent & Co",
                "bio": OWNER_BIO,
                "tags_csv": "Founder, Brent & Co, Verified",
                "instrument": "Ecosystem Builder",
                "services_csv": "Creator connection, community support, app ecosystem",
                "brent_account_id": brent_account_id(email),
                "auth_provider": OWNER_AUTH_PROVIDER,
            }
            existing = conn.execute(
                "SELECT * FROM users WHERE lower(email) = lower(?)",
                (email,),
            ).fetchone()
            if existing:
                password_sql = ", password_hash = ?" if OWNER_INITIAL_PASSWORD else ""
                password_args = (
                    [generate_password_hash(OWNER_INITIAL_PASSWORD)]
                    if OWNER_INITIAL_PASSWORD
                    else []
                )
                conn.execute(
                    f"""
                    UPDATE users
                    SET full_name = ?, display_name = ?, role = ?, genre = ?, city = ?, bio = ?,
                        tags_csv = ?, instrument = ?, services_csv = ?,
                        brent_account_id = ?, provider = ?, auth_provider = ?,
                        authentication_provider = COALESCE(NULLIF(authentication_provider, ''), ?),
                        is_admin = 1, is_founder = 1, is_verified = 1{password_sql},
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        owner_values["full_name"],
                        owner_values["display_name"],
                        owner_values["role"],
                        owner_values["genre"],
                        owner_values["city"],
                        owner_values["bio"],
                        owner_values["tags_csv"],
                        owner_values["instrument"],
                        owner_values["services_csv"],
                        owner_values["brent_account_id"],
                        owner_values["auth_provider"],
                        owner_values["auth_provider"],
                        owner_values["auth_provider"],
                        *password_args,
                        existing["id"],
                    ),
                )
                ensure_app_profile(conn, existing["id"], "find-the-beat")
                continue
            conn.execute(
                """
                INSERT INTO users (
                    email, password_hash, full_name, display_name, role, genre, city, bio,
                    tags_csv, instrument, services_csv, brent_account_id,
                    provider, auth_provider, authentication_provider, is_admin, is_founder, is_verified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1)
                """,
                (
                    owner_values["email"],
                    generate_password_hash(
                        OWNER_INITIAL_PASSWORD or secrets.token_urlsafe(32)
                    ),
                    owner_values["full_name"],
                    owner_values["display_name"],
                    owner_values["role"],
                    owner_values["genre"],
                    owner_values["city"],
                    owner_values["bio"],
                    owner_values["tags_csv"],
                    owner_values["instrument"],
                    owner_values["services_csv"],
                    owner_values["brent_account_id"],
                    owner_values["auth_provider"],
                    owner_values["auth_provider"],
                    owner_values["auth_provider"],
                ),
            )
            new_owner = conn.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
            if new_owner:
                ensure_app_profile(conn, new_owner["id"], "find-the-beat")


def second_chance_category(slug):
    return next(
        (category for category in SECOND_CHANCE_CATEGORIES if category["slug"] == slug),
        None,
    )


def second_chance_resource_group(slug):
    return next(
        (group for group in SECOND_CHANCE_RESOURCE_GROUPS if group["slug"] == slug),
        None,
    )


def get_performances(profile_id=None):
    sql = "SELECT * FROM performances"
    params = []
    if profile_id is not None:
        sql += " WHERE profile_id = ?"
        params.append(profile_id)
    sql += " ORDER BY id DESC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        profile_ids = {row["profile_id"] for row in rows}
        profiles = {}
        if profile_ids:
            placeholders = ",".join("?" for _ in profile_ids)
            profile_rows = conn.execute(
                f"SELECT * FROM users WHERE id IN ({placeholders})", tuple(profile_ids)
            ).fetchall()
            profiles = {row["id"]: row_to_profile(row) for row in profile_rows}

    return [row_to_performance(row, profiles.get(row["profile_id"])) for row in rows]


def get_showcase_tiles(limit=6, role=None, profile_id=None):
    role_key = (role or "").strip().lower()
    performances = get_performances(profile_id=profile_id)
    if role_key:
        performances = [
            perf
            for perf in performances
            if perf.profile and role_key in (perf.profile.role or "").lower()
        ]
    performances = sorted(
        performances,
        key=lambda perf: (bool(perf.is_featured), perf.views, perf.likes, perf.id),
        reverse=True,
    )
    return performances[:limit]


def showcase_context():
    performances = get_performances()
    profiles = search_profiles()

    featured_performances = [
        perf
        for perf in performances
        if perf.is_featured
        or perf.video_filename
        or perf.audio_filename
        or perf.image_filename
        or perf.external_url
    ][:6] or performances[:6]
    trending_performances = sorted(
        performances,
        key=lambda perf: (perf.views, perf.likes, perf.id),
        reverse=True,
    )[:8]

    def role_profiles(role):
        return search_profiles(role=role)[:6]

    local_spotlight = [
        perf
        for perf in performances
        if perf.profile and (perf.profile.city or perf.profile.state)
    ][:8] or performances[:8]
    featured_artists = role_profiles("artist")

    return {
        "this_week_showcases": featured_performances,
        "featured_performances": featured_performances,
        "trending_performances": trending_performances,
        "new_uploads": performances[:8],
        "local_spotlight": local_spotlight,
        "featured_artists": featured_artists,
    }


def get_user_map(user_ids):
    user_ids = {int(user_id) for user_id in user_ids if user_id}
    if not user_ids:
        return {}
    placeholders = ",".join("?" for _ in user_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM users WHERE id IN ({placeholders})",
            tuple(user_ids),
        ).fetchall()
    return {row["id"]: row_to_profile(row) for row in rows}


def get_inbox_messages(user_id):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM messages
            WHERE sender_id = ? OR recipient_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (user_id, user_id),
        ).fetchall()
    users = get_user_map(
        {row["sender_id"] for row in rows} | {row["recipient_id"] for row in rows}
    )
    return [
        row_to_message(
            row,
            sender=users.get(row["sender_id"]),
            recipient=users.get(row["recipient_id"]),
            other=users.get(row["recipient_id"] if row["sender_id"] == user_id else row["sender_id"]),
        )
        for row in rows
    ]


def get_thread_messages(user_id, other_id):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM messages
            WHERE (sender_id = ? AND recipient_id = ?)
               OR (sender_id = ? AND recipient_id = ?)
            ORDER BY datetime(created_at) ASC, id ASC
            """,
            (user_id, other_id, other_id, user_id),
        ).fetchall()
        conn.execute(
            "UPDATE messages SET is_read = 1 WHERE sender_id = ? AND recipient_id = ?",
            (other_id, user_id),
        )
    users = get_user_map({user_id, other_id})
    return [
        row_to_message(
            row,
            sender=users.get(row["sender_id"]),
            recipient=users.get(row["recipient_id"]),
        )
        for row in rows
    ]


@app.route("/second-chance")
def second_chance_home():
    return render_template(
        "second_chance/home.html",
        categories=SECOND_CHANCE_CATEGORIES,
        search_items=SECOND_CHANCE_SEARCH_ITEMS[:5],
        features=SECOND_CHANCE_FEATURES,
        checklist=SECOND_CHANCE_CHECKLIST,
    )


@app.route("/my-path")
@app.route("/second-chance/my-path")
def second_chance_my_path():
    return render_template(
        "second_chance/my_path.html",
        profile=current_user(),
        checklist=SECOND_CHANCE_CHECKLIST,
        job_help=SECOND_CHANCE_JOB_HELP,
        features=SECOND_CHANCE_FEATURES,
        resource_groups=SECOND_CHANCE_RESOURCE_GROUPS,
    )


@app.route("/second-chance/resources")
def second_chance_resources():
    return render_template(
        "second_chance/resources.html",
        groups=SECOND_CHANCE_RESOURCE_GROUPS,
        active_group=None,
    )


@app.route("/second-chance/resources/<slug>")
def second_chance_resource_page(slug):
    group = second_chance_resource_group(slug)
    if not group:
        flash("That resource section was not found.")
        return redirect(url_for("second_chance_resources"))
    return render_template(
        "second_chance/resources.html",
        groups=SECOND_CHANCE_RESOURCE_GROUPS,
        active_group=group,
    )


@app.route("/second-chance/search")
def second_chance_search():
    q = request.args.get("q", "").strip()
    focus = request.args.get("focus", "").strip()
    return render_template(
        "second_chance/search.html",
        search_items=SECOND_CHANCE_SEARCH_ITEMS,
        job_help=SECOND_CHANCE_JOB_HELP,
        resource_groups=SECOND_CHANCE_RESOURCE_GROUPS,
        q=q,
        focus=focus,
    )


@app.route("/second-chance/category/<slug>")
def second_chance_category_page(slug):
    category = second_chance_category(slug)
    if not category:
        flash("That Second Chance section was not found.")
        return redirect(url_for("second_chance_home"))
    return render_template("second_chance/category.html", category=category)


@app.route("/second-chance/signup", methods=["GET", "POST"])
def second_chance_signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        display_name = request.form.get("display_name", "").strip()

        if not email or not password or not display_name:
            flash("Name, email, and password are required.")
            return redirect(url_for("second_chance_signup"))
        if len(password) < 8:
            flash("Please choose a password with at least 8 characters.")
            return redirect(url_for("second_chance_signup"))
        if confirm_password and password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("second_chance_signup"))

        fields = {
            "display_name": display_name,
            "role": "Second Chance Member",
            "genre": "Career readiness",
            "city": request.form.get("city", "").strip(),
            "state": "",
            "country": "",
            "bio": "Building a new career path with Second Chance Careers.",
            "tags_csv": "resume, jobs, life skills",
            "instrument": "",
            "services_csv": ", ".join(request.form.getlist("skills")),
        }

        try:
            profile_pic, _ = uploaded_profile_media()
            user_id = create_user(email, password, fields, profile_pic)
        except sqlite3.IntegrityError:
            flash("An account with that email already exists. Please sign in.")
            return redirect(url_for("login"))
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("second_chance_signup"))

        session["user_id"] = user_id
        flash("Welcome to Second Chance Careers.")
        return redirect(url_for("second_chance_profile"))

    return render_template("second_chance/signup.html")


@app.route("/second-chance/profile")
def second_chance_profile():
    return render_template(
        "second_chance/profile.html",
        profile=current_user(),
        skills=SECOND_CHANCE_SKILLS,
        search_items=SECOND_CHANCE_SEARCH_ITEMS[:4],
        checklist=SECOND_CHANCE_CHECKLIST,
        job_help=SECOND_CHANCE_JOB_HELP,
        resource_groups=SECOND_CHANCE_RESOURCE_GROUPS,
    )


@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    genre = request.args.get("genre", "").strip()
    city = request.args.get("city", "").strip()
    creators = search_profiles(q, role, genre, city)[:4]
    return render_template(
        "index.html",
        creators=creators,
        featured_showcase=get_showcase_tiles(limit=6),
        category_tiles=SEARCH_CATEGORIES,
        q=q,
        role_filter=role,
        genre_filter=genre,
        city_filter=city,
    )


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/admin")
@admin_required
def admin_dashboard():
    filters = {
        "q": request.args.get("q", "").strip(),
        "app": request.args.get("app", "").strip(),
        "role": request.args.get("role", "").strip(),
        "state": request.args.get("state", "").strip(),
        "city": request.args.get("city", "").strip(),
        "signup_date": request.args.get("signup_date", "").strip(),
        "active": request.args.get("active", "").strip(),
        "incomplete": request.args.get("incomplete", "").strip(),
    }
    with get_db() as conn:
        stats = {
            "total_users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "online_now": conn.execute(
                "SELECT COUNT(*) FROM users WHERE datetime(last_login_at) >= datetime('now', '-15 minutes')"
            ).fetchone()[0],
            "new_today": conn.execute(
                "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
            ).fetchone()[0],
            "new_week": conn.execute(
                "SELECT COUNT(*) FROM users WHERE datetime(created_at) >= datetime('now', '-7 days')"
            ).fetchone()[0],
            "new_month": conn.execute(
                "SELECT COUNT(*) FROM users WHERE datetime(created_at) >= datetime('now', '-30 days')"
            ).fetchone()[0],
            "profile_count": conn.execute(
                "SELECT COUNT(*) FROM users WHERE COALESCE(display_name, '') != ''"
            ).fetchone()[0],
            "active_week": conn.execute(
                "SELECT COUNT(*) FROM users WHERE datetime(last_login_at) >= datetime('now', '-7 days')"
            ).fetchone()[0],
            "upload_count": conn.execute("SELECT COUNT(*) FROM performances").fetchone()[0],
            "message_count": conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "showcase_count": conn.execute(
                "SELECT COUNT(*) FROM performances WHERE is_featured = 1 OR COALESCE(media_type, '') != ''"
            ).fetchone()[0],
            "music_profiles": conn.execute("SELECT COUNT(*) FROM music_profiles").fetchone()[0],
            "cook_profiles": conn.execute("SELECT COUNT(*) FROM cook_profiles").fetchone()[0],
            "career_profiles": conn.execute("SELECT COUNT(*) FROM career_profiles").fetchone()[0],
            "travel_profiles": conn.execute("SELECT COUNT(*) FROM travel_profiles").fetchone()[0],
        }
        users_per_app = [
            {"name": "Find The Beat", "count": stats["music_profiles"], "url": url_for("sso_start", app="find-the-beat")},
            {"name": "Let's Cook Y'all", "count": stats["cook_profiles"], "url": url_for("sso_start", app="lets-cook")},
            {"name": "Second Chance", "count": stats["career_profiles"], "url": url_for("sso_start", app="second-chance")},
            {"name": "BEU", "count": stats["travel_profiles"], "url": url_for("sso_start", app="beu")},
        ]
        latest_user_rows = conn.execute(
            """
            SELECT *
            FROM users
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 8
            """
        ).fetchall()
        latest_users = [admin_user_card(conn, row) for row in latest_user_rows]
        directory_users = admin_user_directory(conn, filters)
        filter_options = {
            "roles": admin_distinct_options(conn, "role"),
            "states": admin_distinct_options(conn, "state"),
            "cities": admin_distinct_options(conn, "city"),
            "apps": [{"key": key, "label": label} for key, (label, _) in ADMIN_APP_TABLES.items()],
        }
        latest_messages = conn.execute(
            """
            SELECT m.id, m.body, m.created_at,
                   sender.display_name AS sender_name, sender.email AS sender_email,
                   recipient.display_name AS recipient_name, recipient.email AS recipient_email
            FROM messages m
            LEFT JOIN users sender ON sender.id = m.sender_id
            LEFT JOIN users recipient ON recipient.id = m.recipient_id
            ORDER BY datetime(m.created_at) DESC, m.id DESC
            LIMIT 8
            """
        ).fetchall()
        latest_uploads = conn.execute(
            """
            SELECT p.id, p.title, p.created_at, p.media_type, u.display_name, u.email, u.city, u.state
            FROM performances p
            LEFT JOIN users u ON u.id = p.profile_id
            ORDER BY datetime(p.created_at) DESC, p.id DESC
            LIMIT 8
            """
        ).fetchall()
        latest_activity = conn.execute(
            """
            SELECT a.id, a.event_type, a.description, a.created_at, u.display_name, u.email
            FROM activity_log a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY datetime(a.created_at) DESC, a.id DESC
            LIMIT 12
            """
        ).fetchall()
        analytics = admin_analytics_summary(conn)
    return render_template(
        "admin.html",
        stats=stats,
        latest_users=latest_users,
        directory_users=directory_users,
        filters=filters,
        filter_options=filter_options,
        latest_messages=latest_messages,
        latest_uploads=latest_uploads,
        latest_activity=latest_activity,
        users_per_app=users_per_app,
        analytics=analytics,
    )


@app.route("/admin/users")
@admin_required
def admin_users():
    return admin_dashboard()


@app.route("/admin/users/<int:user_id>")
@admin_required
def admin_user_detail(user_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            flash("User not found.")
            return redirect(url_for("admin_dashboard"))
        user_record = admin_user_card(conn, row)
        app_profiles = admin_app_profile_context(conn, user_id)
        activity = conn.execute(
            """
            SELECT *
            FROM activity_log
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 40
            """,
            (user_id,),
        ).fetchall()
        uploads = conn.execute(
            """
            SELECT *
            FROM performances
            WHERE profile_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 40
            """,
            (user_id,),
        ).fetchall()
        message_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE sender_id = ? OR recipient_id = ?",
            (user_id, user_id),
        ).fetchone()[0]
        showcase_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM performances
            WHERE profile_id = ? AND (is_featured = 1 OR COALESCE(media_type, '') != '')
            """,
            (user_id,),
        ).fetchone()[0]
        analytics = conn.execute(
            """
            SELECT path, feature, created_at
            FROM analytics_events
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
    return render_template(
        "admin_user_detail.html",
        record=user_record,
        app_profiles=app_profiles,
        activity=activity,
        uploads=uploads,
        message_count=message_count,
        showcase_count=showcase_count,
        analytics=analytics,
    )


@app.route("/search")
def search():
    return render_template(
        "search.html",
        categories=SEARCH_CATEGORIES,
    )


@app.route("/search/<slug>")
def search_directory(slug):
    if slug == "showcases":
        return redirect(url_for("showcase"))
    category = category_by_slug(slug)
    if not category:
        flash("Directory not found.")
        return redirect(url_for("search"))
    filters = {
        "q": request.args.get("q", "").strip(),
        "state": request.args.get("state", "").strip(),
        "city": request.args.get("city", "").strip(),
        "genre": request.args.get("genre", "").strip(),
        "instrument": request.args.get("instrument", "").strip(),
        "role": request.args.get("role", "").strip(),
        "services": request.args.get("services", "").strip(),
        "availability": request.args.get("availability", "").strip(),
        "country": request.args.get("country", "").strip(),
    }
    selected_instruments = [
        item.strip()
        for item in request.args.getlist("instruments")
        if item.strip()
    ]
    match_mode = request.args.get("match", "any")
    if slug == "musicians" and selected_instruments:
        filters["instrument"] = ""
    results = search_category_profiles(category, filters)
    if filters["availability"]:
        availability = filters["availability"].lower()
        results = [
            profile for profile in results
            if availability in f"{profile.availability} {profile.tags_csv} {profile.services_csv} {profile.bio}".lower()
        ]
    if slug == "musicians" and selected_instruments:
        needles = [item.lower() for item in selected_instruments]

        def instrument_match(profile):
            haystack = f"{profile.instrument} {profile.services_csv} {profile.tags_csv}".lower()
            hits = [needle in haystack for needle in needles]
            return all(hits) if match_mode == "all" else any(hits)

        results = [profile for profile in results if instrument_match(profile)]
    view_mode = request.args.get("view", "list")
    if view_mode not in {"list", "map"}:
        view_mode = "list"
    map_points = []
    location_counts = {}
    location_coords = {}
    for profile in results:
        location = ", ".join(part for part in [profile.city, profile.state] if part) or profile.country or "Location coming soon"
        location_counts[location] = location_counts.get(location, 0) + 1
        coords = profile_coordinates(profile)
        if coords:
            location_coords[location] = coords
    for location, count in location_counts.items():
        coords = location_coords.get(location)
        if coords:
            map_points.append({"location": location, "count": count, "lat": coords[0], "lng": coords[1]})
    return render_template(
        "directory_map.html" if view_mode == "map" else "directory.html",
        category=category,
        profiles=results,
        filters=filters,
        selected_instruments=selected_instruments,
        match_mode=match_mode,
        instrument_options=INSTRUMENT_OPTIONS,
        is_musicians=slug == "musicians",
        view_mode=view_mode,
        map_points=map_points,
    )


@app.route("/profiles")
def profiles():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    genre = request.args.get("genre", "").strip()
    city = request.args.get("city", "").strip()
    state = request.args.get("state", "").strip()
    instrument = request.args.get("instrument", "").strip()
    services = request.args.get("services", "").strip()
    tags = request.args.get("tags", "").strip()
    results = search_profiles(q=q, role=role, genre=genre, city=city, state=state, instrument=instrument, services=services, tags=tags)
    return render_template(
        "profiles.html",
        profiles=results,
        showcase_items=get_showcase_tiles(limit=8, role=role) if role else [],
        q=q,
        role=role,
        genre=genre,
        city=city,
        state=state,
        instrument=instrument,
        services=services,
        tags=tags,
    )


@app.route("/browse/<slug>")
def browse_category(slug):
    if slug in {"production", "producers"}:
        return redirect(url_for("search_directory", slug="production", **request.args))
    if slug in {"composers", "artists", "musicians"}:
        return redirect(url_for("search_directory", slug=slug, **request.args))
    if slug == "showcases":
        return redirect(url_for("showcase"))
    category = category_by_slug(slug)
    if not category:
        instrument = INSTRUMENT_CATEGORY_REDIRECTS.get(slug)
        if instrument:
            return redirect(url_for("instruments", instruments=instrument))
        flash("Category not found.")
        return redirect(url_for("profiles"))
    filters = {
        "q": request.args.get("q", "").strip(),
        "state": request.args.get("state", "").strip(),
        "city": request.args.get("city", "").strip(),
        "genre": request.args.get("genre", "").strip(),
        "instrument": request.args.get("instrument", "").strip(),
        "role": request.args.get("role", "").strip(),
        "services": request.args.get("services", "").strip(),
        "country": request.args.get("country", "").strip(),
    }
    results = search_category_profiles(category, filters)
    result_ids = {profile.id for profile in results}
    showcase_items = [
        perf
        for perf in get_performances()
        if perf.profile and perf.profile.id in result_ids and profile_matches_category(perf.profile, category)
    ][:6]
    location_label = filters["state"] or filters["city"] or filters["country"]
    return render_template(
        "browse_category.html",
        category=category,
        profiles=results,
        showcase_items=showcase_items,
        filters=filters,
        category_tiles=SEARCH_CATEGORIES,
        instrument_options=INSTRUMENT_OPTIONS,
        location_label=location_label,
    )


@app.route("/instruments")
def instruments():
    filters = {
        "q": request.args.get("q", "").strip(),
        "state": request.args.get("state", "").strip(),
        "city": request.args.get("city", "").strip(),
        "genre": request.args.get("genre", "").strip(),
        "instrument": request.args.get("instrument", "").strip(),
        "role": request.args.get("role", "").strip(),
        "services": request.args.get("services", "").strip(),
        "country": request.args.get("country", "").strip(),
    }
    selected = [
        item.strip()
        for item in request.args.getlist("instruments")
        if item.strip()
    ]
    match_mode = request.args.get("match", "any")
    profiles = search_profiles(
        q=filters["q"],
        role=filters["role"],
        genre=filters["genre"],
        city=filters["city"],
        state=filters["state"],
        country=filters["country"],
        instrument=filters["instrument"],
        services=filters["services"],
    )
    if selected:
        selected_lower = [item.lower() for item in selected]
        def instrument_hit(profile):
            haystack = f"{profile.instrument} {profile.services_csv} {profile.tags_csv} {profile.role}".lower()
            matches = [needle in haystack for needle in selected_lower]
            return all(matches) if match_mode == "all" else any(matches)
        profiles = [profile for profile in profiles if instrument_hit(profile)]
    return render_template(
        "instruments.html",
        profiles=profiles,
        filters=filters,
        selected_instruments=selected,
        match_mode=match_mode,
        instrument_options=INSTRUMENT_OPTIONS,
    )


@app.route("/profiles/new", methods=["GET", "POST"])
@app.route("/create-profile", methods=["GET", "POST"])
def create_profile():
    return signup()


@app.route("/profile/new")
def new_profile():
    return redirect(url_for("signup"))


@app.route("/profiles/<int:profile_id>")
def profile_detail(profile_id):
    profile = get_profile(profile_id)
    if not profile:
        flash("Profile not found.")
        return redirect(url_for("profiles"))
    return render_template(
        "profile_detail.html",
        profile=profile,
        perfs=get_performances(profile_id=profile.id),
        showcase_items=get_showcase_tiles(limit=12, profile_id=profile.id),
    )


@app.route("/users/<int:user_id>")
def user_detail(user_id):
    return profile_detail(user_id)


@app.route("/perfomances")
@app.route("/performance")
@app.route("/performances")
def performances():
    return render_template("perfomances.html", performances=get_performances())


@app.route("/performances/<int:perf_id>")
def performance_detail(perf_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE performances SET views = COALESCE(views, 0) + 1 WHERE id = ?",
            (perf_id,),
        )
        row = conn.execute("SELECT * FROM performances WHERE id = ?", (perf_id,)).fetchone()
    if not row:
        flash("Performance not found.")
        return redirect(url_for("performances"))
    perf = row_to_performance(row, get_profile(row["profile_id"]))
    return render_template("performance_detail.html", perf=perf)


@app.route("/showcase/<int:perf_id>")
def showcase_item(perf_id):
    return performance_detail(perf_id)


@app.route("/performances/<int:perf_id>/share", methods=["POST"])
def share_performance(perf_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM performances WHERE id = ?", (perf_id,)).fetchone()
    if not row:
        flash("Performance not found.")
        return redirect(url_for("showcase"))
    perf = row_to_performance(row, get_profile(row["profile_id"]))
    viewer = current_user()
    log_activity(
        viewer.id if viewer else None,
        "showcase_shared",
        f"Shared {perf.title}",
        {"performance_id": perf.id, "profile_id": perf.profile.id if perf.profile else row["profile_id"]},
    )
    return render_template("share_confirmation.html", perf=perf)


@app.route("/my-uploads")
@app.route("/uploads")
@login_required
def my_uploads():
    user = current_user()
    return render_template("my_uploads.html", user=user, perfs=get_performances(profile_id=user.id))


@app.route("/performances/<int:perf_id>/delete", methods=["POST"])
@login_required
def delete_performance(perf_id):
    user = current_user()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM performances WHERE id = ?", (perf_id,)).fetchone()
        if not row:
            flash("Performance not found.")
            return redirect(url_for("my_uploads"))
        if row["profile_id"] != user.id:
            flash("You can only delete your own uploads.")
            return redirect(url_for("my_uploads"))
        perf = row_to_performance(row, user)
        remove_upload(perf.video_filename)
        remove_upload(perf.audio_filename)
        remove_upload(perf.image_filename)
        remove_upload(perf.thumb_filename)
        conn.execute("DELETE FROM performances WHERE id = ?", (perf_id,))
    flash("Upload deleted.")
    return redirect(url_for("my_uploads"))


@app.route("/perfomances/upload", methods=["GET", "POST"])
@app.route("/upload", methods=["GET", "POST"])
@app.route("/upload-performance", methods=["GET", "POST"])
@app.route("/performances/upload", methods=["GET", "POST"])
@login_required
def upload_performance():
    user = current_user()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        external_url = request.form.get("external_url", "").strip()
        profile_id = request.form.get("profile_id", str(user.id)).strip()
        if not title or not profile_id:
            flash("Title and artist profile are required.")
            return redirect(url_for("upload_performance"))
        if not valid_media_url(external_url):
            flash("Use a full media link that starts with http:// or https://.")
            return redirect(url_for("upload_performance"))

        profile = get_profile(profile_id)
        if not profile:
            flash("Please choose a valid profile.")
            return redirect(url_for("upload_performance"))
        if profile.id != user.id:
            flash("You can only add performances to your own profile.")
            return redirect(url_for("upload_performance"))

        try:
            video_filename = save_upload(
                first_uploaded_file("video", "video_file"),
                ALLOWED_VIDEO_EXTENSIONS,
                VIDEO_DIR,
            )
            audio_filename = save_upload(
                first_uploaded_file("audio", "audio_file"),
                ALLOWED_AUDIO_EXTENSIONS,
                AUDIO_DIR,
            )
            image_filename = save_upload(
                first_uploaded_file("image", "image_file"),
                ALLOWED_IMAGE_EXTENSIONS,
                PHOTO_DIR,
            )
            thumb_filename = save_upload(
                first_uploaded_file("thumb", "photo"),
                ALLOWED_IMAGE_EXTENSIONS,
                PHOTO_DIR,
            )
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("upload_performance"))
        if not any([video_filename, audio_filename, image_filename, external_url]):
            flash("Add a video, audio demo, image, or media link.")
            return redirect(url_for("upload_performance"))

        perf_id = create_performance(
            profile.id,
            title,
            description,
            video_filename,
            audio_filename,
            image_filename,
            thumb_filename,
            external_url,
        )
        log_activity(
            user.id,
            "performance_uploaded",
            f"Uploaded {title}",
            {"performance_id": perf_id, "media_link": bool(external_url)},
        )
        flash("Performance uploaded.")
        return redirect(url_for("performance_detail", perf_id=perf_id))

    return render_template("upload_performance.html", profiles=[user])


@app.route("/performances/new")
def new_performance():
    return redirect(url_for("upload_performance"))


@app.route("/performance/new")
def performance_new():
    return redirect(url_for("upload_performance"))


@app.route("/upload-media", methods=["POST"])
@login_required
def upload_media():
    user = current_user()
    try:
        profile_pic, profile_video = uploaded_profile_media(
            user.profile_pic,
            user.profile_video,
        )
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("edit_profile"))

    with get_db() as conn:
        conn.execute(
            "UPDATE users SET avatar_url = ?, profile_pic = ?, profile_video = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (profile_pic, profile_pic, profile_video, user.id),
        )
    flash("Media uploaded.")
    return redirect(url_for("profile"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        try:
            fields = profile_form_fields()
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("signup"))
        if not email or not password or not fields["display_name"]:
            flash("Display name, email, and password are required.")
            return redirect(url_for("signup"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for("signup"))
        if confirm_password and password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("signup"))

        try:
            profile_pic, _ = uploaded_profile_media()
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("signup"))

        try:
            user_id = create_user(email, password, fields, profile_pic)
        except sqlite3.IntegrityError:
            remove_upload(profile_pic)
            flash("An account with that email already exists.")
            return redirect(url_for("signup"))

        session.clear()
        session["user_id"] = user_id
        flash("Welcome to Find the Beat. Complete your profile to help other creators find you.")
        return redirect(url_for("profile"))

    return render_template("signup.html", instrument_options=INSTRUMENT_OPTIONS)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not row or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        post_login_redirect = session.get("post_login_redirect")
        session.clear()
        session["user_id"] = row["id"]
        with get_db() as conn:
            conn.execute(
                """
                UPDATE users
                SET brent_account_id = COALESCE(NULLIF(brent_account_id, ''), ?),
                    provider = COALESCE(NULLIF(provider, ''), ?),
                    auth_provider = COALESCE(NULLIF(auth_provider, ''), ?),
                    authentication_provider = COALESCE(NULLIF(authentication_provider, ''), ?),
                    last_login_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (brent_account_id(row["email"]), AUTH_PROVIDER, AUTH_PROVIDER, AUTH_PROVIDER, row["id"]),
            )
            ensure_app_profile(conn, row["id"], "find-the-beat")
        log_activity(row["id"], "user_logged_in", "Email/password login")
        count = unread_message_count(row["id"])
        flash("You have new messages." if count else "You are logged in.")
        return redirect(post_login_redirect or url_for("profile"))

    return render_template(
        "login.html",
        google_ready=GOOGLE_OAUTH_READY,
        apple_ready=APPLE_OAUTH_READY,
    )


@app.route("/auth/google")
def auth_google():
    if not GOOGLE_OAUTH_READY:
        flash("Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in Render first.")
        return redirect(url_for("login"))
    return oauth.google.authorize_redirect(url_for("auth_google_callback", _external=True))


@app.route("/auth/google/callback")
def auth_google_callback():
    if not GOOGLE_OAUTH_READY:
        flash("Google sign-in is not configured yet.")
        return redirect(url_for("login"))
    try:
        token = oauth.google.authorize_access_token()
        info = token.get("userinfo") or oauth.google.userinfo()
        user_id = upsert_oauth_user(
            "google",
            info.get("email", ""),
            info.get("name") or info.get("given_name") or "",
            info.get("picture", ""),
            info.get("sub", ""),
        )
    except Exception as exc:
        app.logger.exception("Google OAuth failed")
        flash(f"Google sign-in failed: {exc}")
        return redirect(url_for("login"))
    post_login_redirect = session.get("post_login_redirect")
    session.clear()
    session["user_id"] = user_id
    flash("You are logged in with Google.")
    return redirect(post_login_redirect or url_for("profile"))


@app.route("/auth/apple")
def auth_apple():
    if not APPLE_OAUTH_READY:
        flash("Apple sign-in needs APPLE_CLIENT_ID, APPLE_TEAM_ID, APPLE_KEY_ID, and APPLE_PRIVATE_KEY in Render first.")
        return redirect(url_for("login"))
    return oauth.apple.authorize_redirect(
        url_for("auth_apple_callback", _external=True),
        response_mode="form_post",
    )


@app.route("/auth/apple/callback", methods=["GET", "POST"])
def auth_apple_callback():
    if not APPLE_OAUTH_READY:
        flash("Apple sign-in is not configured yet.")
        return redirect(url_for("login"))
    try:
        token = oauth.apple.authorize_access_token()
        info = {}
        try:
            info = oauth.apple.parse_id_token(token) or {}
        except Exception:
            info = token.get("userinfo") or {}
        apple_user = request.form.get("user", "")
        if apple_user:
            try:
                apple_payload = json.loads(apple_user)
                name = apple_payload.get("name") or {}
                full_name = " ".join(
                    part for part in [name.get("firstName", ""), name.get("lastName", "")] if part
                )
                if full_name:
                    info["name"] = full_name
            except json.JSONDecodeError:
                pass
        user_id = upsert_oauth_user(
            "apple",
            info.get("email", ""),
            info.get("name") or "",
            "",
            info.get("sub", ""),
        )
    except Exception as exc:
        app.logger.exception("Apple OAuth failed")
        flash(f"Apple sign-in failed: {exc}")
        return redirect(url_for("login"))
    post_login_redirect = session.get("post_login_redirect")
    session.clear()
    session["user_id"] = user_id
    flash("You are logged in with Apple.")
    return redirect(post_login_redirect or url_for("profile"))


@app.route("/sso/start")
def sso_start():
    target_app = request.args.get("app", "find-the-beat").strip().lower()
    next_path = request.args.get("next", "").strip()
    if target_app not in SSO_APP_TARGETS:
        flash("That Brent & Co app is not configured for SSO yet.")
        return redirect(url_for("profile" if current_user() else "login"))

    user_id = session.get("user_id")
    if not user_id:
        session["post_login_redirect"] = request.full_path
        flash("Sign in once with your Brent & Co account, then you can open the app.")
        return redirect(url_for("login"))

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            session.clear()
            return redirect(url_for("login"))
        ensure_app_profile(conn, user_id, "find-the-beat")
        if target_app in {"find-the-beat", "brent"}:
            ensure_app_profile(conn, user_id, target_app)

    if target_app == "find-the-beat":
        return redirect(next_path or url_for("profile"))
    if target_app == "brent":
        return redirect(SSO_APP_TARGETS[target_app])

    token = sign_sso_payload(sso_user_payload(user, target_app))
    callback = f"{SSO_APP_TARGETS[target_app]}/sso/consume"
    query = {"token": token}
    if next_path:
        query["next"] = next_path
    return redirect(f"{callback}?{urlencode(query)}")


@app.route("/sso/consume")
def sso_consume():
    token = request.args.get("token", "")
    payload = verify_sso_token(token)
    if not payload or payload.get("aud") != "find-the-beat":
        flash("That Brent & Co sign-in link expired. Please sign in again.")
        return redirect(url_for("login"))
    email = (payload.get("email") or "").strip().lower()
    if not email:
        flash("That Brent & Co sign-in link did not include an email.")
        return redirect(url_for("login"))
    user_id = upsert_oauth_user(
        payload.get("authentication_provider") or "brent-sso",
        email,
        payload.get("display_name") or "",
        payload.get("profile_photo") or "",
        payload.get("sub") or "",
    )
    session.clear()
    session["user_id"] = user_id
    with get_db() as conn:
        ensure_app_profile(conn, user_id, "find-the-beat")
    return redirect(request.args.get("next") or url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You are logged out.")
    return redirect(url_for("home"))


@app.route("/profile")
@login_required
def profile():
    try:
        user = current_user()
        completion = profile_completion(user)
        unread = unread_message_count(user.id) if user else 0
    except sqlite3.OperationalError as exc:
        app.logger.exception("Profile load failed; retrying after schema init")
        init_db()
        user = current_user()
        completion = profile_completion(user)
        unread = unread_message_count(user.id) if user else 0
        flash("Profile data was refreshed.")
    except Exception as exc:
        app.logger.exception("Profile load failed")
        user = current_user()
        completion = {"percent": 0, "items": []}
        unread = 0
        flash("We had trouble loading part of your profile, but your account is safe.")
    return render_template(
        "profile.html",
        user=user,
        completion=completion,
        unread_count=unread,
    )


@app.route("/profile/edit", methods=["GET", "POST"])
@app.route("/profiles/<int:profile_id>/edit", methods=["GET", "POST"])
@login_required
def edit_profile(profile_id=None):
    user = current_user()
    if profile_id is not None and profile_id != user.id:
        flash("You can only edit your own profile.")
        return redirect(url_for("profile_detail", profile_id=profile_id))

    if request.method == "POST":
        try:
            fields = profile_form_fields()
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("edit_profile"))
        if not fields["display_name"]:
            flash("Display name is required.")
            return redirect(url_for("edit_profile"))

        try:
            profile_pic, profile_video = uploaded_profile_media(
                user.profile_pic,
                user.profile_video,
            )
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("edit_profile"))

        update_user_profile(user.id, fields, profile_pic, profile_video)
        flash("Profile updated.")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", user=user, instrument_options=INSTRUMENT_OPTIONS)


@app.route("/profile/delete", methods=["POST", "GET"])
@app.route("/profiles/<int:profile_id>/delete", methods=["POST", "GET"])
@login_required
def delete_profile(profile_id=None):
    user = current_user()
    if profile_id is not None and profile_id != user.id:
        flash("You can only delete your own profile.")
        return redirect(url_for("profile_detail", profile_id=profile_id))

    remove_upload(user.profile_pic)
    remove_upload(user.profile_video)
    with get_db() as conn:
        for perf in get_performances(profile_id=user.id):
            remove_upload(perf.video_filename)
            remove_upload(perf.audio_filename)
            remove_upload(perf.image_filename)
            remove_upload(perf.thumb_filename)
        conn.execute("DELETE FROM performances WHERE profile_id = ?", (user.id,))
        conn.execute(
            "DELETE FROM messages WHERE sender_id = ? OR recipient_id = ?",
            (user.id, user.id),
        )
        conn.execute("DELETE FROM users WHERE id = ?", (user.id,))
    session.clear()
    flash("Your profile has been deleted.")
    return redirect(url_for("home"))


@app.route("/profile/delete-photo", methods=["POST"])
@login_required
def delete_profile_photo():
    user = current_user()
    remove_upload(user.profile_pic)
    with get_db() as conn:
        conn.execute("UPDATE users SET profile_pic = '' WHERE id = ?", (user.id,))
    flash("Profile picture removed.")
    return redirect(url_for("profile"))


@app.route("/profile/delete-video", methods=["POST"])
@login_required
def delete_profile_video():
    user = current_user()
    remove_upload(user.profile_video)
    with get_db() as conn:
        conn.execute("UPDATE users SET profile_video = '' WHERE id = ?", (user.id,))
    flash("Profile video removed.")
    return redirect(url_for("profile"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    for folder in (UPLOAD_DIR, PHOTO_DIR, VIDEO_DIR, AUDIO_DIR):
        if (folder / filename).exists():
            return send_from_directory(folder, filename)
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/uploads/photos/<path:filename>")
def uploaded_photo(filename):
    return send_from_directory(PHOTO_DIR, filename)


@app.route("/uploads/videos/<path:filename>")
def uploaded_video(filename):
    return send_from_directory(VIDEO_DIR, filename)


@app.route("/uploads/audio/<path:filename>")
def uploaded_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


@app.route("/dashboard")
def dashboard():
    return redirect(url_for("profile" if current_user() else "login"))


@app.route("/me")
def my_profile():
    return redirect(url_for("profile" if current_user() else "login"))


@app.route("/messages/new", methods=["GET", "POST"])
@app.route("/profiles/<int:recipient_id>/message", methods=["GET", "POST"])
@login_required
def new_message(recipient_id=None):
    user = current_user()
    profiles = [profile for profile in search_profiles() if profile.id != user.id]
    selected_recipient = get_profile(recipient_id) if recipient_id else None

    if recipient_id and (not selected_recipient or selected_recipient.id == user.id):
        flash("Choose another profile to message.")
        return redirect(url_for("profiles"))

    if request.method == "POST":
        recipient_id = request.form.get("recipient_id") or recipient_id
        body = request.form.get("body", "").strip()
        recipient = get_profile(recipient_id) if recipient_id else None
        if not recipient or recipient.id == user.id:
            flash("Choose a valid recipient.")
            return redirect(url_for("new_message"))
        if not body:
            flash("Write a message before sending.")
            return redirect(url_for("new_message", recipient_id=recipient.id))

        create_message(user.id, recipient.id, body)
        flash("Message sent.")
        return redirect(url_for("thread", other=recipient.id))

    return render_template(
        "new_message.html",
        profiles=profiles,
        selected_recipient=selected_recipient,
    )


@app.route("/inbox")
@login_required
def inbox():
    user = current_user()
    return render_template("inbox.html", msgs=get_inbox_messages(user.id))


@app.route("/api/messages/unread-count")
@login_required
def api_unread_count():
    user = current_user()
    return jsonify({
        "unreadCount": unread_message_count(user.id),
        "futureNotifications": {
            "email": False,
            "push": False,
            "note": "This endpoint supports future live badge refresh, push, and email notifications.",
        },
    })


@app.route("/showcase")
@app.route("/showcases")
def showcase():
    return render_template("showcase.html", **showcase_context())


@app.route("/production")
def production():
    return redirect(url_for("search_directory", slug="production"))


@app.route("/producers")
def producers():
    return redirect(url_for("search_directory", slug="production"))


@app.route("/artists")
def artists():
    return redirect(url_for("search_directory", slug="artists"))


@app.route("/musicians")
def musicians():
    return redirect(url_for("search_directory", slug="musicians"))


@app.route("/singers")
@app.route("/vocalists")
def singers():
    return redirect(url_for("search_directory", slug="singers"))


@app.route("/composers")
def composers():
    return redirect(url_for("search_directory", slug="composers"))


@app.route("/thread")
@login_required
def thread():
    user = current_user()
    other_id = request.args.get("other") or request.args.get("me")
    other = get_profile(other_id) if other_id else None
    if not other or other.id == user.id:
        flash("Conversation not found.")
        return redirect(url_for("inbox"))
    return render_template(
        "thread.html",
        me=user,
        other=other,
        msgs=get_thread_messages(user.id, other.id),
    )


@app.route("/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_message(message_id):
    user = current_user()
    with get_db() as conn:
        msg = conn.execute(
            "SELECT * FROM messages WHERE id = ? AND (sender_id = ? OR recipient_id = ?)",
            (message_id, user.id, user.id),
        ).fetchone()
        if msg:
            conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            flash("Message deleted.")
        else:
            flash("Message not found.")
    return redirect(url_for("inbox"))


@app.route("/performances/<int:perf_id>/like", methods=["POST"])
def like_performance(perf_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE performances SET likes = COALESCE(likes, 0) + 1 WHERE id = ?",
            (perf_id,),
        )
    flash("Performance liked.")
    return redirect(url_for("performance_detail", perf_id=perf_id))


@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(error):
    flash("That upload is too large. Please choose a smaller file.")
    return redirect(request.referrer or url_for("profile"))


@app.errorhandler(sqlite3.Error)
def handle_database_error(error):
    app.logger.exception("SQLite error: %s", error)
    return (
        "The app hit a database problem while handling that request. "
        "Please go back and try again.",
        500,
    )


@app.errorhandler(404)
def handle_not_found(error):
    flash("That page was not found.")
    return redirect(url_for("home"))


init_db()
seed_demo_profiles_if_empty()
seed_founder_profile()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5001")))
