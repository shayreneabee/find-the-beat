import os
import sqlite3
import secrets
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.getenv("INSTANCE_DIR", BASE_DIR / "instance"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "static" / "uploads"))
DB_PATH = Path(os.getenv("DATABASE_PATH", INSTANCE_DIR / "find_the_beat_v2.db"))

INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.secret_key = os.getenv("SECRET_KEY", "dev-find-the-beat-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "100")) * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "m4v", "webm"}
ROLE_OPTIONS = [
    ("artist", "Artist"),
    ("producer", "Producer"),
    ("musician", "Musician"),
    ("composer", "Composer"),
    ("engineer", "Engineer"),
    ("songwriter", "Songwriter"),
    ("dj", "DJ"),
    ("vocalist", "Vocalist"),
    ("manager", "Manager"),
]
ROLE_LABELS = dict(ROLE_OPTIONS)
ROLE_ALIASES = {
    "d.j.": "dj",
    "d.j": "dj",
    "disc jockey": "dj",
    "beat maker": "producer",
    "beatmaker": "producer",
    "production": "producer",
    "singer": "vocalist",
    "singer/songwriter": "songwriter",
    "song writer": "songwriter",
    "composer": "composer",
    "producer": "producer",
    "artist": "artist",
    "musician": "musician",
    "engineer": "engineer",
    "manager": "manager",
}


def utc_now():
    return datetime.utcnow().isoformat(timespec="seconds")


def normalize_role(value):
    role = (value or "").strip().lower()
    return ROLE_ALIASES.get(role, role)


def role_label(value):
    role = normalize_role(value)
    return ROLE_LABELS.get(role, role.title() if role else "")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_columns(conn, table, columns):
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


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
            state TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            tags_csv TEXT DEFAULT '',
            instrument TEXT DEFAULT '',
            services_csv TEXT DEFAULT '',
            profile_pic TEXT DEFAULT '',
            profile_video TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    ensure_columns(
        conn,
        "users",
        {
            "display_name": "TEXT DEFAULT ''",
            "role": "TEXT DEFAULT ''",
            "genre": "TEXT DEFAULT ''",
            "city": "TEXT DEFAULT ''",
            "state": "TEXT DEFAULT ''",
            "bio": "TEXT DEFAULT ''",
            "tags_csv": "TEXT DEFAULT ''",
            "instrument": "TEXT DEFAULT ''",
            "services_csv": "TEXT DEFAULT ''",
            "profile_pic": "TEXT DEFAULT ''",
            "profile_video": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        },
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS performances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            video_filename TEXT DEFAULT '',
            thumb_filename TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_upload(file_storage, allowed_extensions, subdir):
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_file(file_storage.filename, allowed_extensions):
        raise ValueError("Invalid file type.")

    upload_subdir = UPLOAD_DIR / subdir
    upload_subdir.mkdir(parents=True, exist_ok=True)
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower()
    filename = f"{subdir}/{secrets.token_hex(12)}.{ext}"
    file_storage.save(UPLOAD_DIR / filename)
    return filename


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user(user_id)


def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            flash("Please log in first.")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def profile_search_results(query="", role="", genre="", city="", tag=""):
    filters = []
    values = []
    if query:
        filters.append("(display_name LIKE ? OR bio LIKE ? OR email LIKE ? OR role LIKE ?)")
        values.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])
    if role:
        filters.append("LOWER(role) LIKE ?")
        values.append(f"%{normalize_role(role)}%")
    if genre:
        filters.append("genre LIKE ?")
        values.append(f"%{genre}%")
    if city:
        filters.append("(city LIKE ? OR state LIKE ?)")
        values.extend([f"%{city}%", f"%{city}%"])
    if tag:
        filters.append("(tags_csv LIKE ? OR services_csv LIKE ? OR instrument LIKE ?)")
        values.extend([f"%{tag}%", f"%{tag}%", f"%{tag}%"])

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    conn = get_db()
    users = conn.execute(
        f"""
        SELECT *
        FROM users
        {where}
        ORDER BY updated_at DESC, id DESC
        """,
        values,
    ).fetchall()
    conn.close()
    return users


def performances_for_user(user_id):
    conn = get_db()
    performances = conn.execute(
        """
        SELECT performances.*, users.display_name, users.role
        FROM performances
        JOIN users ON users.id = performances.user_id
        WHERE performances.user_id = ?
        ORDER BY performances.created_at DESC, performances.id DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return performances


def all_performances():
    conn = get_db()
    performances = conn.execute(
        """
        SELECT performances.*, users.display_name, users.role
        FROM performances
        JOIN users ON users.id = performances.user_id
        ORDER BY performances.created_at DESC, performances.id DESC
        """
    ).fetchall()
    conn.close()
    return performances


@app.context_processor
def inject_user():
    return {"user": current_user()}


@app.route("/")
def home():
    filters = {
        "query": request.args.get("q", "").strip(),
        "role": request.args.get("role", "").strip(),
        "genre": request.args.get("genre", "").strip(),
        "city": request.args.get("city", "").strip(),
        "tag": request.args.get("q", "").strip(),
    }
    return render_template(
        "index.html",
        creators=profile_search_results(**filters),
        q=filters["query"],
        role_filter=filters["role"],
        genre_filter=filters["genre"],
        city_filter=filters["city"],
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip()
        role = normalize_role(request.form.get("role", ""))
        genre = request.form.get("genre", "").strip()
        city = request.form.get("city", "").strip()
        bio = request.form.get("bio", "").strip()
        tags_csv = request.form.get("tags_csv", "").strip()
        instrument = request.form.get("instrument", "").strip()
        services_csv = request.form.get("services_csv", "").strip()

        if not email or not password or not display_name:
            flash("Email, password, and display name are required.")
            return redirect(url_for("signup"))

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("That account already exists. Try logging in.")
            return redirect(url_for("login"))

        profile_pic = ""
        try:
            image_file = request.files.get("profile_pic")
            if image_file and image_file.filename:
                profile_pic = save_upload(image_file, ALLOWED_IMAGE_EXTENSIONS, "photos")
        except ValueError as error:
            conn.close()
            flash(str(error))
            return redirect(url_for("signup"))

        cursor = conn.execute(
            """
            INSERT INTO users
                (email, password_hash, display_name, role, genre, city, bio,
                 tags_csv, instrument, services_csv, profile_pic, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email,
                generate_password_hash(password),
                display_name,
                role,
                genre,
                city,
                bio,
                tags_csv,
                instrument,
                services_csv,
                profile_pic,
                utc_now(),
                utc_now(),
            ),
        )
        conn.commit()
        session["user_id"] = cursor.lastrowid
        conn.close()
        flash("Welcome to Find the Beat. Build your profile next.")
        return redirect(url_for("edit_profile"))

    return render_template("signup.html", role_options=ROLE_OPTIONS)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid credentials.")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        next_url = request.args.get("next")
        return redirect(next_url or url_for("profile"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("home"))


@app.route("/profile")
@login_required
def profile():
    me = current_user()
    return render_template(
        "profile.html",
        profile=me,
        performances=performances_for_user(me["id"]),
        is_owner=True,
    )


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    me = current_user()
    if request.method == "POST":
        fields = {
            "display_name": request.form.get("display_name", "").strip(),
            "role": normalize_role(request.form.get("role", "")),
            "genre": request.form.get("genre", "").strip(),
            "city": request.form.get("city", "").strip(),
            "state": request.form.get("state", "").strip(),
            "bio": request.form.get("bio", "").strip(),
            "tags_csv": request.form.get("tags_csv", "").strip(),
            "instrument": request.form.get("instrument", "").strip(),
            "services_csv": request.form.get("services_csv", "").strip(),
        }
        if not fields["display_name"]:
            flash("Display name is required.")
            return redirect(url_for("edit_profile"))

        profile_pic = me["profile_pic"] or ""
        profile_video = me["profile_video"] or ""
        try:
            image_file = request.files.get("profile_pic")
            if image_file and image_file.filename:
                profile_pic = save_upload(image_file, ALLOWED_IMAGE_EXTENSIONS, "photos")
            video_file = request.files.get("profile_video")
            if video_file and video_file.filename:
                profile_video = save_upload(video_file, ALLOWED_VIDEO_EXTENSIONS, "videos")
        except ValueError as error:
            flash(str(error))
            return redirect(url_for("edit_profile"))

        conn = get_db()
        conn.execute(
            """
            UPDATE users
            SET display_name = ?, role = ?, genre = ?, city = ?, state = ?,
                bio = ?, tags_csv = ?, instrument = ?, services_csv = ?,
                profile_pic = ?, profile_video = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                fields["display_name"],
                fields["role"],
                fields["genre"],
                fields["city"],
                fields["state"],
                fields["bio"],
                fields["tags_csv"],
                fields["instrument"],
                fields["services_csv"],
                profile_pic,
                profile_video,
                utc_now(),
                me["id"],
            ),
        )
        conn.commit()
        conn.close()
        flash("Profile updated.")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", profile=me, role_options=ROLE_OPTIONS)


@app.route("/profiles")
def profiles():
    filters = {
        "q": request.args.get("q", "").strip(),
        "role": request.args.get("role", "").strip(),
        "genre": request.args.get("genre", "").strip(),
        "city": request.args.get("city", "").strip(),
        "tag": request.args.get("tag", "").strip(),
    }
    results = profile_search_results(
        query=filters["q"],
        role=filters["role"],
        genre=filters["genre"],
        city=filters["city"],
        tag=filters["tag"],
    )
    return render_template(
        "profiles.html",
        profiles=results,
        filters=filters,
        active_role_label=role_label(filters["role"]),
    )


@app.route("/search")
def search():
    return redirect(url_for("profiles", **request.args))


@app.route("/profiles/<int:user_id>")
@app.route("/users/<int:user_id>")
def public_profile(user_id):
    profile_user = get_user(user_id)
    if not profile_user:
        flash("Profile not found.")
        return redirect(url_for("profiles"))
    return render_template(
        "profile.html",
        profile=profile_user,
        performances=performances_for_user(user_id),
        is_owner=current_user() and current_user()["id"] == user_id,
    )


@app.route("/performances")
def performances():
    return render_template("performances.html", performances=all_performances())


@app.route("/performances/upload", methods=["GET", "POST"])
@app.route("/upload-performance", methods=["GET", "POST"])
@login_required
def upload_performance():
    me = current_user()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title:
            flash("Performance title is required.")
            return redirect(url_for("upload_performance"))

        try:
            video_filename = save_upload(
                request.files.get("video"),
                ALLOWED_VIDEO_EXTENSIONS,
                "videos",
            )
            thumb_filename = save_upload(
                request.files.get("thumb"),
                ALLOWED_IMAGE_EXTENSIONS,
                "photos",
            )
        except ValueError as error:
            flash(str(error))
            return redirect(url_for("upload_performance"))

        conn = get_db()
        conn.execute(
            """
            INSERT INTO performances
                (user_id, title, description, video_filename, thumb_filename, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (me["id"], title, description, video_filename, thumb_filename, utc_now()),
        )
        conn.commit()
        conn.close()
        flash("Performance uploaded.")
        return redirect(url_for("profile"))

    return render_template("upload_performance.html")


@app.route("/performances/<int:perf_id>")
def performance_detail(perf_id):
    conn = get_db()
    perf = conn.execute(
        """
        SELECT performances.*, users.display_name, users.role, users.id AS owner_id
        FROM performances
        JOIN users ON users.id = performances.user_id
        WHERE performances.id = ?
        """,
        (perf_id,),
    ).fetchone()
    conn.close()
    if not perf:
        flash("Performance not found.")
        return redirect(url_for("performances"))
    return render_template("performance_detail.html", perf=perf)


@app.route("/messages/new", methods=["GET", "POST"])
@app.route("/profiles/<int:recipient_id>/message", methods=["GET", "POST"])
@login_required
def new_message(recipient_id=None):
    me = current_user()
    recipient = get_user(recipient_id) if recipient_id else None
    if recipient_id and not recipient:
        flash("Recipient not found.")
        return redirect(url_for("profiles"))

    if request.method == "POST":
        target_id = recipient_id or request.form.get("recipient_id", type=int)
        body = request.form.get("body", "").strip()
        target = get_user(target_id)
        if not target or target["id"] == me["id"]:
            flash("Choose another user to message.")
            return redirect(url_for("profiles"))
        if not body:
            flash("Message body is required.")
            return redirect(url_for("new_message", recipient_id=target_id))

        conn = get_db()
        conn.execute(
            """
            INSERT INTO messages (sender_id, recipient_id, body, is_read, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (me["id"], target["id"], body, utc_now()),
        )
        conn.commit()
        conn.close()
        flash("Message sent.")
        return redirect(url_for("thread", other_id=target["id"]))

    recipients = profile_search_results()
    return render_template("new_message.html", recipient=recipient, recipients=recipients)


@app.route("/inbox")
@login_required
def inbox():
    me = current_user()
    conn = get_db()
    msgs = conn.execute(
        """
        SELECT messages.*, sender.display_name AS sender_name, recipient.display_name AS recipient_name
        FROM messages
        JOIN users sender ON sender.id = messages.sender_id
        JOIN users recipient ON recipient.id = messages.recipient_id
        WHERE messages.sender_id = ? OR messages.recipient_id = ?
        ORDER BY messages.created_at DESC, messages.id DESC
        """,
        (me["id"], me["id"]),
    ).fetchall()
    conn.close()
    return render_template("inbox.html", msgs=msgs)


@app.route("/thread/<int:other_id>", methods=["GET", "POST"])
@login_required
def thread(other_id):
    me = current_user()
    other = get_user(other_id)
    if not other:
        flash("Conversation user not found.")
        return redirect(url_for("inbox"))

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            conn = get_db()
            conn.execute(
                """
                INSERT INTO messages (sender_id, recipient_id, body, is_read, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (me["id"], other["id"], body, utc_now()),
            )
            conn.commit()
            conn.close()
        return redirect(url_for("thread", other_id=other_id))

    conn = get_db()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE sender_id = ? AND recipient_id = ?",
        (other["id"], me["id"]),
    )
    msgs = conn.execute(
        """
        SELECT *
        FROM messages
        WHERE (sender_id = ? AND recipient_id = ?)
           OR (sender_id = ? AND recipient_id = ?)
        ORDER BY created_at ASC, id ASC
        """,
        (me["id"], other["id"], other["id"], me["id"]),
    ).fetchall()
    conn.commit()
    conn.close()
    return render_template("thread.html", me=me, other=other, msgs=msgs)


@app.route("/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_message(message_id):
    me = current_user()
    conn = get_db()
    conn.execute(
        "DELETE FROM messages WHERE id = ? AND (sender_id = ? OR recipient_id = ?)",
        (message_id, me["id"], me["id"]),
    )
    conn.commit()
    conn.close()
    flash("Message deleted.")
    return redirect(url_for("inbox"))


@app.route("/profile/delete", methods=["POST"])
@login_required
def delete_profile():
    me = current_user()
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (me["id"],))
    conn.commit()
    conn.close()
    session.clear()
    flash("Your profile has been deleted.")
    return redirect(url_for("home"))


@app.route("/profile/delete-photo", methods=["POST"])
@login_required
def delete_profile_photo():
    me = current_user()
    conn = get_db()
    conn.execute("UPDATE users SET profile_pic = '', updated_at = ? WHERE id = ?", (utc_now(), me["id"]))
    conn.commit()
    conn.close()
    flash("Profile picture removed.")
    return redirect(url_for("edit_profile"))


@app.route("/profile/delete-video", methods=["POST"])
@login_required
def delete_profile_video():
    me = current_user()
    conn = get_db()
    conn.execute("UPDATE users SET profile_video = '', updated_at = ? WHERE id = ?", (utc_now(), me["id"]))
    conn.commit()
    conn.close()
    flash("Profile video removed.")
    return redirect(url_for("edit_profile"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/healthz")
def healthz():
    return {"ok": True, "database": str(DB_PATH)}


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print(f"Initialized database at {DB_PATH}")


@app.cli.command("seed-test-users")
def seed_test_users_command():
    init_db()
    password_hash = generate_password_hash("password123")
    users = [
        ("shay@example.com", "Shay", "artist", "R&B / Soul", "Atlanta", "GA", "Vocalist and curator building community through music.", "vocals, songwriter, live performance", "voice", "features, hooks, live sets"),
        ("rod@example.com", "Rod", "producer", "Hip-Hop / Gospel", "New Orleans", "LA", "Producer and musician sharing beats, keys, and live sessions.", "producer, keys, beatmaker", "keys", "production, mixing, performance"),
    ]
    conn = get_db()
    for row in users:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (row[0],)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE users
                SET display_name = ?, role = ?, genre = ?, city = ?, state = ?,
                    bio = ?, tags_csv = ?, instrument = ?, services_csv = ?, updated_at = ?
                WHERE email = ?
                """,
                (*row[1:], utc_now(), row[0]),
            )
        else:
            conn.execute(
                """
                INSERT INTO users
                    (email, password_hash, display_name, role, genre, city, state,
                     bio, tags_csv, instrument, services_csv, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (row[0], password_hash, *row[1:], utc_now(), utc_now()),
            )
    conn.commit()
    conn.close()
    print("Seeded Shay and Rod. Password for both: password123")


init_db()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
