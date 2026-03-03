import os
import secrets
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash, send_from_directory
)
from werkzeug.utils import secure_filename

from extensions import db
from models import Profile, Performance, Message

BASE_DIR = Path(__file__).resolve().parent

ALLOWED_IMG = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO = {"mp4", "mov", "m4v", "webm"}


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # DB in instance/
    instance_dir = BASE_DIR / "instance"
    instance_dir.mkdir(exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{instance_dir / 'find_the_beat.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Upload folders
    app.config["UPLOAD_PHOTOS"] = str(BASE_DIR / "static" / "uploads" / "photos")
    app.config["UPLOAD_VIDEOS"] = str(BASE_DIR / "static" / "uploads" / "videos")
    os.makedirs(app.config["UPLOAD_PHOTOS"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_VIDEOS"], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # ----------------------------
    # Helpers
    # ----------------------------
    def _ext_ok(filename: str, allowed: set[str]) -> bool:
        if not filename or "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in allowed

    def _save_upload(file_storage, folder: str) -> str:
        original = secure_filename(file_storage.filename)
        ext = original.rsplit(".", 1)[1].lower()
        stored = f"{secrets.token_hex(16)}.{ext}"
        file_storage.save(os.path.join(folder, stored))
        return stored

    # ----------------------------
    # Routes (ENDPOINT NAMES MATTER)
    # ----------------------------
    @app.get("/")
    def home():
        return render_template("home.html")

    @app.get("/search")
    def search():
        # placeholder search page (prevents BuildError)
        q = request.args.get("q", "").strip()
        results = []
        if q:
            results = Profile.query.filter(Profile.display_name.ilike(f"%{q}%")).all()
        return render_template("search.html", q=q, results=results)

    @app.get("/showcases")
    def showcases():
        performances = Performance.query.order_by(Performance.created_at.desc()).all()
        return render_template("showcases.html", performances=performances)

    # ---------- Profiles ----------
    @app.get("/profiles")
    def profiles():
        items = Profile.query.order_by(Profile.created_at.desc()).all()
        return render_template("profiles.html", items=items)

    @app.route("/profiles/new", methods=["GET", "POST"])
    def new_profile():
        if request.method == "POST":
            display_name = request.form.get("display_name", "").strip()
            role = request.form.get("role", "artist").strip()
            bio = request.form.get("bio", "").strip()

            if not display_name:
                flash("Display name is required.")
                return redirect(url_for("new_profile"))

            photo = request.files.get("photo")
            photo_filename = None
            if photo and photo.filename:
                if not _ext_ok(photo.filename, ALLOWED_IMG):
                    flash("Photo must be jpg/jpeg/png/webp.")
                    return redirect(url_for("new_profile"))
                photo_filename = _save_upload(photo, app.config["UPLOAD_PHOTOS"])

            p = Profile(display_name=display_name, role=role, bio=bio, photo_filename=photo_filename)
            db.session.add(p)
            db.session.commit()
            flash("Profile created!")
            return redirect(url_for("profiles"))

        return render_template("new_profile.html")

    @app.get("/profiles/<int:profile_id>")
    def profile_detail(profile_id):
        p = Profile.query.get_or_404(profile_id)
        perf = Performance.query.filter_by(profile_id=p.id).order_by(Performance.created_at.desc()).all()
        return render_template("profile_detail.html", p=p, performances=perf)

    # ---------- Performances ----------
    @app.get("/performances")
    def performances():
        performances = Performance.query.order_by(Performance.created_at.desc()).all()
        profiles = Profile.query.order_by(Profile.display_name.asc()).all()
        return render_template("performances.html", performances=performances, profiles=profiles)

    @app.route("/upload_performance", methods=["GET", "POST"])
    def upload_performance():
        profiles = Profile.query.order_by(Profile.display_name.asc()).all()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            profile_id = request.form.get("profile_id")

            if not title:
                flash("Title is required.")
                return redirect(url_for("upload_performance"))
            if not profile_id:
                flash("Choose a profile.")
                return redirect(url_for("upload_performance"))

            video = request.files.get("video")
            thumb = request.files.get("thumb")

            video_filename = None
            thumb_filename = None

            if video and video.filename:
                if not _ext_ok(video.filename, ALLOWED_VIDEO):
                    flash("Video must be mp4/mov/m4v/webm.")
                    return redirect(url_for("upload_performance"))
                video_filename = _save_upload(video, app.config["UPLOAD_VIDEOS"])

            if thumb and thumb.filename:
                if not _ext_ok(thumb.filename, ALLOWED_IMG):
                    flash("Thumbnail must be jpg/jpeg/png/webp.")
                    return redirect(url_for("upload_performance"))
                thumb_filename = _save_upload(thumb, app.config["UPLOAD_PHOTOS"])

            perf = Performance(
                title=title,
                description=description,
                profile_id=int(profile_id),
                video_filename=video_filename,
                thumb_filename=thumb_filename,
            )
            db.session.add(perf)
            db.session.commit()
            flash("Performance uploaded!")
            return redirect(url_for("showcases"))

        return render_template("upload_performance.html", profiles=profiles)

    # ---------- Inbox ----------
    @app.get("/inbox")
    def inbox():
        # simple: show all messages newest first
        messages = Message.query.order_by(Message.created_at.desc()).all()
        profiles = {p.id: p for p in Profile.query.all()}
        return render_template("inbox.html", messages=messages, profiles=profiles)

    @app.route("/messages/new", methods=["GET", "POST"])
    def new_message():
        profiles = Profile.query.order_by(Profile.display_name.asc()).all()

        if request.method == "POST":
            sender_id = request.form.get("sender_id")
            recipient_id = request.form.get("recipient_id")
            subject = request.form.get("subject", "").strip()
            body = request.form.get("body", "").strip()

            if not sender_id or not recipient_id:
                flash("Pick sender and recipient.")
                return redirect(url_for("new_message"))
            if not body:
                flash("Message body can’t be empty.")
                return redirect(url_for("new_message"))

            m = Message(
                sender_id=int(sender_id),
                recipient_id=int(recipient_id),
                subject=subject,
                body=body,
                created_at=datetime.utcnow(),
            )
            db.session.add(m)
            db.session.commit()
            flash("Message sent!")
            return redirect(url_for("inbox"))

        return render_template("new_message.html", profiles=profiles)

    # ---------- Serve uploads ----------
    @app.get("/uploads/photos/<path:filename>")
    def uploaded_photo(filename):
        return send_from_directory(app.config["UPLOAD_PHOTOS"], filename)

    @app.get("/uploads/videos/<path:filename>")
    def uploaded_video(filename):
        return send_from_directory(app.config["UPLOAD_VIDEOS"], filename)

    return app


# ✅ This is what Flask CLI looks for by default
app = create_app()
