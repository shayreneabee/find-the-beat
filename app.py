import hashlib
import base64
import binascii
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import smtplib
import time
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

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
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "").strip()
TICKETMASTER_IMPORT_KEYWORDS = [
    item.strip()
    for item in os.getenv("TICKETMASTER_IMPORT_KEYWORDS", "music,open mic,concert,audition").split(",")
    if item.strip()
]
TICKETMASTER_IMPORT_CITY = os.getenv("TICKETMASTER_IMPORT_CITY", "").strip()
TICKETMASTER_IMPORT_STATE = os.getenv("TICKETMASTER_IMPORT_STATE", "").strip()
TICKETMASTER_IMPORT_COUNTRY = os.getenv("TICKETMASTER_IMPORT_COUNTRY", "US").strip() or "US"
EVENTBRITE_OAUTH_TOKEN = os.getenv("EVENTBRITE_OAUTH_TOKEN", "").strip()
EVENTBRITE_IMPORT_QUERY = os.getenv("EVENTBRITE_IMPORT_QUERY", "music audition gig open mic").strip()
EVENTBRITE_IMPORT_LOCATION = os.getenv("EVENTBRITE_IMPORT_LOCATION", "Mississippi").strip()
BANDSINTOWN_APP_ID = os.getenv("BANDSINTOWN_APP_ID", "").strip()
BANDSINTOWN_IMPORT_ARTISTS = [
    item.strip()
    for item in os.getenv("BANDSINTOWN_IMPORT_ARTISTS", "").split(",")
    if item.strip()
]
FTB_AUTO_IMPORT_GIGS = os.getenv("FTB_AUTO_IMPORT_GIGS", "").strip().lower() in {"1", "true", "yes", "on"}
FTB_SEED_DEMO_CONTENT = os.getenv("FTB_SEED_DEMO_CONTENT", "").strip().lower() in {"1", "true", "yes", "on"}

MUSIC_OPPORTUNITY_TERMS = [
    "audition", "band", "bass", "beat", "booking", "church", "choir", "collab",
    "composer", "concert", "creative", "dj", "drum", "festival", "gig", "gospel",
    "guitar", "instrument", "keyboard", "live", "music", "musician", "open mic",
    "opening act", "orchestra", "performance", "producer", "recording", "singer",
    "songwriter", "sound", "stage", "studio", "showcase", "venue", "vocal",
    "wedding", "worship",
]

US_GEO_POINTS = {
    "atlanta ga": (33.7490, -84.3880),
    "baton rouge la": (30.4515, -91.1871),
    "dallas tx": (32.7767, -96.7970),
    "gulfport ms": (30.3674, -89.0928),
    "hattiesburg ms": (31.3271, -89.2903),
    "houston tx": (29.7604, -95.3698),
    "jackson ms": (32.2988, -90.1848),
    "meridian ms": (32.3643, -88.7037),
    "memphis tn": (35.1495, -90.0490),
    "new orleans la": (29.9511, -90.0715),
}

ZIP_GEO_POINTS = {
    "303": (33.7490, -84.3880),
    "392": (32.2988, -90.1848),
    "394": (31.3271, -89.2903),
    "395": (30.3674, -89.0928),
    "701": (29.9511, -90.0715),
    "708": (30.4515, -91.1871),
    "752": (32.7767, -96.7970),
    "770": (29.7604, -95.3698),
}

DISCOVERY_CATEGORY_LABELS = {
    "all": "All activity",
    "gigs": "Gigs and paid opportunities",
    "auditions": "Auditions",
    "musicians": "Musicians and vocalists",
    "producers": "Producers and songwriters",
    "venues": "Venues",
    "churches": "Churches seeking musicians",
    "showcases": "Showcases",
    "collaborations": "Collaborations",
    "events": "Upcoming live events",
    "remote": "Remote opportunities",
}

FTB_GIG_BOARD_ENDPOINT = "opportunities_board"
BRENT_SSO_URL = os.getenv("BRENT_SSO_URL", "https://www.brentandco.org/sso/start").strip()
SSO_SHARED_SECRET = os.getenv("SSO_SHARED_SECRET", "dev-sso-change-me").strip()
SSO_TOKEN_TTL_SECONDS = int(os.getenv("SSO_TOKEN_TTL_SECONDS", "900") or "900")
SSO_CLOCK_SKEW_SECONDS = int(os.getenv("SSO_CLOCK_SKEW_SECONDS", "120") or "120")
SSO_ACCEPTED_ISSUERS = {
    value.strip()
    for value in os.getenv("SSO_ACCEPTED_ISSUERS", "brent-co-identity,brent-co-sso").split(",")
    if value.strip()
}
DEBUG_SSO = os.getenv("DEBUG_SSO", "").strip().lower() in {"1", "true", "yes", "on"}
AUTH_PROVIDER = os.getenv("BRENT_AUTH_PROVIDER", "local")
OWNER_AUTH_PROVIDER = os.getenv("BRENT_OWNER_AUTH_PROVIDER", "brent-core")
OWNER_INITIAL_PASSWORD = os.getenv("BRENT_OWNER_INITIAL_PASSWORD", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "").strip()
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "").strip()
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "").strip()
APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY", "").strip()
FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID", "").strip()
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET", "").strip()
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
    "Founder of Brent & Co and builder of Find The Beat, a creative network for "
    "musicians, producers, composers, artists, and collaborators."
)
FOUNDER_AVATAR_URL = os.getenv(
    "BRENT_OWNER_AVATAR_URL",
    "/static/images/find-the-beat/founder-shalanda-brent.png",
).strip()
FOUNDER_LINK_URL = os.getenv(
    "BRENT_OWNER_LINK_URL",
    "https://www.brentandco.org/founder",
).strip()

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


def log_sso_debug(event, app_name="find-the-beat", callback_url=""):
    if not DEBUG_SSO:
        return
    app.logger.info(
        "SSO %s app=%s BRENT_SSO_URL=%s SSO_SHARED_SECRET_PRESENT=%s callback=%s",
        event,
        app_name,
        BRENT_SSO_URL,
        bool(SSO_SHARED_SECRET),
        callback_url,
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
                stage_name TEXT DEFAULT '',
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
            CREATE TABLE IF NOT EXISTS profile_follows (
                follower_id INTEGER NOT NULL,
                followed_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(follower_id, followed_id),
                FOREIGN KEY(follower_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(followed_id) REFERENCES users(id) ON DELETE CASCADE
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                opportunity_type TEXT DEFAULT '',
                role_needed TEXT DEFAULT '',
                instrument_needed TEXT DEFAULT '',
                genre TEXT DEFAULT '',
                city TEXT DEFAULT '',
                state TEXT DEFAULT '',
                location_name TEXT DEFAULT '',
                latitude REAL,
                longitude REAL,
                paid_status TEXT DEFAULT '',
                compensation TEXT DEFAULT '',
                event_date TEXT DEFAULT '',
                application_deadline TEXT DEFAULT '',
                contact_method TEXT DEFAULT '',
                application_url TEXT DEFAULT '',
                created_by INTEGER,
                source_type TEXT DEFAULT 'user',
                source_name TEXT DEFAULT '',
                external_id TEXT DEFAULT '',
                is_featured INTEGER DEFAULT 0,
                is_seeded_demo INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                event_type TEXT DEFAULT '',
                performer TEXT DEFAULT '',
                venue TEXT DEFAULT '',
                address TEXT DEFAULT '',
                city TEXT DEFAULT '',
                state TEXT DEFAULT '',
                postal_code TEXT DEFAULT '',
                latitude REAL,
                longitude REAL,
                start_datetime TEXT DEFAULT '',
                end_datetime TEXT DEFAULT '',
                price_min REAL,
                price_max REAL,
                ticket_url TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                source_name TEXT DEFAULT '',
                external_id TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                genre TEXT DEFAULT '',
                is_featured INTEGER DEFAULT 0,
                is_seeded_demo INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                verification_status TEXT DEFAULT 'pending'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                actor_user_id INTEGER,
                related_profile_id INTEGER,
                related_event_id INTEGER,
                related_opportunity_id INTEGER,
                related_performance_id INTEGER,
                image_url TEXT DEFAULT '',
                city TEXT DEFAULT '',
                state TEXT DEFAULT '',
                occurred_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source_type TEXT DEFAULT 'platform',
                source_name TEXT DEFAULT '',
                external_url TEXT DEFAULT '',
                visibility TEXT DEFAULT 'public',
                is_seeded_demo INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(related_profile_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(related_event_id) REFERENCES events(id) ON DELETE SET NULL,
                FOREIGN KEY(related_opportunity_id) REFERENCES opportunities(id) ON DELETE SET NULL,
                FOREIGN KEY(related_performance_id) REFERENCES performances(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_import_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                source_type TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                imported_count INTEGER DEFAULT 0,
                duplicate_count INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                profile_completion_percentage INTEGER DEFAULT 0,
                profile_visibility TEXT DEFAULT 'public',
                social_links TEXT DEFAULT '{}',
                interests TEXT DEFAULT '',
                settings_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_memberships (
                user_id INTEGER NOT NULL,
                app_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, app_name),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        for table, columns in {
            "music_profiles": {
                "source_app": "TEXT DEFAULT 'find-the-beat'",
                "profile_completion_status": "TEXT DEFAULT 'incomplete'",
                "instruments": "TEXT DEFAULT ''",
                "genres": "TEXT DEFAULT ''",
                "city": "TEXT DEFAULT ''",
                "state": "TEXT DEFAULT ''",
                "bio": "TEXT DEFAULT ''",
                "services": "TEXT DEFAULT ''",
                "availability": "TEXT DEFAULT ''",
            },
            "cook_profiles": {
                "source_app": "TEXT DEFAULT 'lets-cook'",
                "profile_completion_status": "TEXT DEFAULT 'incomplete'",
                "favorite_cuisines": "TEXT DEFAULT ''",
                "saved_recipes": "TEXT DEFAULT ''",
                "hosting_interests": "TEXT DEFAULT ''",
                "meal_plans": "TEXT DEFAULT ''",
            },
            "career_profiles": {
                "source_app": "TEXT DEFAULT 'second-chance'",
                "profile_completion_status": "TEXT DEFAULT 'incomplete'",
                "career_goal": "TEXT DEFAULT ''",
                "certifications": "TEXT DEFAULT ''",
                "resume_status": "TEXT DEFAULT ''",
                "applications": "TEXT DEFAULT ''",
                "checklist_progress": "TEXT DEFAULT ''",
            },
            "travel_profiles": {
                "source_app": "TEXT DEFAULT 'beu'",
                "profile_completion_status": "TEXT DEFAULT 'incomplete'",
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
            "stage_name": "TEXT DEFAULT ''",
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
            "latitude": "REAL",
            "longitude": "REAL",
            "location_source": "TEXT DEFAULT ''",
            "is_admin": "INTEGER DEFAULT 0",
            "is_founder": "INTEGER DEFAULT 0",
            "is_verified": "INTEGER DEFAULT 0",
            "is_seeded_demo": "INTEGER DEFAULT 0",
            "demo_label": "TEXT DEFAULT ''",
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

        for table, columns in {
            "opportunities": {
                "source_url": "TEXT DEFAULT ''",
                "imported_at": "TEXT DEFAULT ''",
                "location_source": "TEXT DEFAULT ''",
                "is_featured": "INTEGER DEFAULT 0",
                "is_seeded_demo": "INTEGER DEFAULT 0",
                "status": "TEXT DEFAULT 'active'",
                "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            },
            "events": {
                "location_source": "TEXT DEFAULT ''",
                "is_featured": "INTEGER DEFAULT 0",
                "is_seeded_demo": "INTEGER DEFAULT 0",
                "verification_status": "TEXT DEFAULT 'pending'",
                "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            },
            "feed_items": {
                "is_seeded_demo": "INTEGER DEFAULT 0",
                "visibility": "TEXT DEFAULT 'public'",
            },
            "performances": {
                "latitude": "REAL",
                "longitude": "REAL",
                "location_source": "TEXT DEFAULT ''",
            },
        }.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_opportunity_external_source
            ON opportunities(source_name, external_id)
            WHERE COALESCE(source_name, '') != '' AND COALESCE(external_id, '') != ''
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_event_external_source
            ON events(source_name, external_id)
            WHERE COALESCE(source_name, '') != '' AND COALESCE(external_id, '') != ''
            """
        )


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


def username_slug(value, fallback="creator"):
    base = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return base or fallback


def unique_username(conn, preferred, email="", user_id=None):
    base = username_slug(preferred or (email or "").split("@")[0], "creator")
    candidate = base
    suffix = 2
    while True:
        if user_id is None:
            row = conn.execute("SELECT id FROM users WHERE lower(username) = lower(?)", (candidate,)).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM users WHERE lower(username) = lower(?) AND id != ?",
                (candidate, user_id),
            ).fetchone()
        if not row:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def sso_b64encode(data):
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def sso_b64decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def sso_secret_fingerprint():
    return hashlib.sha256(SSO_SHARED_SECRET.encode("utf-8")).hexdigest()[:12]


def unverified_sso_payload(token):
    try:
        body, _signature = token.split(".", 1)
        return json.loads(sso_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, TypeError, binascii.Error, UnicodeDecodeError):
        return {}


def sso_failure_details(error, token):
    payload = unverified_sso_payload(token) if token else {}
    now = int(time.time())
    exp = int(payload.get("exp") or 0)
    iat = int(payload.get("iat") or 0)
    return {
        "error": error,
        "secret_present": bool(SSO_SHARED_SECRET),
        "secret_is_default": SSO_SHARED_SECRET == "dev-sso-change-me",
        "secret_fingerprint": sso_secret_fingerprint(),
        "brent_sso_url": BRENT_SSO_URL,
        "accepted_issuers": sorted(SSO_ACCEPTED_ISSUERS),
        "expected_audience": "find-the-beat",
        "token_has_separator": bool(token and "." in token),
        "token_issuer": payload.get("iss"),
        "token_audience": payload.get("aud"),
        "issued_at": iat,
        "expires_at": exp,
        "server_now": now,
        "token_age_seconds": now - iat if iat else None,
        "seconds_until_expiry": exp - now if exp else None,
        "clock_skew_seconds": SSO_CLOCK_SKEW_SECONDS,
    }


def sign_sso_payload(payload):
    body = sso_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        SSO_SHARED_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{sso_b64encode(signature)}"


def verify_sso_token(token):
    if not token:
        return None, "missing"
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(
            SSO_SHARED_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(sso_b64decode(signature), expected):
            return None, "bad_signature"
        payload = json.loads(sso_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, TypeError, binascii.Error, UnicodeDecodeError):
        return None, "malformed"
    issuer = payload.get("iss")
    if issuer and issuer not in SSO_ACCEPTED_ISSUERS:
        return None, "invalid_issuer"
    if int(payload.get("exp", 0)) + SSO_CLOCK_SKEW_SECONDS < int(time.time()):
        return None, "expired"
    return payload, ""


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
        f"""
        INSERT OR IGNORE INTO {table}
            (user_id, source_app, profile_completion_status, updated_at)
        VALUES (?, ?, 'incomplete', CURRENT_TIMESTAMP)
        """,
        (user_id, app_key),
    )
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return
    if not (user["username"] or "").strip():
        conn.execute(
            "UPDATE users SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (unique_username(conn, user["display_name"] or user["email"].split("@")[0], user["email"], user_id), user_id),
        )
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    profile = row_to_profile(user)
    completion = profile_completion(profile)["percent"]
    interests = ", ".join(
        item for item in [profile.role, profile.genre, profile.instrument, profile.services_csv, profile.city] if item
    )
    conn.execute(
        """
        INSERT INTO profiles (
            user_id, profile_completion_percentage, profile_visibility,
            social_links, interests, updated_at
        )
        VALUES (?, ?, 'public', '{}', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            profile_completion_percentage = excluded.profile_completion_percentage,
            interests = excluded.interests,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, completion, interests),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO app_memberships (user_id, app_name, role)
        VALUES (?, ?, 'user')
        """,
        (user_id, app_key),
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
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "").strip()
    latitude, longitude, location_source = geocode_location(city, state)
    return {
        "display_name": request.form.get("display_name", "").strip(),
        "stage_name": request.form.get("stage_name", "").strip(),
        "role": normalize_profile_role(request.form.get("role", "")),
        "genre": request.form.get("genre", "").strip(),
        "city": city,
        "state": state,
        "country": request.form.get("country", "").strip(),
        "latitude": latitude,
        "longitude": longitude,
        "location_source": location_source,
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
                email, password_hash, full_name, display_name, stage_name, role, genre, city, state, country, bio,
                previous_work, availability,
                tags_csv, instrument, services_csv, profile_pic,
                latitude, longitude, location_source,
                instagram_url, tiktok_url, youtube_url, spotify_url, linkedin_url,
                brent_account_id, provider, auth_provider, authentication_provider, profile_photo, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                email,
                generate_password_hash(password),
                fields["display_name"],
                fields["display_name"],
                fields.get("stage_name", ""),
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
                fields.get("latitude"),
                fields.get("longitude"),
                fields.get("location_source", ""),
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
        username = unique_username(conn, fields["display_name"], email, user_id)
        conn.execute(
            "UPDATE users SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (username, user_id),
        )
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
                display_name = ?, stage_name = ?, role = ?, genre = ?, city = ?, state = ?, country = ?, bio = ?,
                previous_work = ?, availability = ?, tags_csv = ?, instrument = ?, services_csv = ?,
                avatar_url = ?, profile_pic = ?, profile_video = ?,
                latitude = ?, longitude = ?, location_source = ?,
                instagram_url = ?, tiktok_url = ?, youtube_url = ?,
                spotify_url = ?, linkedin_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                fields["display_name"],
                fields["display_name"],
                fields.get("stage_name", ""),
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
                fields.get("latitude"),
                fields.get("longitude"),
                fields.get("location_source", ""),
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
                 thumb_filename, external_url, media_type, media_url, thumbnail_url, genre, city, state,
                 latitude, longitude, location_source, tags_csv, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                profile.state if profile else "",
                profile.latitude if profile else None,
                profile.longitude if profile else None,
                profile.location_source if profile else "",
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
    {
        "slug": "production",
        "title": "Production",
        "image": "images/find-the-beat/producer.jpg",
        "terms": ["producer", "production", "beats", "beat production", "engineer", "mixing", "mastering"],
    },
    {
        "slug": "composers",
        "title": "Composers",
        "image": "images/find-the-beat/composer.jpg",
        "terms": ["composer", "composition", "score", "arrangement"],
    },
    {
        "slug": "artists",
        "title": "Artists",
        "image": "images/find-the-beat/artist.jpg",
        "terms": ["artist", "rapper", "performer"],
    },
    {
        "slug": "singers",
        "title": "Singers",
        "image": "images/find-the-beat/singer.jpg",
        "terms": ["singer", "vocalist", "vocals", "voice", "hooks", "background vocals"],
    },
    {
        "slug": "musicians",
        "title": "Musicians",
        "image": "images/find-the-beat/musician.jpg",
        "terms": ["musician", "instrumentalist", "band", "live", "guitar", "bass", "drums", "piano", "keyboard", "violin", "tambourine"],
    },
    {
        "slug": "showcases",
        "title": "Showcases",
        "image": "images/find-the-beat/showcase.jpg",
        "terms": [],
    },
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


def normalize_geo_key(*parts):
    return re.sub(r"[^a-z0-9]+", " ", " ".join(str(part or "") for part in parts).lower()).strip()


def geocode_location(city="", state="", zip_code="", location_text=""):
    zip_digits = re.sub(r"\D", "", zip_code or location_text or "")
    if zip_digits:
        point = ZIP_GEO_POINTS.get(zip_digits[:3])
        if point:
            return (*point, "zip")

    candidates = []
    if city and state:
        candidates.append(normalize_geo_key(city, state))
    if location_text:
        candidates.append(normalize_geo_key(location_text))
    if city:
        city_key = normalize_geo_key(city)
        candidates.append(city_key)
        candidates.extend(key for key in US_GEO_POINTS if key.startswith(f"{city_key} "))
    for key in candidates:
        point = US_GEO_POINTS.get(key)
        if point:
            return (*point, "city_state")
    return (None, None, "")


def miles_between(lat1, lng1, lat2, lng2):
    radius = 3958.8
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lam = math.radians(float(lng2) - float(lng1))
    hav = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lam / 2) ** 2
    )
    return radius * (2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav)))


def us_marker_position(latitude, longitude):
    if latitude is None or longitude is None:
        return None
    x = (float(longitude) + 125.0) / 58.0 * 100
    y = (50.0 - float(latitude)) / 26.0 * 100
    return {
        "x": max(2, min(98, round(x, 2))),
        "y": max(2, min(98, round(y, 2))),
    }


def is_remote_record(*values):
    haystack = " ".join(str(value or "").lower() for value in values)
    return "remote" in haystack or "virtual" in haystack or "online" in haystack


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
    data.setdefault("stage_name", "")
    data.setdefault("username", "")
    data.setdefault("state", "")
    data.setdefault("country", "")
    data.setdefault("avatar_url", "")
    data.setdefault("profile_pic", "")
    data.setdefault("profile_video", "")
    data.setdefault("latitude", None)
    data.setdefault("longitude", None)
    data.setdefault("location_source", "")
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
    data["is_seeded_demo"] = bool(data.get("is_seeded_demo"))
    data["demo_label"] = data.get("demo_label") or ""
    data["photo_filename"] = data.get("profile_pic") or ""
    data["avatar_url"] = data.get("avatar_url") or data["photo_filename"] or ""
    data["video_filename"] = data.get("profile_video") or ""
    data["name"] = data.get("display_name") or ""
    data["stage_name"] = data.get("stage_name") or ""
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
    data.setdefault("state", "")
    data.setdefault("latitude", None)
    data.setdefault("longitude", None)
    data.setdefault("location_source", "")
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
        data["state"] = data.get("state") or profile.state
        data["latitude"] = data.get("latitude") or profile.latitude
        data["longitude"] = data.get("longitude") or profile.longitude
        data["location_source"] = data.get("location_source") or profile.location_source
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
        ("Add profile photo", bool(getattr(user, "profile_pic", "") or getattr(user, "avatar_url", "") or getattr(user, "profile_photo", ""))),
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
        unread = unread_message_count(user.get("id") if isinstance(user, dict) else user.id) if user else 0
    except Exception:
        app.logger.exception("Template user context failed")
        user = None
        unread = 0
    return {
        "user": user,
        "unread_count": unread,
        "ftb_gig_board_url": ftb_gig_board_url,
        "ftb_opportunity_url": ftb_opportunity_url,
        "ftb_apply_url": ftb_apply_url,
        "current_endpoint": request.endpoint,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            destination = request_destination()
            session["post_login_redirect"] = destination
            flash("Please log in first.")
            return redirect(url_for("login", next=destination))
        return view(*args, **kwargs)

    return wrapped


def request_destination():
    destination = request.full_path.rstrip("?")
    return destination or request.path


def safe_redirect_target(value):
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.netloc or parsed.scheme:
        return ""
    return value if value.startswith("/") else ""


def profile_action_ready(user):
    return bool(
        user
        and (user.display_name or user.full_name)
        and (user.role or user.instrument or user.services_csv)
        and (user.city or user.state)
    )


def require_profile_action(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            destination = request_destination()
            session["post_login_redirect"] = destination
            flash("Please log in first.")
            return redirect(url_for("login", next=destination))
        if not profile_action_ready(user):
            destination = request_destination()
            session["post_profile_redirect"] = destination
            flash("Complete the required parts of your profile to continue.")
            return redirect(url_for("edit_profile", next=destination))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please log in first.")
            return redirect(url_for("login"))
        email = user.get("email", "") if isinstance(user, dict) else user.email
        if (email or "").strip().lower() != ADMIN_EMAIL:
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


DEMO_PROFILE_IMAGE_URLS = [
    "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1511379938547-c1f69419868d?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1521337581100-8ca9a73a5f79?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1501612780327-45045538702b?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1517230878791-4d28214057c2?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1525201548942-d8732f6617a0?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1520523839897-bd0b52f945a0?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1526328828355-69b01701ca6a?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1510915361894-db8b60106cb1?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1461784121038-f088ca1e7714?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1531651008558-ed1740375b39?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1511367461989-f85a21fda167?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1507838153414-b4b713384a76?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1511192336575-5a79af67a629?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1499364615650-ec38552f4f34?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1429962714451-bb934ecdc4ec?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=1000&q=80&sat=-15",
]


DEMO_PROFILES = [
    ("sample.jasmine.reed@example.com", "Jasmine Reed", "Singer", "R&B / Soul", "Jackson", "MS", "Voice", "Hooks, Background Vocals, Live Performance", "Warm vocals, harmony stacks, and live-show poise for studio sessions and showcases."),
    ("sample.marcus.bell@example.com", "Marcus Bell", "Gospel Musician", "Gospel / Worship", "McComb", "MS", "Keyboard, Organ", "Sunday service, choir support, MD support", "Church-ready keys player available for worship teams, rehearsals, and recordings."),
    ("sample.delta.pulse@example.com", "Delta Pulse Band", "Band", "Blues / Southern Soul", "Hattiesburg", "MS", "Guitar, Bass, Drums", "Festivals, Openers, Collaborations", "Working southern soul band seeking horn players and regional opener slots."),
    ("sample.ari.stone@example.com", "Ari Stone", "Producer", "Hip-Hop / Pop", "Memphis", "TN", "Beat Production, Keys", "Production, Vocal Arrangement, Mixing Prep", "Producer building polished records with vocalists, rappers, and writers across the Mid-South."),
    ("sample.nyla.marie@example.com", "Nyla Marie", "Rapper", "Hip-Hop", "New Orleans", "LA", "Voice", "Features, Live Sets, Writing", "Sharp verse writer with high-energy stage presence and collaborative studio focus."),
    ("sample.eli.brooks@example.com", "Eli Brooks", "Bassist", "Jazz / Funk", "Biloxi", "MS", "Bass", "Live Bass, Studio Tracking, Rehearsals", "Pocket-first bassist for jazz sets, gospel services, funk bands, and studio dates."),
    ("sample.camille.price@example.com", "Camille Price", "Audio Engineer", "R&B / Gospel", "Baton Rouge", "LA", "Console, Pro Tools", "Recording, Mixing, Live Sound", "Engineer focused on clean vocals, church events, and artist-friendly studio sessions."),
    ("sample.noah.king@example.com", "Noah King", "Drummer", "Gospel / Rock", "Gulfport", "MS", "Drums", "Live Drums, Session Tracking, Auditions", "Dynamic drummer available for churches, touring artists, and weekend showcases."),
    ("sample.sofia.valdez@example.com", "Sofia Valdez", "Violinist", "Classical / Pop", "Oxford", "MS", "Violin", "Strings, Weddings, Studio Layers", "Violinist adding strings to recordings, weddings, worship nights, and acoustic showcases."),
    ("sample.miles.carter@example.com", "Miles Carter", "Jazz Musician", "Jazz / Blues", "Tupelo", "MS", "Saxophone", "Live Horns, Sessions, Arrangements", "Saxophonist with blues roots and smooth jazz phrasing for bands and studio work."),
    ("sample.kenya.ross@example.com", "Kenya Ross", "Choir Director", "Gospel", "Meridian", "MS", "Voice, Piano", "Choir Direction, Vocal Coaching", "Choir director helping churches build confident, modern worship teams."),
    ("sample.dj.ren@example.com", "DJ Ren", "DJ", "Hip-Hop / Club", "Mobile", "AL", "DJ", "DJ Bookings, Event Hosting", "Open-format DJ for college nights, showcases, private events, and artist release parties."),
    ("sample.lena.gray@example.com", "Lena Gray", "Country Artist", "Country / Americana", "Hattiesburg", "MS", "Guitar, Voice", "Acoustic Sets, Songwriting", "Country storyteller booking acoustic sets and co-writing sessions."),
    ("sample.rivercity.brass@example.com", "River City Brass", "Brass Section", "Soul / Marching Band", "New Orleans", "LA", "Trumpet, Trombone, Saxophone", "Horn Section, Parade Sets, Studio Horns", "Brass collective available for stage punch, second-line energy, and studio sections."),
    ("sample.zion.walker@example.com", "Zion Walker", "Guitarist", "Blues / Gospel", "Jackson", "MS", "Guitar", "Lead Guitar, Worship Nights, Studio Tracking", "Expressive guitarist available for church services, blues sets, and artist sessions."),
    ("sample.maya.hart@example.com", "Maya Hart", "Music Teacher", "Classical / Pop", "Baton Rouge", "LA", "Piano, Voice", "Lessons, Audition Prep, Vocal Coaching", "Teacher and coach helping new musicians build confidence for stage and studio."),
    ("sample.coastline.collective@example.com", "Coastline Collective", "Band", "R&B / Funk", "Gulfport", "MS", "Full Band", "Private Events, Festivals, Openers", "Flexible live band booking polished sets for weddings, festivals, and artist showcases."),
    ("sample.omar.price@example.com", "Omar Price", "Producer", "Trap / Gospel", "Memphis", "TN", "MPC, Keys", "Beat Production, Session Direction, Artist Development", "Producer blending church chords, trunk knock, and artist-first studio direction."),
    ("sample.alana.brooks@example.com", "Alana Brooks", "Classical Musician", "Classical / Film", "Meridian", "MS", "Cello", "Strings, Scores, Weddings, Studio Layers", "Cellist available for string sections, ceremonies, scoring sessions, and live ensembles."),
    ("sample.kai.morgan@example.com", "Kai Morgan", "Live Sound Engineer", "Rock / Gospel / Country", "Mobile", "AL", "Live Sound", "FOH, Monitors, Festival Support", "Live engineer supporting churches, venues, outdoor events, and touring artists."),
]


DEMO_OPPORTUNITIES = [
    ("Gospel keys player needed for Sunday services", "Church Music", "Keyboard Player", "Keyboard, Organ", "Gospel", "Jackson", "MS", "New Hope Worship Center", "Paid", "$175 per service", "2026-08-02 09:00", "2026-07-30", "Email", "", "church-jackson-keys", 1),
    ("Wedding band hiring bassist for August dates", "Paid Performance", "Bassist", "Bass", "R&B, Soul, Pop", "McComb", "MS", "Magnolia Event Band", "Paid", "$300 per event", "2026-08-15 18:00", "2026-08-05", "Message", "", "mccomb-wedding-bass", 1),
    ("Producer seeking vocalist for EP sessions", "Collaboration", "Vocalist", "Voice", "R&B, Pop", "Memphis", "TN", "Southside Studio", "Collaboration", "Split agreement", "2026-08-07 13:00", "2026-08-01", "Message", "", "memphis-vocalist-ep", 1),
    ("Venue seeking opening act for Friday concert", "Opening Act", "Band or Solo Artist", "Any", "Blues, Soul, Rock", "Hattiesburg", "MS", "The Rail Room", "Paid", "$250 flat", "2026-07-31 20:00", "2026-07-26", "Application URL", "", "hattiesburg-opener", 1),
    ("Studio booking session drummer", "Recording Session", "Drummer", "Drums", "Gospel, Funk", "Gulfport", "MS", "Coastline Recording", "Paid", "$80/hour", "2026-08-10 11:00", "2026-08-03", "Email", "", "gulfport-session-drums", 0),
    ("Auditions for regional touring choir", "Audition", "Singers", "Voice", "Gospel, Classical", "Meridian", "MS", "Queen City Arts Hall", "Unpaid", "Travel stipend for selected singers", "2026-08-18 17:30", "2026-08-12", "Application URL", "", "meridian-choir-audition", 0),
    ("DJ needed for college welcome-week event", "DJ Booking", "DJ", "DJ", "Hip-Hop, Pop", "Oxford", "MS", "Campus Activities Board", "Paid", "$500", "2026-08-23 19:00", "2026-08-10", "Email", "", "oxford-dj-welcome", 0),
    ("Singer-songwriter seeks violinist for live session", "Collaboration", "Violinist", "Violin", "Country, Americana", "Tupelo", "MS", "Warehouse Studio", "Collaboration", "Video credit plus split", "2026-08-05 15:00", "2026-07-29", "Message", "", "tupelo-violin-live", 0),
    ("Audio engineer for church music conference", "Sound Engineer", "Live Sound Engineer", "Live Sound", "Gospel", "Baton Rouge", "LA", "River Center", "Paid", "$650 weekend rate", "2026-09-04 10:00", "2026-08-20", "Email", "", "baton-rouge-sound", 1),
    ("Battle of the bands looking for contestants", "Showcase", "Band", "Full Band", "Rock, Hip-Hop, Blues", "Biloxi", "MS", "Coast Music Hall", "Paid", "Prize pool", "2026-08-29 18:00", "2026-08-16", "Application URL", "", "biloxi-band-battle", 0),
    ("Producer needs rapper for weekend studio lock-in", "Collaboration", "Rapper", "Voice", "Hip-Hop", "Memphis", "TN", "Memphis Music Lab", "Collaboration", "Split agreement", "2026-08-09 14:00", "2026-08-04", "Message", "", "memphis-rapper-lockin", 0),
    ("Choir needs alto section leader", "Church Music", "Alto Section Leader", "Voice", "Gospel", "Meridian", "MS", "Queen City Choirs", "Paid", "$125 rehearsal stipend", "2026-08-12 18:30", "2026-08-08", "Email", "", "meridian-alto-leader", 0),
    ("Country artist seeking pedal steel player", "Recording Session", "Pedal Steel Player", "Pedal Steel", "Country, Americana", "Hattiesburg", "MS", "Pine Belt Studio", "Paid", "$200 session", "2026-08-16 12:00", "2026-08-09", "Message", "", "hattiesburg-pedal-steel", 0),
    ("Mobile venue needs Saturday DJ", "DJ Booking", "DJ", "DJ", "Hip-Hop, R&B, Pop", "Mobile", "AL", "Saenger Lounge", "Paid", "$400", "2026-08-17 21:00", "2026-08-11", "Email", "", "mobile-saturday-dj", 0),
    ("Jazz trio looking for upright bassist", "Band Member", "Bassist", "Upright Bass", "Jazz", "New Orleans", "LA", "Frenchmen Street Co-op", "Paid", "$150 plus tips", "2026-08-20 20:00", "2026-08-13", "Message", "", "nola-upright-bass", 0),
]


DEMO_EVENTS = [
    ("Jackson Soul Night", "Concert", "Jasmine Reed and friends", "Duling Hall", "Jackson", "MS", "2026-07-25 20:00", "R&B / Soul", 18, 35, "Venue Calendar", "https://images.unsplash.com/photo-1501612780327-45045538702b?auto=format&fit=crop&w=1200&q=80", "jackson-soul-night", 1),
    ("McComb Gospel Choir Workshop", "Workshop", "Kenya Ross", "Summit Arts Center", "McComb", "MS", "2026-07-26 10:00", "Gospel", 0, 15, "Local Arts Feed", "https://images.unsplash.com/photo-1521337581100-8ca9a73a5f79?auto=format&fit=crop&w=1200&q=80", "mccomb-gospel-workshop", 1),
    ("Hattiesburg Open Mic", "Open Mic", "Hosted by The Rail Room", "The Rail Room", "Hattiesburg", "MS", "2026-07-24 19:30", "Open Mic", 0, 0, "Venue Calendar", "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=1200&q=80", "hattiesburg-open-mic", 1),
    ("Gulfport Jazz on the Coast", "Festival", "Miles Carter Quartet", "Jones Park", "Gulfport", "MS", "2026-08-01 17:00", "Jazz", 20, 45, "Tourism Calendar", "https://images.unsplash.com/photo-1511192336575-5a79af67a629?auto=format&fit=crop&w=1200&q=80", "gulfport-jazz-coast", 1),
    ("Biloxi Band Battle", "Battle", "Coast Music Hall", "Coast Music Hall", "Biloxi", "MS", "2026-08-29 18:00", "Rock / Hip-Hop", 12, 20, "Venue Calendar", "https://images.unsplash.com/photo-1499364615650-ec38552f4f34?auto=format&fit=crop&w=1200&q=80", "biloxi-band-battle-event", 0),
    ("Oxford Songwriters Circle", "Artist Meetup", "Lena Gray", "Proud Larry's", "Oxford", "MS", "2026-08-08 18:30", "Country / Americana", 10, 10, "Community Feed", "https://images.unsplash.com/photo-1510915361894-db8b60106cb1?auto=format&fit=crop&w=1200&q=80", "oxford-songwriters", 0),
    ("Memphis Producer Meetup", "Networking", "Ari Stone", "Memphis Music Lab", "Memphis", "TN", "2026-08-06 19:00", "Hip-Hop / R&B", 0, 0, "Public Community Feed", "https://images.unsplash.com/photo-1511379938547-c1f69419868d?auto=format&fit=crop&w=1200&q=80", "memphis-producer-meetup", 1),
    ("New Orleans Brass Jam", "Jam Session", "River City Brass", "Frenchmen Street Co-op", "New Orleans", "LA", "2026-08-03 21:00", "Brass / Soul", 8, 15, "Venue Calendar", "https://images.unsplash.com/photo-1461784121038-f088ca1e7714?auto=format&fit=crop&w=1200&q=80", "nola-brass-jam", 0),
    ("Baton Rouge Music Conference", "Conference", "River Center Music Network", "River Center", "Baton Rouge", "LA", "2026-09-04 10:00", "Industry", 35, 95, "Arts Organization", "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=1200&q=80", "baton-rouge-conference", 1),
    ("Mobile DJ Showcase", "Showcase", "DJ Ren", "Saenger Theatre Lounge", "Mobile", "AL", "2026-08-14 21:00", "DJ / Club", 15, 25, "Venue Calendar", "https://images.unsplash.com/photo-1429962714451-bb934ecdc4ec?auto=format&fit=crop&w=1200&q=80", "mobile-dj-showcase", 0),
    ("Tupelo Studio Strings Session", "Workshop", "Sofia Valdez", "Warehouse Studio", "Tupelo", "MS", "2026-08-05 15:00", "Strings", 20, 30, "University Music Feed", "https://images.unsplash.com/photo-1507838153414-b4b713384a76?auto=format&fit=crop&w=1200&q=80", "tupelo-strings", 0),
    ("Meridian Choir Night", "Church Music Event", "Queen City Choirs", "Queen City Arts Hall", "Meridian", "MS", "2026-08-18 19:00", "Gospel", 0, 12, "Local Arts Feed", "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?auto=format&fit=crop&w=1200&q=80", "meridian-choir-night", 0),
    ("Jackson Battle of the Bands", "Battle of the Bands", "Capital City Music League", "Hal and Mal's", "Jackson", "MS", "2026-08-22 19:00", "Rock / Soul / Hip-Hop", 10, 20, "Venue Calendar", "https://images.unsplash.com/photo-1499364615650-ec38552f4f34?auto=format&fit=crop&w=1200&q=80", "jackson-battle-bands", 0),
    ("Baton Rouge Song Camp", "Workshop", "Maya Hart and River Center writers", "River Center Studio", "Baton Rouge", "LA", "2026-08-27 11:00", "Songwriting", 25, 45, "Arts Organization", "https://images.unsplash.com/photo-1511379938547-c1f69419868d?auto=format&fit=crop&w=1200&q=80", "baton-rouge-song-camp", 0),
    ("Memphis Studio Open House", "Artist Meetup", "Memphis Music Lab", "Memphis Music Lab", "Memphis", "TN", "2026-08-30 16:00", "Production / Networking", 0, 0, "Public Community Feed", "https://images.unsplash.com/photo-1525201548942-d8732f6617a0?auto=format&fit=crop&w=1200&q=80", "memphis-studio-open-house", 0),
]


def ns(row):
    return SimpleNamespace(**dict(row)) if row is not None else None


def ftb_gig_board_url(**values):
    return url_for(FTB_GIG_BOARD_ENDPOINT, **values)


def ftb_opportunity_url(opportunity_id):
    return url_for("opportunity_detail", opportunity_id=opportunity_id)


def ftb_apply_url(opportunity_id):
    return url_for("apply_opportunity", opportunity_id=opportunity_id)


def redirect_to_ftb_gig_board(**values):
    params = request.args.to_dict(flat=True)
    params.update({key: value for key, value in values.items() if value not in (None, "")})
    return redirect(ftb_gig_board_url(**params), code=302)


def opportunity_filters_from_request():
    return {
        "q": request.args.get("q", "").strip(),
        "role": request.args.get("role", "").strip(),
        "instrument": request.args.get("instrument", "").strip(),
        "genre": request.args.get("genre", "").strip(),
        "city": request.args.get("city", "").strip(),
        "state": request.args.get("state", "").strip(),
        "paid": request.args.get("paid", "").strip(),
    }


def row_to_opportunity(row):
    data = dict(row) if row is not None else {}
    for field in [
        "description", "opportunity_type", "role_needed", "instrument_needed",
        "genre", "city", "state", "location_name", "paid_status", "compensation",
        "event_date", "application_deadline", "contact_method", "application_url",
        "source_type", "source_name", "external_id", "source_url", "imported_at",
        "location_source", "created_at", "updated_at", "status",
    ]:
        data.setdefault(field, "")
    data.setdefault("latitude", None)
    data.setdefault("longitude", None)
    data.setdefault("is_featured", 0)
    data.setdefault("is_seeded_demo", 0)
    data.setdefault("created_by", None)
    return SimpleNamespace(**data) if data else None


def get_opportunities(filters=None, limit=None):
    filters = filters or {}
    clauses = [
        "status = 'active'",
        "(COALESCE(is_seeded_demo, 0) = 0 OR ? = 1)",
        """
        (
            title LIKE ? OR description LIKE ? OR opportunity_type LIKE ? OR
            role_needed LIKE ? OR instrument_needed LIKE ? OR genre LIKE ? OR
            location_name LIKE ?
        )
        """,
        """
        LOWER(COALESCE(source_name, '')) NOT LIKE '%second chance%' AND
        LOWER(COALESCE(source_type, '')) NOT LIKE '%second-chance%' AND
        LOWER(COALESCE(source_type, '')) NOT LIKE '%career%'
        """,
    ]
    params = []
    params.append(1 if FTB_SEED_DEMO_CONTENT or filters.get("include_demo") else 0)
    music_filter_sql = " OR ".join(
        """
        title LIKE ? OR description LIKE ? OR opportunity_type LIKE ? OR
        role_needed LIKE ? OR instrument_needed LIKE ? OR genre LIKE ? OR
        location_name LIKE ?
        """.strip()
        for _ in MUSIC_OPPORTUNITY_TERMS
    )
    clauses[2] = f"({music_filter_sql})"
    for term in MUSIC_OPPORTUNITY_TERMS:
        params.extend([f"%{term}%"] * 7)
    q = filters.get("q", "")
    if q:
        clauses.append(
            """
            (
                title LIKE ? OR description LIKE ? OR role_needed LIKE ? OR
                instrument_needed LIKE ? OR genre LIKE ? OR location_name LIKE ?
            )
            """
        )
        params.extend([f"%{q}%"] * 6)
    for key, column in {
        "role": "role_needed",
        "instrument": "instrument_needed",
        "genre": "genre",
        "city": "city",
        "state": "state",
        "paid": "paid_status",
    }.items():
        if filters.get(key):
            clauses.append(f"{column} LIKE ?")
            params.append(f"%{filters[key]}%")
    sql = f"""
        SELECT *
        FROM opportunities
        WHERE {' AND '.join(clauses)}
        ORDER BY datetime(created_at) DESC, id DESC
    """
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with get_db() as conn:
        return [row_to_opportunity(row) for row in conn.execute(sql, params).fetchall()]


def get_opportunity(opportunity_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM opportunities WHERE id = ? AND status = 'active'",
            (opportunity_id,),
        ).fetchone()
    return row_to_opportunity(row)


def row_to_event(row):
    data = dict(row) if row is not None else {}
    for field in [
        "description", "event_type", "performer", "venue", "address", "city", "state",
        "postal_code", "start_datetime", "end_datetime", "ticket_url", "source_url",
        "source_name", "external_id", "image_url", "genre", "verification_status",
        "created_at", "updated_at", "location_source",
    ]:
        data.setdefault(field, "")
    data.setdefault("latitude", None)
    data.setdefault("longitude", None)
    data.setdefault("price_min", None)
    data.setdefault("price_max", None)
    data.setdefault("is_featured", 0)
    data.setdefault("is_seeded_demo", 0)
    return SimpleNamespace(**data) if data else None


def get_events(limit=None, include_demo=None):
    include_seeded = FTB_SEED_DEMO_CONTENT if include_demo is None else include_demo
    sql = """
        SELECT *
        FROM events
        WHERE COALESCE(verification_status, 'reviewed') NOT IN ('hidden', 'rejected')
          AND (COALESCE(is_seeded_demo, 0) = 0 OR ? = 1)
        ORDER BY datetime(COALESCE(NULLIF(start_datetime, ''), created_at)) ASC, id DESC
    """
    params = [1 if include_seeded else 0]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with get_db() as conn:
        return [row_to_event(row) for row in conn.execute(sql, params).fetchall()]


def get_event(event_id):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM events
            WHERE id = ?
              AND COALESCE(verification_status, 'reviewed') NOT IN ('hidden', 'rejected')
              AND (COALESCE(is_seeded_demo, 0) = 0 OR ? = 1)
            """,
            (event_id, 1 if FTB_SEED_DEMO_CONTENT else 0),
        ).fetchone()
    return row_to_event(row)


def create_opportunity(user_id, fields):
    latitude, longitude, location_source = geocode_location(
        fields.get("city", ""),
        fields.get("state", ""),
        location_text=fields.get("location_name", ""),
    )
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO opportunities (
                title, description, opportunity_type, role_needed, instrument_needed,
                genre, city, state, location_name, paid_status, compensation,
                event_date, application_deadline, contact_method, application_url,
                latitude, longitude, location_source,
                created_by, source_name, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Find The Beat', 'active', CURRENT_TIMESTAMP)
            """,
            (
                fields["title"],
                fields["description"],
                fields["opportunity_type"],
                fields["role_needed"],
                fields["instrument_needed"],
                fields["genre"],
                fields["city"],
                fields["state"],
                fields["location_name"],
                fields["paid_status"],
                fields["compensation"],
                fields["event_date"],
                fields["application_deadline"],
                fields["contact_method"],
                fields["application_url"],
                latitude,
                longitude,
                location_source,
                user_id,
            ),
        )
        log_activity(user_id, "opportunity_posted", fields["title"])
        return cursor.lastrowid


def http_json(url, params=None, headers=None, timeout=15):
    query = urlencode(params or {}, doseq=True)
    request_url = f"{url}?{query}" if query else url
    req = Request(request_url, headers=headers or {"User-Agent": "FindTheBeat/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        app.logger.warning("Opportunity import request failed for %s: %s", url, exc)
        return None


def upsert_imported_opportunity(conn, item):
    source_name = item.get("source_name", "").strip()
    external_id = item.get("external_id", "").strip()
    if not source_name or not external_id or not item.get("title"):
        return False
    existing = conn.execute(
        "SELECT id FROM opportunities WHERE source_name = ? AND external_id = ?",
        (source_name, external_id),
    ).fetchone()
    latitude, longitude, location_source = geocode_location(
        item.get("city", ""),
        item.get("state", ""),
        location_text=item.get("location_name", ""),
    )
    values = (
        item["title"],
        item.get("description", ""),
        item.get("opportunity_type", ""),
        item.get("role_needed", ""),
        item.get("instrument_needed", ""),
        item.get("genre", ""),
        item.get("city", ""),
        item.get("state", ""),
        item.get("location_name", ""),
        item.get("paid_status", ""),
        item.get("compensation", ""),
        item.get("event_date", ""),
        item.get("application_deadline", ""),
        item.get("contact_method", ""),
        item.get("application_url", ""),
        item.get("source_url", ""),
        latitude,
        longitude,
        location_source,
        source_name,
        external_id,
    )
    if existing:
        conn.execute(
            """
            UPDATE opportunities
            SET title = ?, description = ?, opportunity_type = ?, role_needed = ?,
                instrument_needed = ?, genre = ?, city = ?, state = ?, location_name = ?,
                paid_status = ?, compensation = ?, event_date = ?, application_deadline = ?,
                contact_method = ?, application_url = ?, source_url = ?, latitude = ?,
                longitude = ?, location_source = ?, source_name = ?, external_id = ?,
                imported_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                status = 'active'
            WHERE id = ?
            """,
            (*values, existing["id"]),
        )
        return False
    conn.execute(
        """
        INSERT INTO opportunities (
            title, description, opportunity_type, role_needed, instrument_needed,
            genre, city, state, location_name, paid_status, compensation,
            event_date, application_deadline, contact_method, application_url,
            source_url, latitude, longitude, location_source, source_name, external_id,
            imported_at, status, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'active', CURRENT_TIMESTAMP)
        """,
        values,
    )
    return True


def import_ticketmaster_opportunities():
    if not TICKETMASTER_API_KEY:
        return 0
    imported = 0
    with get_db() as conn:
        for keyword in TICKETMASTER_IMPORT_KEYWORDS:
            data = http_json(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                {
                    "apikey": TICKETMASTER_API_KEY,
                    "keyword": keyword,
                    "city": TICKETMASTER_IMPORT_CITY or None,
                    "stateCode": TICKETMASTER_IMPORT_STATE or None,
                    "countryCode": TICKETMASTER_IMPORT_COUNTRY,
                    "classificationName": "music",
                    "size": 20,
                },
            )
            for event in ((data or {}).get("_embedded") or {}).get("events", []):
                venue = (((event.get("_embedded") or {}).get("venues") or [{}])[0])
                dates = event.get("dates") or {}
                start = dates.get("start") or {}
                imported += int(upsert_imported_opportunity(conn, {
                    "title": event.get("name") or "Live music event",
                    "description": event.get("info") or event.get("pleaseNote") or "Music event imported for Find The Beat discovery.",
                    "opportunity_type": "Upcoming Live Event",
                    "role_needed": "Performer or attendee",
                    "genre": keyword,
                    "city": venue.get("city", {}).get("name", ""),
                    "state": venue.get("state", {}).get("stateCode", ""),
                    "location_name": venue.get("name", ""),
                    "paid_status": "Ticketed",
                    "event_date": " ".join(part for part in [start.get("localDate", ""), start.get("localTime", "")] if part),
                    "contact_method": "External link",
                    "application_url": event.get("url", ""),
                    "source_url": event.get("url", ""),
                    "source_name": "Ticketmaster",
                    "external_id": str(event.get("id") or ""),
                }))
    return imported


def import_eventbrite_opportunities():
    if not EVENTBRITE_OAUTH_TOKEN:
        return 0
    data = http_json(
        "https://www.eventbriteapi.com/v3/events/search/",
        {"q": EVENTBRITE_IMPORT_QUERY, "location.address": EVENTBRITE_IMPORT_LOCATION, "expand": "venue"},
        headers={"Authorization": f"Bearer {EVENTBRITE_OAUTH_TOKEN}", "User-Agent": "FindTheBeat/1.0"},
    )
    imported = 0
    with get_db() as conn:
        for event in (data or {}).get("events", []):
            venue = event.get("venue") or {}
            address = venue.get("address") or {}
            imported += int(upsert_imported_opportunity(conn, {
                "title": event.get("name", {}).get("text") or "Music event",
                "description": event.get("description", {}).get("text") or "Music opportunity imported for Find The Beat discovery.",
                "opportunity_type": "Upcoming Live Event",
                "role_needed": "Performer or attendee",
                "city": address.get("city", ""),
                "state": address.get("region", ""),
                "location_name": venue.get("name", ""),
                "paid_status": "Ticketed",
                "event_date": (event.get("start") or {}).get("local", ""),
                "contact_method": "External link",
                "application_url": event.get("url", ""),
                "source_url": event.get("url", ""),
                "source_name": "Eventbrite",
                "external_id": str(event.get("id") or ""),
            }))
    return imported


def import_bandsintown_opportunities():
    if not BANDSINTOWN_APP_ID or not BANDSINTOWN_IMPORT_ARTISTS:
        return 0
    imported = 0
    with get_db() as conn:
        for artist in BANDSINTOWN_IMPORT_ARTISTS:
            events = http_json(
                f"https://rest.bandsintown.com/artists/{artist}/events",
                {"app_id": BANDSINTOWN_APP_ID},
            )
            if not isinstance(events, list):
                continue
            for event in events[:20]:
                venue = event.get("venue") or {}
                imported += int(upsert_imported_opportunity(conn, {
                    "title": f"{artist} live opportunity",
                    "description": "Artist tour activity imported for Find The Beat discovery.",
                    "opportunity_type": "Upcoming Live Event",
                    "role_needed": "Performer or attendee",
                    "genre": "Live music",
                    "city": venue.get("city", ""),
                    "state": venue.get("region", ""),
                    "location_name": venue.get("name", ""),
                    "event_date": event.get("datetime", ""),
                    "contact_method": "External link",
                    "application_url": event.get("url", ""),
                    "source_url": event.get("url", ""),
                    "source_name": "Bandsintown",
                    "external_id": str(event.get("id") or event.get("url") or ""),
                }))
    return imported


def import_live_opportunities():
    totals = {
        "Ticketmaster": import_ticketmaster_opportunities(),
        "Eventbrite": import_eventbrite_opportunities(),
        "Bandsintown": import_bandsintown_opportunities(),
    }
    return totals


def seed_demo_profiles_if_empty():
    if not FTB_SEED_DEMO_CONTENT:
        return
    with get_db() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_seeded_demo = 1 OR email LIKE 'sample.%@example.com'"
        ).fetchone()[0]
        if existing >= len(DEMO_PROFILES):
            return
        for index, profile in enumerate(DEMO_PROFILES):
            (
                email, display_name, role, genre, city, state, instrument,
                services_csv, bio,
            ) = profile
            conn.execute(
                """
                INSERT INTO users (
                    email, password_hash, display_name, role, genre, city, state, country,
                    bio, tags_csv, instrument, services_csv, availability, avatar_url,
                    profile_photo, is_seeded_demo, demo_label, is_verified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'United States', ?, ?, ?, ?, ?, ?, ?, 1, 'Community Spotlight', 1)
                ON CONFLICT(email) DO UPDATE SET
                    display_name = excluded.display_name,
                    role = excluded.role,
                    genre = excluded.genre,
                    city = excluded.city,
                    state = excluded.state,
                    bio = excluded.bio,
                    tags_csv = excluded.tags_csv,
                    instrument = excluded.instrument,
                    services_csv = excluded.services_csv,
                    availability = excluded.availability,
                    avatar_url = excluded.avatar_url,
                    profile_photo = excluded.profile_photo,
                    is_seeded_demo = 1,
                    demo_label = 'Community Spotlight',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    email,
                    generate_password_hash(secrets.token_urlsafe(24)),
                    display_name,
                    role,
                    genre,
                    city,
                    state,
                    bio,
                    "Seeded Demo, Community Spotlight, Available for Work",
                    instrument,
                    services_csv,
                    "Available for bookings, collaborations, and selected opportunities.",
                    DEMO_PROFILE_IMAGE_URLS[index % len(DEMO_PROFILE_IMAGE_URLS)],
                    DEMO_PROFILE_IMAGE_URLS[index % len(DEMO_PROFILE_IMAGE_URLS)],
                ),
            )
            row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                ensure_app_profile(conn, row["id"], "find-the-beat")


def seed_community_content():
    if not FTB_SEED_DEMO_CONTENT:
        return
    with get_db() as conn:
        for item in DEMO_OPPORTUNITIES:
            conn.execute(
                """
                INSERT OR IGNORE INTO opportunities (
                    title, opportunity_type, role_needed, instrument_needed, genre, city, state,
                    location_name, paid_status, compensation, event_date, application_deadline,
                    contact_method, application_url, source_type, source_name, external_id,
                    is_featured, is_seeded_demo, status, description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'seeded', 'FindTheBeat Demo Seed', ?, ?, 1, 'active', ?)
                """,
                (
                    item[0], item[1], item[2], item[3], item[4], item[5], item[6],
                    item[7], item[8], item[9], item[10], item[11], item[12], item[13],
                    item[14], item[15],
                    f"{item[1]} opportunity in {item[5]} for {item[2].lower()}."
                ),
            )

        for item in DEMO_EVENTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO events (
                    title, event_type, performer, venue, city, state, start_datetime, genre,
                    price_min, price_max, source_name, image_url, external_id, is_featured,
                    is_seeded_demo, verification_status, description, source_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'reviewed', ?, '')
                """,
                (
                    item[0], item[1], item[2], item[3], item[4], item[5],
                    item[6], item[7], item[8], item[9], item[10], item[11],
                    item[12], item[13],
                    f"{item[1]} listing sourced from {item[10]} for Find The Beat discovery."
                ),
            )

        feed_count = conn.execute("SELECT COUNT(*) FROM feed_items WHERE is_seeded_demo = 1").fetchone()[0]
        if feed_count < 20:
            conn.execute("DELETE FROM feed_items WHERE is_seeded_demo = 1")
            feed_items = [
                ("Upload", "Jasmine Reed uploaded a live R&B performance", "A new vocal showcase is live from Jackson.", "Jackson", "MS", "platform"),
                ("Opportunity", "New church keys opportunity posted", "A Jackson worship team needs a keyboard player this month.", "Jackson", "MS", "platform"),
                ("Event", "Hattiesburg open mic is happening this week", "Local singers, rappers, and bands can sign up at the venue.", "Hattiesburg", "MS", "Venue Calendar"),
                ("Profile", "Ari Stone is available for vocal production", "Producer profile updated with studio availability.", "Memphis", "TN", "platform"),
                ("Audition", "Regional choir auditions were added", "Singers can review the Meridian audition window.", "Meridian", "MS", "Local Arts Feed"),
                ("Collab", "Singer-songwriter seeks violinist", "A Tupelo live-session collaboration is open now.", "Tupelo", "MS", "platform"),
                ("Event", "Gulfport Jazz on the Coast announced", "A weekend festival listing is ready for review.", "Gulfport", "MS", "Tourism Calendar"),
                ("Booking", "DJ booking request opened in Oxford", "Campus welcome week needs an open-format DJ.", "Oxford", "MS", "platform"),
                ("Profile", "River City Brass joined the community", "New brass section profile added from New Orleans.", "New Orleans", "LA", "platform"),
                ("Opportunity", "Baton Rouge needs a live sound engineer", "Conference organizers are reviewing engineer applications.", "Baton Rouge", "LA", "Arts Organization"),
                ("Event", "Memphis producer meetup added", "Producers and vocalists can connect at the music lab.", "Memphis", "TN", "Public Community Feed"),
                ("Showcase", "Biloxi battle of the bands is recruiting", "Bands can apply for a paid prize-pool showcase.", "Biloxi", "MS", "Venue Calendar"),
                ("Profile", "Sofia Valdez marked strings available", "Violin and studio layers are open for August sessions.", "Oxford", "MS", "platform"),
                ("Opportunity", "Studio drummer request posted in Gulfport", "Coastline Recording is looking for session drums.", "Gulfport", "MS", "platform"),
                ("Event", "Mobile DJ Showcase announced", "A public showcase listing is ready for local discovery.", "Mobile", "AL", "Venue Calendar"),
                ("Profile", "Kenya Ross added choir direction services", "Choir support and vocal coaching are now listed.", "Meridian", "MS", "platform"),
                ("Opportunity", "Venue seeking Friday opening act", "The Rail Room is reviewing blues, soul, and rock acts.", "Hattiesburg", "MS", "platform"),
                ("Event", "New Orleans brass jam added", "A late-night jam session is listed from a venue calendar.", "New Orleans", "LA", "Venue Calendar"),
                ("Collab", "Producer needs rapper for weekend lock-in", "A Memphis studio session is looking for a rapper with quick turnaround.", "Memphis", "TN", "platform"),
                ("Gig", "Mobile venue needs a Saturday DJ", "A paid DJ booking is open for a late-night crowd.", "Mobile", "AL", "Venue Calendar"),
            ]
            for index, item in enumerate(feed_items):
                conn.execute(
                    """
                    INSERT INTO feed_items (
                        activity_type, title, description, city, state, source_type, source_name,
                        image_url, occurred_at, is_seeded_demo
                    )
                    VALUES (?, ?, ?, ?, ?, 'seeded', ?, ?, datetime('now', ?), 1)
                    """,
                    (
                        item[0], item[1], item[2], item[3], item[4], item[5],
                        DEMO_PROFILE_IMAGE_URLS[index % len(DEMO_PROFILE_IMAGE_URLS)],
                        f"-{index * 3 + 1} hours",
                    ),
                )


def dedupe_event_candidate(conn, source_name, external_id, title, venue, city, start_datetime):
    if source_name and external_id:
        row = conn.execute(
            "SELECT id FROM events WHERE source_name = ? AND external_id = ?",
            (source_name, external_id),
        ).fetchone()
        if row:
            return row["id"]
    row = conn.execute(
        """
        SELECT id
        FROM events
        WHERE lower(title) = lower(?)
          AND lower(COALESCE(venue, '')) = lower(?)
          AND lower(COALESCE(city, '')) = lower(?)
          AND date(start_datetime) = date(?)
        """,
        (title, venue or "", city or "", start_datetime or ""),
    ).fetchone()
    return row["id"] if row else None


def archive_expired_listings():
    with get_db() as conn:
        conn.execute(
            """
            UPDATE opportunities
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'active'
              AND COALESCE(application_deadline, event_date, '') != ''
              AND datetime(COALESCE(NULLIF(application_deadline, ''), event_date)) < datetime('now', '-1 day')
            """
        )
        conn.execute(
            """
            UPDATE events
            SET verification_status = CASE
                WHEN verification_status = 'verified' THEN 'completed'
                ELSE verification_status
            END,
                updated_at = CURRENT_TIMESTAMP
            WHERE COALESCE(start_datetime, '') != ''
              AND datetime(start_datetime) < datetime('now', '-1 day')
              AND verification_status != 'completed'
            """
        )


def discovery_record_category(record):
    text = " ".join(
        str(record.get(key, "") or "").lower()
        for key in ("title", "subtitle", "description", "type", "role", "location_name")
    )
    if record["kind"] == "showcase":
        return "showcases"
    if record["kind"] == "event":
        return "events"
    if record["kind"] == "venue":
        return "venues"
    if record["kind"] == "creator":
        if any(word in text for word in ["producer", "songwriter", "composer"]):
            return "producers"
        return "musicians"
    if "church" in text or "worship" in text:
        return "churches"
    if "audition" in text:
        return "auditions"
    if "collab" in text or "collaboration" in text:
        return "collaborations"
    if any(word in text for word in ["event", "live", "show", "concert", "open mic"]):
        return "events"
    if record.get("location_name"):
        return "venues"
    return "gigs"


def record_matches_category(record, category):
    if category in ("", "all"):
        return True
    if category == "remote":
        return record.get("is_remote")
    if category == "gigs":
        return record["kind"] == "opportunity"
    if category == "musicians":
        return record["kind"] == "creator" and discovery_record_category(record) == "musicians"
    if category == "producers":
        return record["kind"] == "creator" and discovery_record_category(record) == "producers"
    return discovery_record_category(record) == category


def map_record(kind, record_id, title, subtitle, description, city, state, latitude, longitude, href, **extra):
    title = title or "Music activity"
    latitude = extra.get("fallback_latitude", latitude)
    longitude = extra.get("fallback_longitude", longitude)
    position = us_marker_position(latitude, longitude)
    data = {
        "kind": kind,
        "id": record_id,
        "title": title,
        "subtitle": subtitle or "",
        "description": description or "",
        "city": city or "",
        "state": state or "",
        "latitude": latitude,
        "longitude": longitude,
        "href": href,
        "position": position,
        "distance": None,
        "is_remote": is_remote_record(title, subtitle, description, city, state, extra.get("location_name", "")),
        **extra,
    }
    data["category"] = discovery_record_category(data)
    return SimpleNamespace(**data)


def collect_discovery_records():
    records = []
    for opp in get_opportunities():
        subtitle_parts = [
            opp.opportunity_type or "Opportunity",
            opp.role_needed,
            opp.instrument_needed,
            opp.paid_status,
        ]
        records.append(
            map_record(
                "opportunity",
                opp.id,
                opp.title,
                " / ".join(part for part in subtitle_parts if part),
                opp.description,
                opp.city,
                opp.state,
                opp.latitude,
                opp.longitude,
                ftb_opportunity_url(opp.id),
                type=opp.opportunity_type,
                role=opp.role_needed,
                location_name=opp.location_name,
                created_at=opp.created_at,
            )
        )
        if opp.location_name and opp.latitude is not None and opp.longitude is not None:
            records.append(
                map_record(
                    "venue",
                    f"opportunity-{opp.id}",
                    opp.location_name,
                    "Venue / " + (opp.city or opp.state or "Location listed"),
                    f"Music activity connected to {opp.title}.",
                    opp.city,
                    opp.state,
                    opp.latitude,
                    opp.longitude,
                    ftb_opportunity_url(opp.id),
                    type="Venue",
                    role=opp.role_needed,
                    location_name=opp.location_name,
                    created_at=opp.created_at,
                )
            )
    for profile in search_profiles():
        records.append(
            map_record(
                "creator",
                profile.id,
                profile.display_name or profile.full_name or "Creator profile",
                profile.role or profile.instrument or "Creator",
                profile.bio,
                profile.city,
                profile.state,
                profile.latitude,
                profile.longitude,
                url_for("profile_detail", profile_id=profile.id),
                role=profile.role,
                created_at=profile.created_at,
            )
        )
    for perf in get_performances():
        profile = perf.profile
        records.append(
            map_record(
                "showcase",
                perf.id,
                perf.title,
                profile.display_name if profile else "Showcase",
                perf.description,
                perf.city or (profile.city if profile else ""),
                perf.state or (profile.state if profile else ""),
                perf.latitude or (profile.latitude if profile else None),
                perf.longitude or (profile.longitude if profile else None),
                url_for("performance_detail", perf_id=perf.id),
                role=profile.role if profile else "",
                created_at=perf.created_at,
            )
        )
    for event in get_events():
        records.append(
            map_record(
                "event",
                event.id,
                event.title,
                " / ".join(part for part in [event.event_type or "Live event", event.performer, event.venue] if part),
                event.description,
                event.city,
                event.state,
                event.latitude,
                event.longitude,
                url_for("event_detail", event_id=event.id),
                type=event.event_type,
                role=event.performer,
                location_name=event.venue,
                created_at=event.created_at,
            )
        )
        if event.venue and event.latitude is not None and event.longitude is not None:
            records.append(
                map_record(
                    "venue",
                    f"event-{event.id}",
                    event.venue,
                    "Venue / " + (event.city or event.state or "Location listed"),
                    f"Live activity connected to {event.title}.",
                    event.city,
                    event.state,
                    event.latitude,
                    event.longitude,
                    url_for("event_detail", event_id=event.id),
                    type="Venue",
                    role=event.performer,
                    location_name=event.venue,
                    created_at=event.created_at,
                )
            )
    return records


def discovery_filters_from_request():
    user = current_user()
    location = request.args.get("location", "").strip()
    use_profile = request.args.get("use_profile") == "1"
    if use_profile and user and not location:
        location = ", ".join(part for part in [user.city, user.state] if part)
    radius = request.args.get("radius", "25").strip() or "25"
    category = request.args.get("category", "all").strip() or "all"
    view = request.args.get("view", "map").strip() or "map"
    latitude, longitude, source = geocode_location(location_text=location)
    state = request.args.get("state", "").strip()
    if not state and location:
        state_match = re.search(r"\b([A-Z]{2})\b", location.upper())
        state = state_match.group(1) if state_match else ""
    return SimpleNamespace(
        location=location,
        radius=radius,
        category=category,
        view=view,
        use_profile=use_profile,
        latitude=latitude,
        longitude=longitude,
        geo_source=source,
        state=state,
    )


def filtered_discovery_records(filters):
    records = [record for record in collect_discovery_records() if record_matches_category(record.__dict__, filters.category)]
    remote_records = []
    map_records = []
    for record in records:
        if record.is_remote or not record.position:
            remote_records.append(record)
            continue
        if filters.radius == "remote":
            continue
        if filters.radius == "statewide" and filters.state:
            if (record.state or "").upper() != filters.state.upper():
                continue
        elif filters.radius not in ("nationwide", "statewide"):
            if filters.latitude is not None and filters.longitude is not None:
                distance = miles_between(filters.latitude, filters.longitude, record.latitude, record.longitude)
                record.distance = round(distance, 1)
                if distance > int(filters.radius):
                    continue
        map_records.append(record)
    if filters.radius == "remote":
        return [], remote_records
    return map_records, remote_records


def discovery_activity(records, filters):
    city_counts = {}
    for record in records:
        key = ", ".join(part for part in [record.city, record.state] if part) or "your area"
        city_counts.setdefault(key, {"opportunity": 0, "creator": 0, "showcase": 0, "venue": 0, "event": 0})
        city_counts[key][record.kind] += 1
    activity = []
    for place, counts in city_counts.items():
        if counts["opportunity"]:
            activity.append(f"{counts['opportunity']} opportunities active near {place}")
        if counts["creator"]:
            activity.append(f"{counts['creator']} creators available in {place}")
        if counts["showcase"]:
            activity.append(f"{counts['showcase']} showcases posted from {place}")
        if counts["venue"]:
            activity.append(f"{counts['venue']} music venues active near {place}")
        if counts["event"]:
            activity.append(f"{counts['event']} live events listed near {place}")
    if not activity and filters.location:
        activity.append(f"No mapped records yet for {filters.location}")
    return activity[:5]


def discovery_summary():
    records = collect_discovery_records()
    mapped = [record for record in records if record.position]
    remote = [record for record in records if record.is_remote or not record.position]
    return SimpleNamespace(
        mapped_count=len(mapped),
        remote_count=len(remote),
        opportunity_count=sum(1 for record in records if record.kind == "opportunity"),
        creator_count=sum(1 for record in records if record.kind == "creator"),
        showcase_count=sum(1 for record in records if record.kind == "showcase"),
        venue_count=sum(1 for record in records if record.kind == "venue"),
        event_count=sum(1 for record in records if record.kind == "event"),
    )


def backfill_record_coordinates():
    with get_db() as conn:
        for table, location_columns in {
            "users": ("city", "state", "city"),
            "opportunities": ("city", "state", "location_name"),
            "events": ("city", "state", "venue"),
        }.items():
            id_column = "id"
            rows = conn.execute(
                f"SELECT {id_column}, {location_columns[0]} AS city, {location_columns[1]} AS state, "
                f"{location_columns[2]} AS location_text, latitude, longitude FROM {table}"
            ).fetchall()
            for row in rows:
                if row["latitude"] is not None and row["longitude"] is not None:
                    continue
                latitude, longitude, source = geocode_location(
                    row["city"],
                    row["state"],
                    location_text=row["location_text"],
                )
                if latitude is not None and longitude is not None:
                    conn.execute(
                        f"UPDATE {table} SET latitude = ?, longitude = ?, location_source = ?, updated_at = CURRENT_TIMESTAMP WHERE {id_column} = ?",
                        (latitude, longitude, source, row[id_column]),
                    )
        rows = conn.execute(
            """
            SELECT p.id, p.latitude, p.longitude, u.latitude AS user_latitude,
                   u.longitude AS user_longitude, u.location_source AS user_location_source
            FROM performances p
            JOIN users u ON u.id = p.profile_id
            """
        ).fetchall()
        for row in rows:
            if (row["latitude"] is None or row["longitude"] is None) and row["user_latitude"] is not None:
                conn.execute(
                    "UPDATE performances SET latitude = ?, longitude = ?, location_source = ? WHERE id = ?",
                    (row["user_latitude"], row["user_longitude"], row["user_location_source"], row["id"]),
                )


def homepage_context(user=None):
    archive_expired_listings()
    user_get = user.get if isinstance(user, dict) else (lambda key, default="": getattr(user, key, default))
    user_city = user_get("city", "") if user else ""
    user_state = user_get("state", "") if user else ""
    user_role = user_get("role", "") if user else ""
    user_instrument = user_get("instrument", "") if user else ""
    user_genre = user_get("genre", "") if user else ""

    with get_db() as conn:
        opportunity_filters = {}
        if user_city:
            opportunity_filters["city"] = user_city
        if user_state:
            opportunity_filters["state"] = user_state
        opportunities = get_opportunities(opportunity_filters, limit=12)
        if len(opportunities) < 12 and opportunity_filters:
            seen_ids = {opp.id for opp in opportunities}
            opportunities.extend([opp for opp in get_opportunities(limit=12) if opp.id not in seen_ids][:12 - len(opportunities)])

        looking_items = [
            opp for opp in opportunities
            if (
                opp.opportunity_type in {"Collaboration", "Church Music", "Band Member", "DJ Booking", "Recording Session"}
                or any(term in (opp.title or "").lower() for term in ["needs", "needed", "seeking", "looking"])
            )
        ][:8]

        events = get_events(limit=15)

        feed_rows = conn.execute(
            """
            SELECT *
            FROM feed_items
            WHERE visibility = 'public'
            ORDER BY datetime(occurred_at) DESC, id DESC
            LIMIT 18
            """
        ).fetchall()
        feed_items = [ns(row) for row in feed_rows]

        admin_counts = {
            "pending_events": conn.execute("SELECT COUNT(*) FROM events WHERE verification_status IN ('pending', 'reviewed')").fetchone()[0],
            "active_opportunities": conn.execute("SELECT COUNT(*) FROM opportunities WHERE status = 'active'").fetchone()[0],
            "seeded_profiles": conn.execute("SELECT COUNT(*) FROM users WHERE is_seeded_demo = 1").fetchone()[0],
            "import_runs": conn.execute("SELECT COUNT(*) FROM event_import_runs").fetchone()[0],
        }

    def profile_value(profile, key, default=""):
        return profile.get(key, default) if isinstance(profile, dict) else getattr(profile, key, default)

    profiles = search_profiles(city=user_city, state=user_state) if (user_city or user_state) else search_profiles()
    profiles = [profile for profile in profiles if not profile_value(profile, "is_admin")][:6]
    if len(profiles) < 6:
        seen = {profile_value(profile, "id") for profile in profiles}
        profiles.extend([
            profile for profile in search_profiles()
            if profile_value(profile, "id") not in seen and not profile_value(profile, "is_admin")
        ][:6 - len(profiles)])

    personalized = {
        "greeting": f"Good morning, {user_get('display_name', '') or user_get('full_name', '') or 'friend'}" if user else "",
        "gig_matches": len([
            opp for opp in opportunities
            if any(term and term.lower() in " ".join([opp.role_needed, opp.instrument_needed, opp.genre]).lower()
                   for term in [user_role, user_instrument, user_genre])
        ]) if user else 0,
        "collaboration_matches": len([
            item for item in looking_items
            if any(term and term.lower() in " ".join([item.role_needed, item.instrument_needed, item.genre]).lower()
                   for term in [user_role, user_instrument, user_genre])
        ]) if user else 0,
        "nearby_musicians": len([profile for profile in profiles if user_city and profile_value(profile, "city") == user_city]) if user else 0,
        "weekend_events": len(events[:4]) if user else 0,
        "nearby_activity": len([item for item in feed_items if user_state and item.state == user_state]) if user else 0,
    }

    return {
        "opportunities": opportunities,
        "looking_items": looking_items,
        "events": events,
        "feed_items": feed_items,
        "featured_musicians": profiles,
        "personalized": personalized,
        "admin_listing_counts": admin_counts,
    }


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
                "genre": "Music technology, creator community",
                "city": "Jackson",
                "state": "MS",
                "country": "United States",
                "bio": OWNER_BIO,
                "tags_csv": "Founder, Brent & Co, Verified",
                "instrument": "Ecosystem Builder",
                "services_csv": "Creator connection, community support, app ecosystem",
                "previous_work": "Founder of Brent & Co, Find The Beat, Let's Cook Y'all, and Second Chance Careers.",
                "availability": "Available for Brent & Co updates, creator support, partnerships, and ecosystem questions.",
                "avatar_url": FOUNDER_AVATAR_URL,
                "profile_photo": FOUNDER_AVATAR_URL,
                "linkedin_url": FOUNDER_LINK_URL,
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
                    SET full_name = ?, display_name = ?, role = ?, genre = ?, city = ?,
                        state = ?, country = ?, bio = ?, tags_csv = ?, instrument = ?,
                        services_csv = ?, previous_work = ?, availability = ?,
                        avatar_url = COALESCE(NULLIF(avatar_url, ''), ?),
                        profile_photo = COALESCE(NULLIF(profile_photo, ''), ?),
                        linkedin_url = COALESCE(NULLIF(linkedin_url, ''), ?),
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
                        owner_values["state"],
                        owner_values["country"],
                        owner_values["bio"],
                        owner_values["tags_csv"],
                        owner_values["instrument"],
                        owner_values["services_csv"],
                        owner_values["previous_work"],
                        owner_values["availability"],
                        owner_values["avatar_url"],
                        owner_values["profile_photo"],
                        owner_values["linkedin_url"],
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
                    email, password_hash, full_name, display_name, role, genre, city,
                    state, country, bio, tags_csv, instrument, services_csv,
                    previous_work, availability, avatar_url, profile_photo, linkedin_url,
                    brent_account_id,
                    provider, auth_provider, authentication_provider, is_admin, is_founder, is_verified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1)
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
                    owner_values["state"],
                    owner_values["country"],
                    owner_values["bio"],
                    owner_values["tags_csv"],
                    owner_values["instrument"],
                    owner_values["services_csv"],
                    owner_values["previous_work"],
                    owner_values["availability"],
                    owner_values["avatar_url"],
                    owner_values["profile_photo"],
                    owner_values["linkedin_url"],
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


def profile_follow_counts(profile_id):
    with get_db() as conn:
        followers = conn.execute(
            "SELECT COUNT(*) FROM profile_follows WHERE followed_id = ?",
            (profile_id,),
        ).fetchone()[0]
        following = conn.execute(
            "SELECT COUNT(*) FROM profile_follows WHERE follower_id = ?",
            (profile_id,),
        ).fetchone()[0]
    return followers, following


def is_following_profile(follower_id, followed_id):
    if not follower_id or not followed_id:
        return False
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM profile_follows WHERE follower_id = ? AND followed_id = ?",
            (follower_id, followed_id),
        ).fetchone()
    return bool(row)


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
    viewer = current_user()
    community = homepage_context(viewer)
    creators = search_profiles(q, role, genre, city)[:6] if any([q, role, genre, city]) else community["featured_musicians"]
    return render_template(
        "index.html",
        creators=creators,
        featured_showcase=get_showcase_tiles(limit=6),
        category_tiles=SEARCH_CATEGORIES,
        opportunities=community["opportunities"],
        looking_items=community["looking_items"],
        events=community["events"],
        feed_items=community["feed_items"],
        featured_musicians=community["featured_musicians"],
        personalized=community["personalized"],
        admin_listing_counts=community["admin_listing_counts"],
        map_summary=discovery_summary(),
        q=q,
        role_filter=role,
        genre_filter=genre,
        city_filter=city,
    )


@app.route("/map")
@app.route("/discover")
def discovery_map():
    filters = discovery_filters_from_request()
    map_records, remote_records = filtered_discovery_records(filters)
    marker_json = json.dumps([record.__dict__ for record in map_records])
    query_args = request.args.to_dict(flat=True)
    return render_template(
        "map.html",
        filters=filters,
        categories=DISCOVERY_CATEGORY_LABELS,
        records=map_records,
        remote_records=remote_records,
        activity=discovery_activity(map_records + remote_records, filters),
        marker_json=marker_json,
        query_args=query_args,
    )


@app.route("/opportunities")
def opportunities_board():
    filters = SimpleNamespace(**opportunity_filters_from_request())
    return render_template(
        "opportunities.html",
        opportunities=get_opportunities(filters.__dict__),
        filters=filters,
    )


@app.route("/gigs")
@app.route("/gig-search")
@app.route("/find-a-gig")
@app.route("/explore-gigs")
@app.route("/open-gigs")
@app.route("/open-gigs-and-opportunities")
@app.route("/who-is-looking")
@app.route("/whos-looking")
def gig_board_alias():
    return redirect_to_ftb_gig_board()


@app.route("/find-matches")
def find_matches_alias():
    return redirect(url_for("profiles", **request.args.to_dict(flat=True)), code=302)


@app.route("/opportunities/<int:opportunity_id>")
def opportunity_detail(opportunity_id):
    opportunity = get_opportunity(opportunity_id)
    if not opportunity:
        flash("Opportunity not found.")
        return redirect(ftb_gig_board_url())
    return render_template("opportunity_detail.html", opportunity=opportunity)


@app.route("/events/<int:event_id>")
def event_detail(event_id):
    event = get_event(event_id)
    if not event:
        flash("Event not found.")
        return redirect(url_for("discovery_map", category="events"))
    return render_template("event_detail.html", event=event)


@app.route("/gigs/<int:opportunity_id>")
def gig_detail_alias(opportunity_id):
    return redirect(ftb_opportunity_url(opportunity_id), code=302)


@app.route("/opportunities/<int:opportunity_id>/apply", methods=["GET", "POST"])
@require_profile_action
def apply_opportunity(opportunity_id):
    opportunity = get_opportunity(opportunity_id)
    if not opportunity:
        flash("Opportunity not found.")
        return redirect(ftb_gig_board_url())
    user = current_user()
    log_activity(
        user.id,
        "opportunity_apply",
        f"Applied to opportunity {opportunity.id}",
        {"opportunity_id": opportunity.id},
    )
    flash("Your profile is ready. Review the opportunity details to continue.")
    return redirect(ftb_opportunity_url(opportunity.id))


@app.route("/opportunities/new", methods=["GET", "POST"])
@app.route("/post-opportunity", methods=["GET", "POST"])
@require_profile_action
def post_opportunity():
    user = current_user()
    if request.method == "POST":
        fields = {
            "title": request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "opportunity_type": request.form.get("opportunity_type", "").strip(),
            "role_needed": request.form.get("role_needed", "").strip(),
            "instrument_needed": request.form.get("instrument_needed", "").strip(),
            "genre": request.form.get("genre", "").strip(),
            "city": request.form.get("city", "").strip(),
            "state": request.form.get("state", "").strip(),
            "location_name": request.form.get("location_name", "").strip(),
            "paid_status": request.form.get("paid_status", "").strip(),
            "compensation": request.form.get("compensation", "").strip(),
            "event_date": request.form.get("event_date", "").strip(),
            "application_deadline": request.form.get("application_deadline", "").strip(),
            "contact_method": request.form.get("contact_method", "").strip(),
            "application_url": request.form.get("application_url", "").strip(),
        }
        if not fields["title"] or not fields["description"]:
            flash("Title and description are required.")
            return redirect(url_for("post_opportunity"))
        if fields["application_url"] and not valid_media_url(fields["application_url"]):
            flash("Use a full application link that starts with http:// or https://.")
            return redirect(url_for("post_opportunity"))
        opportunity_id = create_opportunity(user.id, fields)
        flash("Opportunity posted.")
        return redirect(ftb_opportunity_url(opportunity_id))
    return render_template("opportunity_form.html", user=user)


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


@app.route("/admin/import-opportunities", methods=["POST"])
@admin_required
def admin_import_opportunities():
    totals = import_live_opportunities()
    imported = sum(totals.values())
    flash(f"Imported {imported} opportunity records.")
    return redirect(url_for("admin_dashboard"))


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


@app.route("/admin/media-status")
@admin_required
def admin_media_status():
    owner_email = (FOUNDER_PROFILES[0].get("email") or ADMIN_EMAIL).lower()

    def upload_exists(folder, filename):
        if not filename:
            return False
        return (folder / filename).exists()

    with get_db() as conn:
        owner = conn.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)",
            (owner_email,),
        ).fetchone()
        owner_profile = row_to_profile(owner) if owner else None
        owner_perfs = []
        if owner:
            rows = conn.execute(
                """
                SELECT *
                FROM performances
                WHERE profile_id = ?
                ORDER BY datetime(created_at) DESC, id DESC
                """,
                (owner["id"],),
            ).fetchall()
            for row in rows:
                owner_perfs.append({
                    "id": row["id"],
                    "title": row["title"],
                    "media_type": row["media_type"],
                    "created_at": row["created_at"],
                    "external_url": row["external_url"],
                    "video_filename": row["video_filename"],
                    "video_file_exists": upload_exists(VIDEO_DIR, row["video_filename"]),
                    "audio_filename": row["audio_filename"],
                    "audio_file_exists": upload_exists(AUDIO_DIR, row["audio_filename"]),
                    "image_filename": row["image_filename"],
                    "image_file_exists": upload_exists(PHOTO_DIR, row["image_filename"]),
                    "thumb_filename": row["thumb_filename"],
                    "thumb_file_exists": upload_exists(PHOTO_DIR, row["thumb_filename"]),
                    "is_featured": bool(row["is_featured"]),
                })

        report = {
            "app": "Find The Beat",
            "database_path": str(DB_PATH),
            "database_exists": DB_PATH.exists(),
            "upload_dir": str(UPLOAD_DIR),
            "upload_dir_exists": UPLOAD_DIR.exists(),
            "sso_shared_secret_present": bool(SSO_SHARED_SECRET),
            "sso_shared_secret_fingerprint": hashlib.sha256(SSO_SHARED_SECRET.encode("utf-8")).hexdigest()[:12],
            "video_dir": str(VIDEO_DIR),
            "audio_dir": str(AUDIO_DIR),
            "photo_dir": str(PHOTO_DIR),
            "founder_email": owner_email,
            "founder_user_exists": bool(owner),
            "founder_profile_completion": profile_completion(owner_profile)["percent"] if owner_profile else 0,
            "founder_performance_count": len(owner_perfs),
            "founder_performances": owner_perfs,
            "total_users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "total_profiles": conn.execute("SELECT COUNT(*) FROM music_profiles").fetchone()[0],
            "total_performances": conn.execute("SELECT COUNT(*) FROM performances").fetchone()[0],
        }
    return jsonify(report)


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


@app.route("/profiles/<int:profile_id>/follow", methods=["POST"])
@login_required
def follow_profile(profile_id):
    user = current_user()
    if not get_profile(profile_id):
        flash("Profile not found.")
        return redirect(url_for("profiles"))
    if profile_id == user.id:
        flash("Your own profile is already in your mix.")
        return redirect(url_for("profile_detail", profile_id=profile_id))
    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM profile_follows WHERE follower_id = ? AND followed_id = ?",
            (user.id, profile_id),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM profile_follows WHERE follower_id = ? AND followed_id = ?",
                (user.id, profile_id),
            )
            flash("Artist removed from your following list.")
        else:
            conn.execute(
                "INSERT OR IGNORE INTO profile_follows (follower_id, followed_id) VALUES (?, ?)",
                (user.id, profile_id),
            )
            flash("Artist added to your following list.")
    return redirect(url_for("profile_detail", profile_id=profile_id))


@app.route("/profiles/<int:profile_id>")
def profile_detail(profile_id):
    profile = get_profile(profile_id)
    if not profile:
        flash("Profile not found.")
        return redirect(url_for("profiles"))
    perfs = get_performances(profile_id=profile.id)
    followers, following = profile_follow_counts(profile.id)
    user = current_user()
    profile_stats = {
        "performances": len(perfs),
        "likes": sum(perf.likes for perf in perfs),
        "comments": 0,
        "followers": followers,
        "following": following,
        "bookings": 0,
        "featured": sum(1 for perf in perfs if perf.is_featured),
    }
    return render_template(
        "profile_detail.html",
        profile=profile,
        perfs=perfs,
        profile_stats=profile_stats,
        showcase_items=get_showcase_tiles(limit=12, profile_id=profile.id),
        user=user,
        is_following=is_following_profile(user.id, profile.id) if user else False,
    )


@app.route("/users/<int:user_id>")
def user_detail(user_id):
    return profile_detail(user_id)


@app.route("/profile/<username>")
def profile_by_username(username):
    normalized = username_slug(username)
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE lower(username) = lower(?)",
            (normalized,),
        ).fetchone()
    if not row:
        flash("Profile not found.")
        return redirect(url_for("profiles"))
    return profile_detail(row["id"])


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
@require_profile_action
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
    next_target = safe_redirect_target(request.values.get("next", ""))
    if next_target:
        session["post_login_redirect"] = next_target
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not row or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        post_login_redirect = safe_redirect_target(session.get("post_login_redirect"))
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


@app.route("/sso/login")
def sso_login():
    next_path = request.args.get("next") or "/profile"
    query = urlencode({"app": "find-the-beat", "next": next_path})
    log_sso_debug("login_redirect", callback_url=f"{request.url_root.rstrip('/')}/sso/consume")
    return redirect(f"{BRENT_SSO_URL}?{query}")


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


@app.route("/sso/callback")
@app.route("/sso/consume")
def sso_consume():
    log_sso_debug("consume", callback_url=f"{request.url_root.rstrip('/')}/sso/consume")
    token = request.args.get("token", "")
    payload, error = verify_sso_token(token)
    if not payload:
        app.logger.warning(
            "Brent SSO token rejected: %s details=%s",
            error,
            json.dumps(sso_failure_details(error, token), sort_keys=True),
        )
        if error == "expired":
            flash("That Brent & Co sign-in link expired. Please sign in again.")
        elif error == "bad_signature":
            flash("Brent & Co sign-in could not be verified. The SSO secret needs to match on Brent & Co and Find The Beat.")
        elif error == "invalid_issuer":
            flash("That Brent & Co sign-in link came from an unrecognized issuer. Please sign in again.")
        else:
            flash("That Brent & Co sign-in link was invalid. Please sign in again.")
        return redirect(url_for("login"))
    if payload.get("aud") != "find-the-beat":
        app.logger.warning(
            "Brent SSO token audience mismatch: %s details=%s",
            payload.get("aud"),
            json.dumps(sso_failure_details("invalid_audience", token), sort_keys=True),
        )
        flash("That Brent & Co sign-in link was made for another app. Please sign in again.")
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
        perfs = get_performances(profile_id=user.id) if user else []
    except sqlite3.OperationalError as exc:
        app.logger.exception("Profile load failed; retrying after schema init")
        init_db()
        user = current_user()
        completion = profile_completion(user)
        unread = unread_message_count(user.id) if user else 0
        perfs = get_performances(profile_id=user.id) if user else []
        flash("Profile data was refreshed.")
    except Exception as exc:
        app.logger.exception("Profile load failed")
        user = current_user()
        completion = {"percent": 0, "items": []}
        unread = 0
        perfs = []
        flash("We had trouble loading part of your profile, but your account is safe.")
    followers, following = profile_follow_counts(user.id) if user else (0, 0)
    profile_stats = {
        "performances": len(perfs),
        "likes": sum(perf.likes for perf in perfs),
        "comments": 0,
        "followers": followers,
        "following": following,
        "bookings": 0,
        "featured": sum(1 for perf in perfs if perf.is_featured),
    }
    return render_template(
        "profile.html",
        user=user,
        completion=completion,
        unread_count=unread,
        perfs=perfs,
        profile_stats=profile_stats,
    )


@app.route("/profile/edit", methods=["GET", "POST"])
@app.route("/profiles/<int:profile_id>/edit", methods=["GET", "POST"])
@login_required
def edit_profile(profile_id=None):
    user = current_user()
    next_target = safe_redirect_target(request.values.get("next", ""))
    if next_target:
        session["post_profile_redirect"] = next_target
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
        return redirect(safe_redirect_target(session.pop("post_profile_redirect", "")) or url_for("profile"))

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
@require_profile_action
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


@app.route("/messages")
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
seed_community_content()
seed_founder_profile()
if FTB_AUTO_IMPORT_GIGS:
    import_live_opportunities()
backfill_record_coordinates()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5001")))
