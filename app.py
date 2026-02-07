import os
import secrets
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# ---------------------------
# App + Config
# ---------------------------

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

PHOTOS_DIR = BASE_DIR / "static" / "uploads" / "photos"
VIDEOS_DIR = BASE_DIR / "static" / "uploads" / "videos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_PHOTO_EXTS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_VIDEO_EXTS = {"mp4", "mov", "webm"}

app = Flask(__name__)

# change later for prod; fine for local dev
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-" + secrets.token_hex(16))

# IMPORTANT: use ONE db. You already saw it's using instance/ftb.db
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{INSTANCE_DIR / 'ftb.db'}",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_PHOTOS_DIR"] = str(PHOTOS_DIR)
app.config["UPLOAD_VIDEOS_DIR"] = str(VIDEOS_DIR)

# Owner key (your “Wizard of Oz mode”)
# set this in your shell later: export FTB_OWNER_KEY="YOURSECRET"
app.config["OWNER_KEY"] = os.getenv("FTB_OWNER_KEY", "wizard")

db = SQLAlchemy(app)


# ---------------------------
# Models
# ---------------------------

class Profile(db.Model):
    __tablename__ = "profile"

    id = db.Column(db.Integer, primary_key=True)

    # basics
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=True)

    # “artist / musician / production / composer”
    role = db.Column(db.String(40), nullable=True)

    # extra bells
    instrument = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    # uploads (stored as filenames in /static/uploads/...)
    photo_filename = db.Column(db.String(255), nullable=True)
    video_filename = db.Column(db.String(255), nullable=True)

    # quick “login-ish” tag you can use later (we’ll build it out)
    owner_tag = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# Create tables if missing (DEV convenience)
with app.app_context():
    db.create_all()


# ---------------------------
# Helpers
# ---------------------------

def owner_key_ok() -> bool:
    """Owner actions allowed if ?key=... matches OWNER_KEY."""
    key = request.args.get("key", "")
    return bool(key) and secrets.compare_digest(key, app.config["OWNER_KEY"])


def allowed_file(filename: str, allowed_exts: set[str]) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_exts


def save_upload(file_storage, dest_dir: Path, allowed_exts: set[str]) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename, allowed_exts):
        return None

    # prevent collisions
    ext = filename.rsplit(".", 1)[1].lower()
    unique = f"{secrets.token_hex(8)}.{ext}"
    out_path = dest_dir / unique
    file_storage.save(out_path)
    return unique


# ---------------------------
# Routes
# ---------------------------
@app.route("/search")
def search():
    return render_template("ftb/search.html")

@app.route("/artists")
def artists():
    return render_template("ftb/artists.html")

@app.route("/musicians")
def musicians():
    return render_template("ftb/musicians.html")

@app.route("/production")
def production():
    return render_template("ftb/production.html")

@app.route("/composers")
def composers():
    return render_template("ftb/composers.html")

@app.route("/showcases")
def showcases():
    return render_template("ftb/showcases.html")

@app.get("/login")
def login():
    return render_template("login.html")

@app.get("/")
def home():
    # your templates/home.html should extend base.html
    return render_template("home.html")


# --- Showcase page (your mockups route) ---
@app.get("/showcase")
def showcase():
    # uses templates/showcase.html (you already have it)
    return render_template("showcase.html")


# --- Search (make BOTH endpoint names work) ---
def _search_view():
    # if you later build category search, we’ll expand here
    return render_template("ftb/search.html") if (BASE_DIR / "templates" / "ftb" / "search.html").exists() else render_template("home.html")


# Two endpoints for the same URL, so BOTH url_for('search') and url_for('ftb_search') can work


# --- List profiles ---
@app.get("/profiles")
def profiles():
    all_profiles = Profile.query.order_by(Profile.created_at.desc()).all()
    # IMPORTANT: your template must be templates/profiles.html
    return render_template("profiles.html", profiles=all_profiles)


# --- Create profile ---
@app.route("/profiles/new", methods=["GET", "POST"])
def new_profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        city = request.form.get("city", "").strip()
        role = request.form.get("role", "").strip()
        instrument = request.form.get("instrument", "").strip()
        bio = request.form.get("bio", "").strip()
        owner_tag = request.form.get("owner_tag", "").strip()

        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("new_profile"))

        # uploads
        photo = request.files.get("photo")
        video = request.files.get("video")

        photo_filename = save_upload(photo, PHOTOS_DIR, ALLOWED_PHOTO_EXTS)
        video_filename = save_upload(video, VIDEOS_DIR, ALLOWED_VIDEO_EXTS)

        p = Profile(
            name=name,
            city=city or None,
            role=role or None,
            instrument=instrument or None,
            bio=bio or None,
            owner_tag=owner_tag or None,
            photo_filename=photo_filename,
            video_filename=video_filename,
        )
        db.session.add(p)
        db.session.commit()

        flash("Profile created!", "success")
        return redirect(url_for("profile_detail", profile_id=p.id))

    return render_template("new_profile.html")


# --- Profile detail ---
@app.get("/profiles/<int:profile_id>")
def profile_detail(profile_id: int):
    p = Profile.query.get_or_404(profile_id)
    return render_template("profile.html", profile=p)


# --- Edit profile (and add video later) ---
@app.route("/profiles/<int:profile_id>/edit", methods=["GET", "POST"])
def edit_profile(profile_id: int):
    p = Profile.query.get_or_404(profile_id)

    # (optional) protect edit with owner key
    # if not owner_key_ok(): abort(403)

    if request.method == "POST":
        p.name = request.form.get("name", p.name).strip() or p.name
        p.city = request.form.get("city", "").strip() or None
        p.role = request.form.get("role", "").strip() or None
        p.instrument = request.form.get("instrument", "").strip() or None
        p.bio = request.form.get("bio", "").strip() or None
        p.owner_tag = request.form.get("owner_tag", "").strip() or None

        photo = request.files.get("photo")
        video = request.files.get("video")

        new_photo = save_upload(photo, PHOTOS_DIR, ALLOWED_PHOTO_EXTS)
        new_video = save_upload(video, VIDEOS_DIR, ALLOWED_VIDEO_EXTS)

        if new_photo:
            p.photo_filename = new_photo
        if new_video:
            p.video_filename = new_video

        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for("profile_detail", profile_id=p.id))

    return render_template("edit_profile.html", profile=p)


# --- Delete profile (owner key required) ---
@app.route("/profiles/<int:profile_id>/delete", methods=["GET", "POST"])
def delete_profile(profile_id: int):
    p = Profile.query.get_or_404(profile_id)

    if not owner_key_ok():
        abort(403)

    if request.method == "POST":
        db.session.delete(p)
        db.session.commit()
        flash("Profile deleted.", "success")
        return redirect(url_for("profiles"))

    return render_template("confirm_delete.html", profile=p)


# ---------------------------
# Error pages
# ---------------------------

@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

