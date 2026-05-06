import os
import secrets
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
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
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = INSTANCE_DIR / "find_the_beat_v2.db"

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(24))
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def ensure_dirs():
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_db():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn, table_name, column_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def add_column_if_missing(conn, table_name, column_name, column_type):
    if not column_exists(conn, table_name, column_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def init_db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,

            display_name TEXT DEFAULT '',
            role TEXT DEFAULT '',
            genre TEXT DEFAULT '',
            city TEXT DEFAULT '',
            bio TEXT DEFAULT '',

            tags_csv TEXT DEFAULT '',
            instrument TEXT DEFAULT '',
            services_csv TEXT DEFAULT '',

            profile_pic TEXT DEFAULT '',
            profile_video TEXT DEFAULT '',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


@app.before_request
def startup():
    init_db()


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_upload(file_storage, allowed_extensions):
    if not file_storage or not file_storage.filename:
        return ""

    if not allowed_file(file_storage.filename, allowed_extensions):
        raise ValueError("Please upload a valid file type.")

    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower()
    filename = f"{secrets.token_hex(10)}.{ext}"
    file_storage.save(UPLOAD_DIR / filename)
    return filename

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    genre = request.args.get("genre", "").strip()
    city = request.args.get("city", "").strip()

    sql = "SELECT * FROM users WHERE 1=1"
    params = []

    if q:
        like = f"%{q}%"
        sql += """
            AND (
                display_name LIKE ?
                OR role LIKE ?
                OR genre LIKE ?
                OR city LIKE ?
                OR bio LIKE ?
                OR tags_csv LIKE ?
                OR instrument LIKE ?
                OR services_csv LIKE ?
            )
        """
        params.extend([like, like, like, like, like, like, like, like])

    if role:
        sql += " AND role LIKE ?"
        params.append(f"%{role}%")

    if genre:
        sql += " AND genre LIKE ?"
        params.append(f"%{genre}%")

    if city:
        sql += " AND city LIKE ?"
        params.append(f"%{city}%")

    sql += " ORDER BY id DESC"

    with get_db() as conn:
        creators = conn.execute(sql, params).fetchall()

    return render_template(
        "index.html",
        creators=creators,
        q=q,
        role_filter=role,
        genre_filter=genre,
        city_filter=city,
        user=current_user(),
    )


@app.route("/search")
def search():
    return home()


@app.route("/profiles")
def profiles():
    return home()


@app.route("/performances")
def performances():
    return render_template("performances.html",user=current_user())


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip()

        role = request.form.get("role", "").strip()
        genre = request.form.get("genre", "").strip()
        city = request.form.get("city", "").strip()
        bio = request.form.get("bio", "").strip()
        tags_csv = request.form.get("tags_csv", "").strip()
        instrument = request.form.get("instrument", "").strip()
        services_csv = request.form.get("services_csv", "").strip()

        if not email or not password or not display_name:
            flash("Display name, email, and password are required.")
            return redirect(url_for("signup"))

        profile_pic = ""
        file_storage = request.files.get("profile_pic")
        if file_storage and file_storage.filename:
            try:
                profile_pic = save_profile_pic(file_storage)
            except ValueError as error:
                flash(str(error))
                return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)

        try:
            with get_db() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (
                        email,
                        password_hash,
                        display_name,
                        role,
                        genre,
                        city,
                        bio,
                        tags_csv,
                        instrument,
                        services_csv,
                        profile_pic,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        email,
                        password_hash,
                        display_name,
                        role,
                        genre,
                        city,
                        bio,
                        tags_csv,
                        instrument,
                        services_csv,
                        profile_pic,
                        now_utc(),
                    ),
                )
                conn.commit()
                session["user_id"] = cursor.lastrowid

        except sqlite3.IntegrityError:
            flash("That email already has a profile. Try logging in.")
            return redirect(url_for("login"))

        return redirect(url_for("profile"))

    return render_template("signup.html", user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        return redirect(url_for("profile"))

    return render_template("login.html", user=current_user())


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    return render_template("profile.html", user=user)


@app.route("/u/<int:user_id>")
def user_detail(user_id):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        flash("Profile not found.")
        return redirect(url_for("home"))

    return render_template("profile.html", user=user, viewer=current_user())


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = current_user()

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        role = request.form.get("role", "").strip()
        genre = request.form.get("genre", "").strip()
        city = request.form.get("city", "").strip()
        bio = request.form.get("bio", "").strip()
        tags_csv = request.form.get("tags_csv", "").strip()
        instrument = request.form.get("instrument", "").strip()
        services_csv = request.form.get("services_csv", "").strip()
        profile_pic = user["profile_pic"] if "profile_pic" in user.keys() else ""
        profile_video = user["profile_video"] if "profile_video" in user.keys() else""
        if not display_name:
            flash("Display name is required.")
            return redirect(url_for("edit_profile"))
        # --- PROFILE PIC ---
        file_storage = request.files.get("profile_pic")
        if file_storage and file_storage.filename:
            try:
                profile_pic = save_upload(file_storage, ALLOWED_IMAGE_EXTENSIONS)
            except ValueError as error:
                flash(str(error))
                return redirect(url_for("edit_profile"))

        # --- PROFILE VIDEO ---
        video_storage = request.files.get("profile_video")
        if video_storage and video_storage.filename:
            try:
                profile_video = save_upload(video_storage, ALLOWED_VIDEO_EXTENSIONS)
            except ValueError:
                flash("Please upload a valid video file: mp4, mov, or webm.")
                return redirect(url_for("edit_profile"))
                UPDATE users
                SET display_name = ?,
                    role = ?,
                    genre = ?,
                    city = ?,
                    bio = ?,
                    tags_csv = ?,
                    instrument = ?,
                    services_csv = ?,
                    profile_pic = ?
                    profile_video = ?
                WHERE id = ?
                """,
                (
                    display_name,
                    role,
                    genre,
                    city,
                    bio,
                    tags_csv,
                    instrument,
                    services_csv,
                    profile_pic,
                    profile_video,
                    user["id"],
                ),
            )
            conn.commit()

        flash("Profile updated.")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", user=user)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/health")
def health():
    return {"ok": True}, 200


if __name__ == "__main__":
    ensure_dirs()
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
