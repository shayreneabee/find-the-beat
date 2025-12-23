import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, abort, redirect, url_for, session, flash, Response

# -----------------------------
# App setup
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ftb.db")

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Uploads (inside /static so browser can see them)
UPLOAD_SHOWCASES_DIR = os.path.join(BASE_DIR, "static", "uploads", "showcases")
os.makedirs(UPLOAD_SHOWCASES_DIR, exist_ok=True)

ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp"}

def allowed_image(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTS

app.config["SECRET_KEY"] = "dev-secret-change-me"  # fine for local dev


# -----------------------------
# DB helpers
# -----------------------------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
def ensure_showcases_table():
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

          host_user_id INTEGER,
          host_name TEXT,

          performers_csv TEXT,
          performer_user_ids_csv TEXT,

          ticket_url TEXT,
          created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def ensure_showcases_schema():
    """
    Adds missing columns safely if you already had an older showcases table.
    """
    ensure_showcases_table()
    conn = db()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(showcases)").fetchall()]

    def add_col(name, coltype):
        if name not in cols:
            conn.execute(f"ALTER TABLE showcases ADD COLUMN {name} {coltype}")

    add_col("event_time", "TEXT")
    add_col("address", "TEXT")
    add_col("host_user_id", "INTEGER")
    add_col("host_name", "TEXT")
    add_col("performers_csv", "TEXT")
    add_col("performer_user_ids_csv", "TEXT")
    add_col("ticket_url", "TEXT")
    add_col("created_at", "TEXT")

    conn.commit()
    conn.close()


def parse_csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def parse_int_csv(s):
    out = []
    for x in parse_csv(s):
        try:
            out.append(int(x))
        except:
            pass
    return out


def current_user_id():
    # only works if your login sets session["user_id"] already
    return session.get("user_id")


def ensure_showcases_schema():
    """
    If the showcases table exists but is missing new columns, add them safely.
    """
    ensure_showcases_table()
    conn = db()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(showcases)").fetchall()]

    def add_col(name, coltype):
        if name not in cols:
            conn.execute(f"ALTER TABLE showcases ADD COLUMN {name} {coltype}")

    add_col("host_name", "TEXT")
    add_col("performers_csv", "TEXT")
    add_col("ticket_url", "TEXT")

    conn.commit()
    conn.close()


def parse_csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def ensure_db():
    """
    If the db exists already, we leave it alone.
    If not, create the users table with your confirmed columns.
    """
    if os.path.exists(DB_PATH):
        return

    conn = db()
    conn.execute(
        """
        CREATE TABLE users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          display_name TEXT,
          role TEXT,
          genre TEXT,
          city TEXT,
          bio TEXT,
          tags_csv TEXT,
          instrument TEXT,
          services_csv TEXT,
          profile_pic TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def parse_csv(s: str) -> List[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


# -----------------------------
# Routes
# -----------------------------
@app.route("/landing")
def landing():
    return render_template("landing.html")
@app.route("/c/showcases")
def showcases_list():
    ensure_showcases_schema()

    conn = db()
    rows = conn.execute(
        """
        SELECT id, title, event_date, event_time, city, address, venue, description, poster_path,
               host_user_id, host_name, performers_csv, performer_user_ids_csv, ticket_url
        FROM showcases
        ORDER BY COALESCE(event_date,'') DESC, id DESC
        """
    ).fetchall()
    conn.close()

    showcases = []
    for r in rows:
        showcases.append({
            "id": r["id"],
            "title": r["title"],
            "event_date": r["event_date"] or "TBA",
            "event_time": r["event_time"] or "",
            "city": r["city"] or "—",
            "address": r["address"] or "",
            "venue": r["venue"] or "—",
            "description": r["description"] or "",
            "poster_path": r["poster_path"] or "img/showcase.jpg",
            "host_user_id": r["host_user_id"],
            "host_name": r["host_name"] or "",
            "performers": parse_csv(r["performers_csv"]),
            "performer_user_ids": parse_int_csv(r["performer_user_ids_csv"]),
            "ticket_url": r["ticket_url"] or "",
        })

    return render_template("showcases_list.html", showcases=showcases)


@app.route("/s/<int:showcase_id>")
def showcase_detail(showcase_id):
    ensure_showcases_schema()

    conn = db()
    r = conn.execute(
        """
        SELECT id, title, event_date, event_time, city, address, venue, description, poster_path,
               host_user_id, host_name, performers_csv, performer_user_ids_csv, ticket_url
        FROM showcases WHERE id = ?
        """,
        (showcase_id,),
    ).fetchone()

    if not r:
        conn.close()
        abort(404)

    performer_ids = parse_int_csv(r["performer_user_ids_csv"])
    performers = parse_csv(r["performers_csv"])

    linked_performers = []
    if performer_ids:
        qs = ",".join("?" for _ in performer_ids)
        user_rows = conn.execute(f"SELECT id, display_name FROM users WHERE id IN ({qs})", performer_ids).fetchall()
        by_id = {u["id"]: u["display_name"] for u in user_rows}
        for pid in performer_ids:
            if pid in by_id:
                linked_performers.append({"id": pid, "name": by_id[pid]})

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
    time_str = r["event_time"] or "19:00"  # default 7pm if you didn’t set one
    location = " ".join([x for x in [r["venue"], r["address"], r["city"]] if x])
    desc = (r["description"] or "").replace("\n", "\\n")

    # If date is missing, make a “now + 1 day” placeholder
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

        host_name = (request.form.get("host_name") or "").strip()
        performers_csv = (request.form.get("performers_csv") or "").strip()
        performer_user_ids_csv = (request.form.get("performer_user_ids_csv") or "").strip()

        if not title:
            return render_template("showcase_new.html", error="Title is required.", form=request.form)

        # tie to logged in user if available
        host_user_id = current_user_id()

        # if logged in, auto host name from DB if blank
        if host_user_id and not host_name:
            conn = db()
            u = conn.execute("SELECT display_name FROM users WHERE id = ?", (host_user_id,)).fetchone()
            conn.close()
            if u:
                host_name = u["display_name"]

        # poster upload
        poster_path = "img/showcase.jpg"
        file = request.files.get("poster")
        if file and file.filename and allowed_image(file.filename):
            safe = secure_filename(file.filename)
            safe = f"showcase_{int(datetime.utcnow().timestamp())}_{safe}"
            save_path = os.path.join(UPLOAD_SHOWCASES_DIR, safe)
            file.save(save_path)
            poster_path = f"uploads/showcases/{safe}"

        conn = db()
        cur = conn.execute(
            """
            INSERT INTO showcases (title, event_date, event_time, city, address, venue, description, poster_path,
                                  host_user_id, host_name, performers_csv, performer_user_ids_csv, ticket_url, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                title, event_date, event_time, city, address, venue, description, poster_path,
                host_user_id, host_name, performers_csv, performer_user_ids_csv, ticket_url,
                datetime.utcnow().isoformat()
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()

        return redirect(url_for("showcase_detail", showcase_id=new_id))

    return render_template("showcase_new.html", error="", form={})


@app.route("/")
def home():
    """
    Search page. Uses templates/index.html if you have it.
    If not, returns a simple HTML fallback so the app still runs.
    """
    q = (request.args.get("q") or "").strip().lower()

    conn = db()
    rows = conn.execute(
        """
        SELECT id, display_name, role, genre, city, bio, tags_csv, instrument, services_csv, profile_pic
        FROM users
        ORDER BY display_name COLLATE NOCASE
        """
    ).fetchall()
    conn.close()

    people = []
    for r in rows:
        blob = " ".join(
            [
                (r["display_name"] or ""),
                (r["role"] or ""),
                (r["genre"] or ""),
                (r["city"] or ""),
                (r["bio"] or ""),
                (r["tags_csv"] or ""),
                (r["instrument"] or ""),
                (r["services_csv"] or ""),
            ]
        ).lower()

        if q and q not in blob:
            continue

        people.append(
            {
                "id": r["id"],
                "display_name": r["display_name"] or "Unnamed",
                "role": r["role"] or "",
                "genre": r["genre"] or "",
                "city": r["city"] or "",
                "bio": r["bio"] or "",
                "tags": parse_csv(r["tags_csv"]),
                "instrument": r["instrument"] or "",
                "services": parse_csv(r["services_csv"]),
                "profile_pic": r["profile_pic"] or "",
            }
        )

    # Try your existing template. If it doesn't exist, fallback HTML.
    try:
        return render_template("index.html", people=people, q=request.args.get("q", ""))
    except TemplateNotFound:
        # Minimal fallback so you never get stuck
        items = "".join(
            f'<li><a href="/u/{p["id"]}">{p["display_name"]}</a> — {p["city"]}</li>'
            for p in people
        )
        return f"""
        <html><head><title>Find the Beat</title></head>
        <body style="font-family:system-ui;padding:20px;">
          <h1>Find the Beat</h1>
          <p><a href="/landing">Go to landing</a></p>
          <form>
            <input name="q" placeholder="search..." value="{request.args.get('q','')}" />
            <button>Search</button>
          </form>
          <ul>{items}</ul>
        </body></html>
        """


@app.route("/u/<int:user_id>")
def user_detail(user_id: int):
    conn = db()
    row = conn.execute(
        """
        SELECT id, display_name, role, genre, city, bio, tags_csv, instrument, services_csv, profile_pic
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    if not row:
        abort(404)

    person = {
        "id": row["id"],
        "display_name": row["display_name"] or "Unnamed",
        "role": row["role"] or "",
        "genre": row["genre"] or "",
        "city": row["city"] or "",
        "state": "",  # not in DB yet
        "bio": row["bio"] or "",
        "instrument": row["instrument"] or "",
        "services": parse_csv(row["services_csv"]),
        "tags": parse_csv(row["tags_csv"]),
        "profile_pic": row["profile_pic"] or "",
    }

    return render_template("user_detail.html", person=person)


@app.route("/c/<string:kind>")
def category(kind: str):
    # Normalize URL variations
    kind = (kind or "").strip().lower()
    aliases = {
        "composer": "composers",
        "composers": "composers",
        "musician": "musicians",
        "musicians": "musicians",
        "showcase": "showcases",
        "showcases": "showcases",
        "production": "production",
        "artist": "artist",
        "artists": "artist",
    }
    kind = aliases.get(kind, kind)

    titles = {
        "production": ("PRODUCTION", "All Production Jobs"),
        "composers": ("COMPOSERS", "All Composers"),
        "musicians": ("MUSICIANS", "All Instruments"),
        "artist": ("ARTIST", "All Artists"),
        "showcases": ("SHOWCASES", "This Week in Showcases"),
    }
    if kind not in titles:
        abort(404)

    title, subtitle = titles[kind]

    conn = db()
    rows = conn.execute(
        """
        SELECT id, display_name, role, genre, city, instrument, services_csv, profile_pic
        FROM users
        ORDER BY display_name COLLATE NOCASE
        """
    ).fetchall()
    conn.close()

    def nonempty(s: str) -> bool:
        return (s or "").strip() != ""

    people: List[Dict] = []
    for r in rows:
        role = (r["role"] or "").lower()
        genre = (r["genre"] or "").lower()
        services = (r["services_csv"] or "").lower()

        ok = True
        special = ""

        if kind == "musicians":
            ok = nonempty(r["instrument"])
            special = r["instrument"] or "Musician"

        elif kind == "composers":
            ok = ("composer" in role) or ("composer" in services) or ("score" in genre) or ("composer" in genre)
            special = r["genre"] or "Composer"

        elif kind == "production":
            ok = ("producer" in services) or ("engineer" in services) or ("mix" in services) or ("master" in services)
            first = parse_csv(r["services_csv"])
            special = first[0] if first else "Production"

        elif kind == "artist":
            ok = ("artist" in role) or ("singer" in role) or ("songwriter" in role)
            special = r["role"] or "Artist"

        elif kind == "showcases":
            # simple stub: anyone with a profile pic looks "featured"
            ok = nonempty(r["profile_pic"])
            special = r["role"] or "Featured"

        if not ok:
            continue

        people.append(
            {
                "id": r["id"],
                "display_name": r["display_name"] or "Unnamed",
                "city": r["city"] or "",
                "state": "",
                "special": special,
                "profile_pic": r["profile_pic"] or "",
            }
        )

    # UI filter pills (we’ll wire these to real query params later)
    filters = []
    if kind == "musicians":
        for inst in ["Guitar", "Piano", "Drums", "Sax", "Violin"]:
            filters.append({"label": inst, "href": f"/c/musicians"})
    elif kind == "composers":
        for g in ["Film Score", "Jazz", "Ragtime", "Video Game", "Television"]:
            filters.append({"label": g, "href": f"/c/composers"})
    elif kind == "production":
        for r in ["Producer", "Engineer", "Mixer", "Mastering"]:
            filters.append({"label": r, "href": f"/c/production"})

    return render_template("category.html", title=title, subtitle=subtitle, people=people, filters=filters)
@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = 1  # for now: you are the only user

    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        role = (request.form.get("role") or "").strip()
        genre = (request.form.get("genre") or "").strip()
        city = (request.form.get("city") or "").strip()
        bio = (request.form.get("bio") or "").strip()
        instrument = (request.form.get("instrument") or "").strip()
        services_csv = (request.form.get("services_csv") or "").strip()
        tags_csv = (request.form.get("tags_csv") or "").strip()

        conn = db()
        conn.execute(
            """
            UPDATE users
            SET display_name=?, role=?, genre=?, city=?, bio=?, instrument=?, services_csv=?, tags_csv=?
            WHERE id=?
            """,
            (display_name, role, genre, city, bio, instrument, services_csv, tags_csv, user_id),
        )
        conn.commit()
        conn.close()

    conn = db()
    user = conn.execute(
        """
        SELECT id, display_name, role, genre, city, bio, tags_csv, instrument, services_csv, profile_pic
        FROM users WHERE id=?
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    if not user:
        abort(404)

    return render_template("profile.html", user=user)


if __name__ == "__main__":
    ensure_db()
    app.run(debug=True)

if __name__ == "__main__":
    ensure_db()
    ensure_showcases_schema()
    app.run(debug=True)

if __name__ == "__main__":
    ensure_db()
    ensure_showcases_schema()
    app.run(debug=True)

