import os
import sqlite3

from datetime import datetime, timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    flash,
    Response,
)
from werkzeug.utils import secure_filename


# ============================================================
# App setup
# ============================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ftb.db")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# images + videos
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "mp4", "mov", "webm"}

# keep it reasonable for local dev
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB


# ============================================================
# Helpers
# ============================================================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def parse_csv(s: str):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def current_user_id():
    # MVP: single user
    return 1


# ============================================================
# Schemas / migrations
# ============================================================
def ensure_db():
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT,
          password_hash TEXT,
          display_name TEXT,
          role TEXT,
          genre TEXT,
          city TEXT,
          bio TEXT,
          tags_csv TEXT,
          instrument TEXT,
          services_csv TEXT,
          profile_pic TEXT,
          state TEXT
        )
        """
    )
    conn.commit()

    # seed a user if empty
    n = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if n == 0:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, role, genre, city, state, bio, tags_csv, instrument, services_csv, profile_pic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "shay@example.com",
                "x",
                "ShayBee",
                "Singer",
                "R&B",
                "McComb",
                "MS",
                "New here — building my network.",
                "R&B, Mississippi",
                "Vocals",
                "producer, songwriter",
                "",
            ),
        )
        conn.commit()

    conn.close()


def ensure_showcases_schema():
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS showcases (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          event_date TEXT,
          event_time TEXT,
          city TEXT,
          address TEXT,
          venue TEXT,
          description TEXT,
          poster_path TEXT,
          video_path TEXT,
          host_user_id INTEGER,
          host_name TEXT,
          performers_csv TEXT,
          performer_user_ids_csv TEXT,
          ticket_url TEXT,
          created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_messages_schema():
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          thread_key TEXT NOT NULL,
          from_user_id INTEGER NOT NULL,
          to_user_id INTEGER NOT NULL,
          body TEXT NOT NULL,
          showcase_id INTEGER,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


# ============================================================
# Landing / Search
# ============================================================
@app.route("/landing")
def landing():
    return render_template("landing.html")


@app.route("/")
def home():
    q = (request.args.get("q") or "").strip().lower()

    conn = db()
    rows = conn.execute(
        """
        SELECT id, display_name, role, genre, city, state, instrument, services_csv, profile_pic
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()

    people = []
    for r in rows:
        services = parse_csv(r["services_csv"])
        if q:
            hay = " ".join(
                [
                    (r["display_name"] or ""),
                    (r["role"] or ""),
                    (r["genre"] or ""),
                    (r["city"] or ""),
                    (r["state"] or ""),
                    (r["instrument"] or ""),
                    (r["services_csv"] or ""),
                ]
            ).lower()
            if q not in hay:
                continue

        people.append(
            {
                "id": r["id"],
                "display_name": r["display_name"],
                "role": r["role"],
                "genre": r["genre"],
                "city": r["city"] or "—",
                "state": r["state"] or "",
                "instrument": r["instrument"] or "",
                "services": services,
                "profile_pic": r["profile_pic"] or "",
            }
        )

    return render_template("index.html", people=people, q=q)


# ============================================================
# Profile (with picture upload)
# ============================================================
@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = current_user_id()

    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        role = (request.form.get("role") or "").strip()
        genre = (request.form.get("genre") or "").strip()
        city = (request.form.get("city") or "").strip()
        state = (request.form.get("state") or "").strip().upper()
        bio = (request.form.get("bio") or "").strip()
        instrument = (request.form.get("instrument") or "").strip()
        services_csv = (request.form.get("services_csv") or "").strip()
        tags_csv = (request.form.get("tags_csv") or "").strip()

        profile_pic_path = None
        file = request.files.get("profile_pic")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = f"user_{user_id}_{int(datetime.utcnow().timestamp())}_{filename}"
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(save_path)
            profile_pic_path = f"uploads/{filename}"

        conn = db()
        if profile_pic_path:
            conn.execute(
                """
                UPDATE users
                SET display_name=?, role=?, genre=?, city=?, state=?, bio=?, instrument=?, services_csv=?, tags_csv=?, profile_pic=?
                WHERE id=?
                """,
                (
                    display_name,
                    role,
                    genre,
                    city,
                    state,
                    bio,
                    instrument,
                    services_csv,
                    tags_csv,
                    profile_pic_path,
                    user_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET display_name=?, role=?, genre=?, city=?, state=?, bio=?, instrument=?, services_csv=?, tags_csv=?
                WHERE id=?
                """,
                (
                    display_name,
                    role,
                    genre,
                    city,
                    state,
                    bio,
                    instrument,
                    services_csv,
                    tags_csv,
                    user_id,
                ),
            )
        conn.commit()
        conn.close()

        flash("Profile saved ✅")
        return redirect(url_for("profile"))

    conn = db()
    user = conn.execute(
        """
        SELECT id, display_name, role, genre, city, state, bio, tags_csv, instrument, services_csv, profile_pic
        FROM users WHERE id=?
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    if not user:
        abort(404)

    return render_template("profile.html", user=dict(user))


# ============================================================
# User detail page
# ============================================================
@app.route("/u/<int:user_id>")
def user_detail(user_id):
    ensure_showcases_schema()

    conn = db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)

    showcases = conn.execute(
        """
        SELECT id, title, event_date, event_time, city, poster_path
        FROM showcases
        WHERE host_user_id = ?
        ORDER BY COALESCE(event_date,'') DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()

    user = dict(row)
    user["tags"] = parse_csv(user.get("tags_csv"))
    user["services"] = parse_csv(user.get("services_csv"))

    show_list = []
    for s in showcases:
        show_list.append(
            {
                "id": s["id"],
                "title": s["title"],
                "event_date": s["event_date"] or "TBA",
                "event_time": s["event_time"] or "",
                "city": s["city"] or "—",
                "poster_path": s["poster_path"] or "img/showcase.jpg",
            }
        )

    return render_template("user_detail.html", user=user, showcases=show_list)


# ============================================================
# Category pages (Screen 1) + Production screen 2
# ============================================================
@app.route("/c/<string:kind>")
def category(kind):
    kind = (kind or "").strip().lower()
    if kind == "showcases":
        return redirect(url_for("showcases_list"))

    conn = db()
    rows = conn.execute(
        """
        SELECT id, display_name, role, genre, city, state, instrument, services_csv, profile_pic
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()

    title_map = {
        "artist": ("Artists", "Pick a vibe"),
        "musicians": ("Musicians", "Pick an instrument"),
        "composers": ("Composers", "Pick a lane"),
        "production": ("Production", "Pick a job"),
    }
    title, subtitle = title_map.get(kind, (kind.title(), f"All {kind.title()}"))

    people = []
    for r in rows:
        people.append(
            {
                "id": r["id"],
                "display_name": r["display_name"],
                "city": r["city"] or "—",
                "state": r["state"] or "",
                "profile_pic": r["profile_pic"] or "",
            }
        )

    return render_template("category.html", kind=kind, title=title, subtitle=subtitle, people=people, filters=[])


@app.route("/c/production/<path:job>")
def production_people(job):
    job_raw = (job or "").replace("-", " ").strip()
    pretty_job = " ".join([w.capitalize() for w in job_raw.split()])
    key = job_raw.lower()

    conn = db()
    rows = conn.execute(
        """
        SELECT id, display_name, city, state, services_csv, role, genre, profile_pic
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()

    def first_name(dn: str):
        dn = (dn or "").strip()
        return dn.split()[0] if dn else "Unnamed"

    people = []
    for r in rows:
        services = (r["services_csv"] or "").lower()
        role = (r["role"] or "").lower()
        genre = (r["genre"] or "").lower()
        if key in services or key in role or key in genre:
            people.append(
                {
                    "id": r["id"],
                    "first": first_name(r["display_name"]),
                    "city": (r["city"] or "—").strip(),
                    "st": (r["state"] or "").strip().upper(),
                    "profile_pic": r["profile_pic"] or "",
                }
            )

    return render_template("production_people.html", job_label=pretty_job, people=people)


# ============================================================
# Showcases (list / detail / new / ics)
# ============================================================
@app.route("/c/showcases")
def showcases_list():
    ensure_showcases_schema()

    conn = db()
    rows = conn.execute(
        """
        SELECT id, title, event_date, event_time, city, venue, poster_path, host_name
        FROM showcases
        ORDER BY COALESCE(event_date,'') DESC, id DESC
        """
    ).fetchall()
    conn.close()

    showcases = []
    for r in rows:
        showcases.append(
            {
                "id": r["id"],
                "title": r["title"],
                "event_date": r["event_date"] or "TBA",
                "event_time": r["event_time"] or "",
                "city": r["city"] or "—",
                "venue": r["venue"] or "—",
                "poster_path": r["poster_path"] or "img/showcase.jpg",
                "host_name": r["host_name"] or "",
            }
        )

    return render_template("showcases_list.html", showcases=showcases)


@app.route("/s/<int:showcase_id>")
def showcase_detail(showcase_id):
    ensure_showcases_schema()

    conn = db()
    r = conn.execute("SELECT * FROM showcases WHERE id = ?", (showcase_id,)).fetchone()
    conn.close()
    if not r:
        abort(404)

    performers = parse_csv(r["performers_csv"])
    linked_ids = parse_csv(r["performer_user_ids_csv"])

    linked_performers = []
    if linked_ids:
        conn = db()
        for pid in linked_ids:
            try:
                uid = int(pid)
            except:
                continue
            u = conn.execute("SELECT id, display_name FROM users WHERE id=?", (uid,)).fetchone()
            if u:
                linked_performers.append({"id": u["id"], "display_name": u["display_name"]})
        conn.close()

    showcase = {
        "id": r["id"],
        "title": r["title"],
        "event_date": r["event_date"] or "TBA",
        "event_time": r["event_time"] or "",
        "city": r["city"] or "—",
        "address": r["address"] or "",
        "venue": r["venue"] or "—",
        "description": r["description"] or "",
        "poster_path": r["poster_path"] or "img/showcase.jpg",
        "video_path": r["video_path"] or "",
        "host_user_id": r["host_user_id"],
        "host_name": r["host_name"] or "",
        "performers": performers,
        "linked_performers": linked_performers,
        "ticket_url": r["ticket_url"] or "",
        "is_owner": (current_user_id() is not None and r["host_user_id"] == current_user_id()),
    }

    return render_template("showcase_detail.html", showcase=showcase)


@app.route("/s/<int:showcase_id>/calendar.ics")
def showcase_ics(showcase_id):
    ensure_showcases_schema()

    conn = db()
    r = conn.execute(
        """
        SELECT id, title, event_date, event_time, city, address, venue, description
        FROM showcases WHERE id = ?
        """,
        (showcase_id,),
    ).fetchone()
    conn.close()

    if not r:
        abort(404)

    title = r["title"]
    date_str = r["event_date"] or ""
    time_str = r["event_time"] or "19:00"
    location = " ".join([x for x in [r["venue"], r["address"], r["city"]] if x])
    desc = (r["description"] or "").replace("\n", "\\n")

    try:
        start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except:
        start = datetime.now() + timedelta(days=1)

    end = start + timedelta(hours=2)

    def fmt(dt):
        return dt.strftime("%Y%m%dT%H%M%S")

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//FindTheBeat//Showcases//EN
BEGIN:VEVENT
UID:ftb-showcase-{r["id"]}@findthebeat
DTSTAMP:{fmt(datetime.utcnow())}
DTSTART:{fmt(start)}
DTEND:{fmt(end)}
SUMMARY:{title}
LOCATION:{location}
DESCRIPTION:{desc}
END:VEVENT
END:VCALENDAR
"""

    return Response(ics, mimetype="text/calendar")


@app.route("/showcases/new", methods=["GET", "POST"])
def showcase_new():
    ensure_showcases_schema()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        event_date = (request.form.get("event_date") or "").strip()
        event_time = (request.form.get("event_time") or "").strip()
        city = (request.form.get("city") or "").strip()
        address = (request.form.get("address") or "").strip()
        venue = (request.form.get("venue") or "").strip()
        description = (request.form.get("description") or "").strip()
        ticket_url = (request.form.get("ticket_url") or "").strip()

        host_user_id = current_user_id()
        host_name = (request.form.get("host_name") or "").strip() or "Host"
        performers_csv = (request.form.get("performers_csv") or "").strip()
        performer_user_ids_csv = (request.form.get("performer_user_ids_csv") or "").strip()

        if not title:
            return render_template("showcase_new.html", error="Title is required.", form=request.form)

        poster_path = ""
        poster = request.files.get("poster")
        if poster and poster.filename and allowed_file(poster.filename):
            filename = secure_filename(poster.filename)
            filename = f"showcase_{int(datetime.utcnow().timestamp())}_{filename}"
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            poster.save(save_path)
            poster_path = f"uploads/{filename}"

        video_path = ""
        video = request.files.get("video")
        if video and video.filename and allowed_file(video.filename):
            vname = secure_filename(video.filename)
            vname = f"showcase_{int(datetime.utcnow().timestamp())}_{vname}"
            vsave = os.path.join(UPLOAD_FOLDER, vname)
            video.save(vsave)
            video_path = f"uploads/{vname}"

        conn = db()
        conn.execute(
            """
            INSERT INTO showcases (
              title, event_date, event_time, city, address, venue, description,
              poster_path, video_path, host_user_id, host_name, performers_csv, performer_user_ids_csv,
              ticket_url, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                event_date,
                event_time,
                city,
                address,
                venue,
                description,
                poster_path,
                video_path,
                host_user_id,
                host_name,
                performers_csv,
                performer_user_ids_csv,
                ticket_url,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        flash("Showcase posted ✅")
        return redirect(url_for("showcases_list"))

    return render_template("showcase_new.html", form={})


# ============================================================
# Messages (Inbox + Thread + New)
# ============================================================
@app.route("/inbox")
def inbox():
    ensure_messages_schema()
    me = current_user_id()

    conn = db()
    rows = conn.execute(
        """
        SELECT m.id, m.thread_key, m.body, m.created_at, m.showcase_id,
               m.from_user_id, m.to_user_id,
               u1.display_name AS from_name,
               u2.display_name AS to_name
        FROM messages m
        LEFT JOIN users u1 ON u1.id = m.from_user_id
        LEFT JOIN users u2 ON u2.id = m.to_user_id
        WHERE m.from_user_id = ? OR m.to_user_id = ?
        ORDER BY m.created_at DESC
        """,
        (me, me),
    ).fetchall()
    conn.close()

    latest = {}
    for r in rows:
        if r["thread_key"] not in latest:
            latest[r["thread_key"]] = dict(r)

    threads = list(latest.values())
    return render_template("inbox.html", threads=threads, me=me)


@app.route("/messages/new", methods=["GET", "POST"])
def message_new():
    ensure_messages_schema()
    me = current_user_id()

    to_user_id = request.args.get("to") or request.form.get("to_user_id") or ""
    showcase_id = request.args.get("showcase") or request.form.get("showcase_id") or ""

    if request.method == "POST":
        to_user_id_int = int(to_user_id or "0")
        body = (request.form.get("body") or "").strip()
        showcase_id_val = int(showcase_id) if showcase_id else None

        if not (to_user_id_int and body):
            flash("Write a message first 😌")
            return redirect(url_for("message_new", to=to_user_id, showcase=showcase_id))

        a, b = sorted([me, to_user_id_int])
        thread_key = f"u{a}_u{b}"
        if showcase_id_val:
            thread_key = f"{thread_key}_s{showcase_id_val}"

        conn = db()
        conn.execute(
            """
            INSERT INTO messages (thread_key, from_user_id, to_user_id, body, showcase_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (thread_key, me, to_user_id_int, body, showcase_id_val, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

        return redirect(url_for("message_thread", thread_key=thread_key))

    conn = db()
    people = conn.execute("SELECT id, display_name, profile_pic FROM users ORDER BY id DESC").fetchall()
    conn.close()

    return render_template("message_new.html", people=people, to_user_id=str(to_user_id), showcase_id=str(showcase_id))


@app.route("/messages/<thread_key>", methods=["GET", "POST"])
def message_thread(thread_key):
    ensure_messages_schema()
    me = current_user_id()

    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        to_user_id = int(request.form.get("to_user_id") or "0")
        showcase_id = request.form.get("showcase_id") or None
        showcase_id = int(showcase_id) if showcase_id else None

        if body and to_user_id:
            conn = db()
            conn.execute(
                """
                INSERT INTO messages (thread_key, from_user_id, to_user_id, body, showcase_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thread_key, me, to_user_id, body, showcase_id, datetime.utcnow().isoformat()),
            )
            conn.commit()
            conn.close()

        return redirect(url_for("message_thread", thread_key=thread_key))

    conn = db()
    msgs = conn.execute(
        """
        SELECT m.*, u1.display_name AS from_name, u1.profile_pic AS from_pic,
                  u2.display_name AS to_name
        FROM messages m
        LEFT JOIN users u1 ON u1.id = m.from_user_id
        LEFT JOIN users u2 ON u2.id = m.to_user_id
        WHERE m.thread_key = ?
        ORDER BY m.created_at ASC
        """,
        (thread_key,),
    ).fetchall()

    other_id = None
    for m in msgs:
        if m["from_user_id"] != me:
            other_id = m["from_user_id"]
            break
        if m["to_user_id"] != me:
            other_id = m["to_user_id"]
            break

    other = None
    if other_id:
        other = conn.execute("SELECT id, display_name, profile_pic FROM users WHERE id=?", (other_id,)).fetchone()

    conn.close()

    return render_template("thread.html", msgs=msgs, thread_key=thread_key, me=me, other=other)


# ============================================================
# Run
# ============================================================
# --- Render / Gunicorn safe startup init ---
def init_app():
    ensure_db()
    ensure_showcases_schema()
    ensure_messages_schema()

init_app()

if __name__ == "__main__":
    ensure_db()
    ensure_showcases_schema()
    ensure_messages_schema()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

