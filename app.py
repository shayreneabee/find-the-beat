import hashlib
import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

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

        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        for column, definition in {
            "full_name": "TEXT DEFAULT ''",
            "username": "TEXT DEFAULT ''",
            "state": "TEXT DEFAULT ''",
            "country": "TEXT DEFAULT ''",
            "avatar_url": "TEXT DEFAULT ''",
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
            "is_admin": "INTEGER DEFAULT 0",
            "is_founder": "INTEGER DEFAULT 0",
            "is_verified": "INTEGER DEFAULT 0",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
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


def profile_form_fields():
    social_fields = {
        key: normalize_social_url(request.form.get(key, "").strip())
        for key in SOCIAL_FIELDS
    }
    return {
        "display_name": request.form.get("display_name", "").strip(),
        "role": request.form.get("role", "").strip(),
        "genre": request.form.get("genre", "").strip(),
        "city": request.form.get("city", "").strip(),
        "bio": request.form.get("bio", "").strip(),
        "tags_csv": request.form.get("tags_csv", "").strip(),
        "instrument": request.form.get("instrument", "").strip(),
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
                email, password_hash, full_name, display_name, role, genre, city, bio,
                tags_csv, instrument, services_csv, profile_pic,
                instagram_url, tiktok_url, youtube_url, spotify_url, linkedin_url,
                brent_account_id, provider, auth_provider, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                email,
                generate_password_hash(password),
                fields["display_name"],
                fields["display_name"],
                fields["role"],
                fields["genre"],
                fields["city"],
                fields["bio"],
                fields["tags_csv"],
                fields["instrument"],
                fields["services_csv"],
                profile_pic,
                fields.get("instagram_url", ""),
                fields.get("tiktok_url", ""),
                fields.get("youtube_url", ""),
                fields.get("spotify_url", ""),
                fields.get("linkedin_url", ""),
                brent_account_id(email),
                AUTH_PROVIDER,
                AUTH_PROVIDER,
            ),
        )
        return cursor.lastrowid


def update_user_profile(user_id, fields, profile_pic, profile_video):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE users
            SET full_name = COALESCE(NULLIF(full_name, ''), ?),
                display_name = ?, role = ?, genre = ?, city = ?, bio = ?,
                tags_csv = ?, instrument = ?, services_csv = ?,
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
                fields["bio"],
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
        return cursor.lastrowid


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
    checks = [
        ("Add profile photo", bool(user.profile_pic)),
        ("Add talent", bool(user.role or user.instrument or user.services_csv)),
        ("Add genre", bool(user.genre)),
        ("Add city", bool(user.city)),
        ("Add bio", bool(user.bio)),
        ("Add social links", bool(user.social_links)),
        ("Add first performance", bool(get_performances(profile_id=user.id))),
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
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_profile(row)


@app.context_processor
def inject_user_context():
    user = current_user()
    return {
        "user": user,
        "unread_count": unread_message_count(user.id) if user else 0,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    return {
        "user": current_user(),
        "brent_co_url": BRENT_CO_URL,
        "find_the_beat_url": FIND_THE_BEAT_URL,
        "second_chance_url": SECOND_CHANCE_URL,
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


def search_profiles(q="", role="", genre="", city="", instrument="", tags=""):
    clauses = []
    params = []
    if q:
        needle = f"%{q}%"
        clauses.append(
            """
            (display_name LIKE ? OR role LIKE ? OR genre LIKE ? OR city LIKE ?
             OR bio LIKE ? OR tags_csv LIKE ? OR instrument LIKE ? OR services_csv LIKE ?)
            """
        )
        params.extend([needle] * 8)
    if role:
        clauses.append("role LIKE ?")
        params.append(f"%{role}%")
    if genre:
        clauses.append("genre LIKE ?")
        params.append(f"%{genre}%")
    if city:
        clauses.append("city LIKE ?")
        params.append(f"%{city}%")
    if instrument:
        clauses.append("(instrument LIKE ? OR services_csv LIKE ?)")
        params.extend([f"%{instrument}%", f"%{instrument}%"])
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
                conn.execute(
                    """
                    UPDATE users
                    SET full_name = ?, display_name = ?, role = ?, genre = ?, city = ?, bio = ?,
                        tags_csv = ?, instrument = ?, services_csv = ?,
                        brent_account_id = ?, provider = ?, auth_provider = ?,
                        is_admin = 1, is_founder = 1, is_verified = 1,
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
                        existing["id"],
                    ),
                )
                continue
            conn.execute(
                """
                INSERT INTO users (
                    email, password_hash, full_name, display_name, role, genre, city, bio,
                    tags_csv, instrument, services_csv, brent_account_id,
                    provider, auth_provider, is_admin, is_founder, is_verified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1)
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
                ),
            )


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
    trending_profiles = sorted(
        profiles,
        key=lambda profile: (
            bool(profile.is_founder),
            bool(profile.is_verified),
            len(profile.badges or []),
            profile.id,
        ),
        reverse=True,
    )[:8]

    def role_profiles(role):
        return search_profiles(role=role)[:6]

    def wants_collab(profile):
        text = " ".join(
            [
                profile.tags_csv or "",
                profile.services_csv or "",
                profile.bio or "",
                profile.genre or "",
            ]
        ).lower()
        return any(
            phrase in text
            for phrase in ("collab", "collaboration", "available", "feature", "session")
        )

    open_collaborations = [profile for profile in profiles if wants_collab(profile)][:8]
    featured_artists = role_profiles("artist")
    featured_producers = role_profiles("producer")
    featured_musicians = role_profiles("musician")
    featured_composers = role_profiles("composer")

    return {
        "featured_performances": featured_performances,
        "trending_performances": trending_performances,
        "trending_profiles": trending_profiles,
        "featured_artists": featured_artists,
        "featured_producers": featured_producers,
        "featured_musicians": featured_musicians,
        "featured_composers": featured_composers,
        "role_sections": [
            {"title": "Featured Artists", "profiles": featured_artists, "endpoint": "artists"},
            {"title": "Featured Producers", "profiles": featured_producers, "endpoint": "producers"},
            {"title": "Featured Musicians", "profiles": featured_musicians, "endpoint": "musicians"},
            {"title": "Featured Composers", "profiles": featured_composers, "endpoint": "composers"},
        ],
        "open_collaborations": open_collaborations,
        "new_this_week": performances[:8],
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
        q=q,
        role_filter=role,
        genre_filter=genre,
        city_filter=city,
    )


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    genre = request.args.get("genre", "").strip()
    city = request.args.get("city", "").strip()
    instrument = request.args.get("instrument", "").strip()
    tags = request.args.get("tags", "").strip()
    results = search_profiles(q=q, role=role, genre=genre, city=city, instrument=instrument, tags=tags)
    return render_template(
        "search.html",
        results=results,
        q=q,
        role=role,
        genre=genre,
        city=city,
        instrument=instrument,
        tags=tags,
    )


@app.route("/profiles")
def profiles():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    genre = request.args.get("genre", "").strip()
    city = request.args.get("city", "").strip()
    instrument = request.args.get("instrument", "").strip()
    tags = request.args.get("tags", "").strip()
    results = search_profiles(q=q, role=role, genre=genre, city=city, instrument=instrument, tags=tags)
    return render_template(
        "profiles.html",
        profiles=results,
        showcase_items=get_showcase_tiles(limit=8, role=role) if role else [],
        q=q,
        role=role,
        genre=genre,
        city=city,
        instrument=instrument,
        tags=tags,
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

    return render_template("signup.html")


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

        session.clear()
        session["user_id"] = row["id"]
        with get_db() as conn:
            conn.execute(
                """
                UPDATE users
                SET brent_account_id = COALESCE(NULLIF(brent_account_id, ''), ?),
                    provider = COALESCE(NULLIF(provider, ''), ?),
                    auth_provider = COALESCE(NULLIF(auth_provider, ''), ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (brent_account_id(row["email"]), AUTH_PROVIDER, AUTH_PROVIDER, row["id"]),
            )
        count = unread_message_count(row["id"])
        flash("You have new messages." if count else "You are logged in.")
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You are logged out.")
    return redirect(url_for("home"))


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    return render_template("profile.html", user=user, completion=profile_completion(user))


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

    return render_template("edit_profile.html", user=user)


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
    return redirect(url_for("profiles", role="producer"))


@app.route("/producers")
def producers():
    return redirect(url_for("profiles", role="producer"))


@app.route("/artists")
def artists():
    return redirect(url_for("profiles", role="artist"))


@app.route("/musicians")
def musicians():
    return redirect(url_for("profiles", role="musician"))


@app.route("/composers")
def composers():
    return redirect(url_for("profiles", role="composer"))


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
