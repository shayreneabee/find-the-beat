import os
import secrets
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    session,
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from models import User, Profile, Performance, Message

BASE_DIR = Path(__file__).resolve().parent

ALLOWED_IMG = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO = {"mp4", "mov", "m4v", "webm"}


def _ext_ok(filename: str, allowed: set[str]) -> bool:
    return bool(filename) and "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def _save_upload(file_storage, folder: str) -> str:
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower()
    stored = f"{secrets.token_hex(16)}.{ext}"
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, stored))
    return stored


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///find_the_beat_v2.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["UPLOAD_PHOTOS"] = str(BASE_DIR / "static" / "uploads" / "photos")
    app.config["UPLOAD_VIDEOS"] = str(BASE_DIR / "static" / "uploads" / "videos")

    os.makedirs(app.config["UPLOAD_PHOTOS"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_VIDEOS"], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return User.query.get(user_id)

    def login_required(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in first.")
                return redirect(url_for("login"))
            return view_func(*args, **kwargs)
        return wrapped

    @app.context_processor
    def inject_user():
        return {
            "current_user": current_user()
        }

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "GET":
            return render_template("signup.html")

        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("signup"))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("That email is already registered.")
            return redirect(url_for("signup"))

        user = User(
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        flash("Account created!")
        return redirect(url_for("dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html")

        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        flash("Welcome back!")
        return redirect(url_for("dashboard"))

    @app.get("/logout")
    def logout():
        session.clear()
        flash("Logged out.")
        return redirect(url_for("home"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        my_profiles = Profile.query.filter_by(user_id=user.id).order_by(Profile.created_at.desc()).all()

        profile_ids = [p.id for p in my_profiles]
        my_performances = []
        if profile_ids:
            my_performances = (
                Performance.query
                .filter(Performance.profile_id.in_(profile_ids))
                .order_by(Performance.created_at.desc())
                .all()
            )

        return render_template(
            "dashboard.html",
            my_profiles=my_profiles,
            my_performances=my_performances,
        )

    @app.get("/my_profile")
    @login_required
    def my_profile():
        user = current_user()
        profile = Profile.query.filter_by(user_id=user.id).order_by(Profile.created_at.desc()).first()

        if not profile:
            flash("Create your profile first.")
            return redirect(url_for("create_profile"))

        perfs = (
            Performance.query
            .filter_by(profile_id=profile.id)
            .order_by(Performance.created_at.desc())
            .all()
        )

        return render_template("my_profile.html", profile=profile, perfs=perfs)

    @app.get("/search")
    def search():
        q = request.args.get("q", "").strip()
        role = request.args.get("role", "").strip()

        query = Profile.query

        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    Profile.display_name.ilike(like),
                    Profile.bio.ilike(like),
                    Profile.role.ilike(like),
                )
            )

        if role:
            query = query.filter(Profile.role.ilike(f"%{role}%"))

        results = query.order_by(Profile.created_at.desc()).all()
        return render_template("search.html", q=q, role=role, results=results)

    @app.get("/profiles")
    def profiles():
        items = Profile.query.order_by(Profile.created_at.desc()).all()
        return render_template("profiles.html", profiles=items)

    @app.get("/profile/<int:profile_id>")
    def profile_detail(profile_id):
        profile = Profile.query.get_or_404(profile_id)
        perfs = (
            Performance.query
            .filter_by(profile_id=profile.id)
            .order_by(Performance.created_at.desc())
            .all()
        )
        return render_template("profile_detail.html", profile=profile, perfs=perfs)

    @app.route("/create_profile", methods=["GET", "POST"])
    @login_required
    def create_profile():
        user = current_user()

        if request.method == "GET":
            return render_template("create_profile.html")

        display_name = request.form["display_name"].strip()
        role = request.form["role"].strip()
        bio = request.form["bio"].strip()

        photo = request.files.get("photo")
        photo_filename = None

        if photo and photo.filename:
            if _ext_ok(photo.filename, ALLOWED_IMG):
                photo_filename = _save_upload(photo, app.config["UPLOAD_PHOTOS"])
            else:
                flash("Photo must be jpg, jpeg, png, or webp.")
                return redirect(url_for("create_profile"))

        if not display_name or not role:
            flash("Display name and role are required.")
            return redirect(url_for("create_profile"))

        profile = Profile(
            display_name=display_name,
            role=role,
            bio=bio,
            photo_filename=photo_filename,
            user_id=user.id,
        )

        db.session.add(profile)
        db.session.commit()

        flash("Profile created!")
        return redirect(url_for("my_profile"))

    @app.route("/edit_profile/<int:profile_id>", methods=["GET", "POST"])
    @login_required
    def edit_profile(profile_id):
        user = current_user()
        profile = Profile.query.get_or_404(profile_id)

        if profile.user_id != user.id:
            flash("You can only edit your own profile.")
            return redirect(url_for("dashboard"))

        if request.method == "GET":
            return render_template("edit_profile.html", profile=profile)

        display_name = request.form["display_name"].strip()
        role = request.form["role"].strip()
        bio = request.form["bio"].strip()

        if not display_name or not role:
            flash("Display name and role are required.")
            return redirect(url_for("edit_profile", profile_id=profile.id))

        profile.display_name = display_name
        profile.role = role
        profile.bio = bio

        photo = request.files.get("photo")
        if photo and photo.filename:
            if _ext_ok(photo.filename, ALLOWED_IMG):
                profile.photo_filename = _save_upload(photo, app.config["UPLOAD_PHOTOS"])
            else:
                flash("Photo must be jpg, jpeg, png, or webp.")
                return redirect(url_for("edit_profile", profile_id=profile.id))

        db.session.commit()

        flash("Profile updated!")
        return redirect(url_for("my_profile"))

    @app.get("/performances")
    def performances():
        items = Performance.query.order_by(Performance.created_at.desc()).all()
        return render_template("performances.html", performances=items)

    @app.get("/performance/<int:perf_id>")
    def performance_detail(perf_id):
        perf = Performance.query.get_or_404(perf_id)
        return render_template("performance_detail.html", perf=perf)

    @app.route("/upload_performance", methods=["GET", "POST"])
    @login_required
    def upload_performance():
        user = current_user()
        profiles = Profile.query.filter_by(user_id=user.id).order_by(Profile.display_name.asc()).all()

        if request.method == "GET":
            return render_template("upload_performance.html", profiles=profiles)

        title = request.form["title"].strip()
        description = request.form["description"].strip()
        profile_id = request.form["profile_id"].strip()

        if not title or not profile_id:
            flash("Title and artist are required.")
            return redirect(url_for("upload_performance"))

        try:
            profile_id = int(profile_id)
        except ValueError:
            flash("Choose a valid artist.")
            return redirect(url_for("upload_performance"))

        profile = Profile.query.get_or_404(profile_id)
        if profile.user_id != user.id:
            flash("You can only upload to your own profile.")
            return redirect(url_for("dashboard"))

        video = request.files.get("video")
        thumb = request.files.get("thumb")

        video_filename = None
        thumb_filename = None

        if video and video.filename:
            if _ext_ok(video.filename, ALLOWED_VIDEO):
                video_filename = _save_upload(video, app.config["UPLOAD_VIDEOS"])
            else:
                flash("Video must be mp4, mov, m4v, or webm.")
                return redirect(url_for("upload_performance"))

        if thumb and thumb.filename:
            if _ext_ok(thumb.filename, ALLOWED_IMG):
                thumb_filename = _save_upload(thumb, app.config["UPLOAD_PHOTOS"])
            else:
                flash("Thumbnail must be jpg, jpeg, png, or webp.")
                return redirect(url_for("upload_performance"))

        perf = Performance(
            title=title,
            description=description,
            profile_id=profile_id,
            video_filename=video_filename,
            thumb_filename=thumb_filename,
            created_at=datetime.utcnow(),
        )

        db.session.add(perf)
        db.session.commit()

        flash("Performance uploaded!")
        return redirect(url_for("dashboard"))

    @app.get("/inbox")
    def inbox():
        msgs = Message.query.order_by(Message.created_at.desc()).all()
        people = Profile.query.order_by(Profile.created_at.desc()).all()
        return render_template("inbox.html", msgs=msgs, profiles=people)

    @app.route("/new_message", methods=["GET", "POST"])
    def new_message():
        if request.method == "GET":
            people = Profile.query.order_by(Profile.created_at.desc()).all()
            return render_template("new_message.html", profiles=people)

        sender_id = int(request.form["sender_id"])
        recipient_id = int(request.form["recipient_id"])
        body = request.form["body"].strip()

        if not body:
            flash("Message can't be empty.")
            return redirect(url_for("new_message"))

        msg = Message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            body=body,
            created_at=datetime.utcnow(),
        )
        db.session.add(msg)
        db.session.commit()

        return redirect(url_for("thread", me=sender_id, other=recipient_id))

    @app.post("/delete_message/<int:message_id>")
    def delete_message(message_id):
        msg = Message.query.get_or_404(message_id)
        db.session.delete(msg)
        db.session.commit()
        flash("Message deleted.")
        return redirect(url_for("inbox"))

    @app.get("/thread")
    def thread():
        me = int(request.args.get("me"))
        other = int(request.args.get("other"))

        msgs = (
            Message.query
            .filter(
                db.or_(
                    db.and_(Message.sender_id == me, Message.recipient_id == other),
                    db.and_(Message.sender_id == other, Message.recipient_id == me),
                )
            )
            .order_by(Message.created_at.asc())
            .all()
        )

        me_profile = Profile.query.get_or_404(me)
        other_profile = Profile.query.get_or_404(other)

        return render_template(
            "thread.html",
            msgs=msgs,
            me=me_profile,
            other=other_profile,
        )

    @app.get("/uploads/photos/<path:filename>")
    def uploaded_photo(filename):
        return send_from_directory(app.config["UPLOAD_PHOTOS"], filename)

    @app.get("/uploads/videos/<path:filename>")
    def uploaded_video(filename):
        return send_from_directory(app.config["UPLOAD_VIDEOS"], filename)

    return app


app = create_app()
