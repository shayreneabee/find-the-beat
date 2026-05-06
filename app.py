import os
import sqlite3
import secrets
from pathlib import Path
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_from_directory,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from werkzeug.utils import secure_filename


# ---------------------------------------------------
# APP CONFIG
# ---------------------------------------------------

app = Flask(__name__)
app.secret_key = "super-secret-key"

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

INSTANCE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

DB_PATH = INSTANCE_DIR / "find_the_beat_v2.db"

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


# ---------------------------------------------------
# DATABASE
# ---------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

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
            profile_video TEXT DEFAULT ''
        )
        """
    )

    conn.commit()
    conn.close()


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def allowed_file(filename, allowed_extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )


def save_upload(file_storage, allowed_extensions):
    if not file_storage or not file_storage.filename:
        return ""

    if not allowed_file(file_storage.filename, allowed_extensions):
        raise ValueError("Invalid file type.")

    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower()

    filename = f"{secrets.token_hex(12)}.{ext}"

    file_storage.save(UPLOAD_DIR / filename)

    return filename


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return user


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


# ---------------------------------------------------
# ROUTES
# ---------------------------------------------------

@app.route("/")
def home():
    return render_template(
        "index.html",
        user=current_user(),
    )

@app.route("/search")
def search():
    return redirect(url_for("profiles"))

@app.route("/profiles")
def profiles():
    conn = get_db()

    users = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "profiles.html",
        users=users,
        user=current_user(),
    )


@app.route("/performances")
def performances():
    return render_template(
        "performances.html",
        user=current_user(),
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip()

        if not email or not password or not display_name:
            flash("All fields are required.")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)

        conn = get_db()

        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if existing:
            conn.close()
            flash("Account already exists.")
            return redirect(url_for("signup"))

        cursor = conn.execute(
            """
            INSERT INTO users (
                email,
                password_hash,
                display_name
            )
            VALUES (?, ?, ?)
            """,
            (
                email,
                password_hash,
                display_name,
            ),
        )

        conn.commit()

        session["user_id"] = cursor.lastrowid

        conn.close()

        return redirect(url_for("profile"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        conn.close()

        if not user:
            flash("Invalid credentials.")
            return redirect(url_for("login"))

        if not check_password_hash(
            user["password_hash"],
            password,
        ):
            flash("Invalid credentials.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]

        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/profile")
@login_required
def profile():
    return render_template(
        "profile.html",
        user=current_user(),
    )


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():

    user = current_user()

    if request.method == "POST":

        display_name = request.form.get("display_name", "")
        role = request.form.get("role", "")
        genre = request.form.get("genre", "")
        city = request.form.get("city", "")
        bio = request.form.get("bio", "")
        tags_csv = request.form.get("tags_csv", "")
        instrument = request.form.get("instrument", "")
        services_csv = request.form.get("services_csv", "")

        profile_pic = user["profile_pic"]
        profile_video = user["profile_video"]

        # IMAGE
        image_file = request.files.get("profile_pic")

        if image_file and image_file.filename:
            try:
                profile_pic = save_upload(
                    image_file,
                    ALLOWED_IMAGE_EXTENSIONS,
                )
            except ValueError:
                flash("Invalid image file.")
                return redirect(url_for("edit_profile"))

        # VIDEO
        video_file = request.files.get("profile_video")

        if video_file and video_file.filename:
            try:
                profile_video = save_upload(
                    video_file,
                    ALLOWED_VIDEO_EXTENSIONS,
                )
            except ValueError:
                flash("Invalid video file.")
                return redirect(url_for("edit_profile"))

        conn = get_db()

        conn.execute(
            """
            UPDATE users
            SET
                display_name = ?,
                role = ?,
                genre = ?,
                city = ?,
                bio = ?,
                tags_csv = ?,
                instrument = ?,
                services_csv = ?,
                profile_pic = ?,
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
        conn.close()

        flash("Profile updated.")

        return redirect(url_for("profile"))

    return render_template(
        "edit_profile.html",
        user=user,
    )


@app.route("/profile/delete", methods=["POST"])
@login_required
def delete_profile():
    user = current_user()

    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()

    session.clear()
    flash("Your profile has been deleted.")
    return redirect(url_for("home"))


@app.route("/profile/delete-photo", methods=["POST"])
@login_required
def delete_profile_photo():
    user = current_user()

    conn = get_db()
    conn.execute(
        "UPDATE users SET profile_pic = '' WHERE id = ?",
        (user["id"],),
    )
    conn.commit()
    conn.close()

    flash("Profile picture removed.")
    return redirect(url_for("edit_profile"))


@app.route("/profile/delete-video", methods=["POST"])
@login_required
def delete_profile_video():
    user = current_user()

    conn = get_db()
    conn.execute(
        "UPDATE users SET profile_video = '' WHERE id = ?",
        (user["id"],),
    )
    conn.commit()
    conn.close()

    flash("Profile video removed.")
    return redirect(url_for("edit_profile"))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        UPLOAD_DIR,
        filename,
    )


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

if __name__ == "__main__":
    init_db()

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5001,
    )
