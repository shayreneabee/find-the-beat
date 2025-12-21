import os
import sqlite3
from flask import Flask, render_template, request, abort, redirect, url_for, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, abort, redirect, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["DATABASE"] = os.path.join(os.path.dirname(__file__), "ftb.db")
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS creators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            genre TEXT NOT NULL,
            location TEXT NOT NULL,
            instagram TEXT,
            bio TEXT,
            photo TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    db.commit()

@app.before_request
def _ensure_db():
    init_db()
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        errors = []
        if len(name) < 2: errors.append("Name is required.")
        if "@" not in email: errors.append("Valid email required.")
        if len(password) < 6: errors.append("Password must be at least 6 characters.")

        if errors:
            return render_template("register.html", errors=errors, form=request.form)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password))
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template("register.html", errors=["Email already registered."], form=request.form)

        return redirect(url_for("login"))

    return render_template("register.html", errors=[], form={})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", errors=["Invalid email or password."], form=request.form)

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("dashboard"))

    return render_template("login.html", errors=[], form={})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

ARTISTS = [
    {
        "slug": "amina-rose",
        "name": "Amina Rose",
        "role": "Singer",
        "genre": "R&B",
        "location": "New Orleans, LA",
        "bio": "Smooth vocals with a classic soul edge. Open to features and live gigs.",
        "links": {"instagram": "@aminarose", "email": "amina@example.com"},
        "photo": "avatars/default.svg",
    },
    {
        "slug": "dj-sway",
        "name": "DJ Sway",
        "role": "DJ",
        "genre": "Hip-Hop",
        "location": "Houston, TX",
        "bio": "Club-ready mixes and clean transitions. Looking for event bookings + collabs.",
        "links": {"instagram": "@djsway", "email": "sway@example.com"},
        "photo": "avatars/default.svg",
    },
    {
        "slug": "kairo-keys",
        "name": "Kairo Keys",
        "role": "Producer",
        "genre": "Afrobeats",
        "location": "Atlanta, GA",
        "bio": "Melodic drums + bright synths. Seeking artists for upbeat, global sounds.",
        "links": {"instagram": "@kairokeys", "email": "kairo@example.com"},
        "photo": "avatars/default.svg",
    },
    {
        "slug": "maya-blu",
        "name": "Maya Blu",
        "role": "Songwriter",
        "genre": "Pop",
        "location": "Chicago, IL",
        "bio": "Hooks for days. If you need lyrics, toplines, or a concept, let’s build.",
        "links": {"instagram": "@mayablu", "email": "maya@example.com"},
        "photo": "avatars/default.svg",
    },
    {
        "slug": "nola-nova",
        "name": "Nola Nova",
        "role": "Vocalist",
        "genre": "Neo-Soul",
        "location": "New Orleans, LA",
        "bio": "Neo-soul textures and harmonies. Available for studio sessions + features.",
        "links": {"instagram": "@nolanova", "email": "nova@example.com"},
        "photo": "avatars/default.svg",
    },
    {
        "slug": "saint-perc",
        "name": "Saint Perc",
        "role": "Drummer",
        "genre": "Jazz",
        "location": "New Orleans, LA",
        "bio": "Pocket + polish. Live and studio work. Touring-friendly.",
        "links": {"instagram": "@saintperc", "email": "perc@example.com"},
        "photo": "avatars/default.svg",
    },
    {
        "slug": "tone-carter",
        "name": "Tone Carter",
        "role": "Producer",
        "genre": "Trap",
        "location": "Memphis, TN",
        "bio": "Hard drums, clean 808s. Looking for artists who want radio-ready sound.",
        "links": {"instagram": "@tonecarter", "email": "tone@example.com"},
        "photo": "avatars/default.svg",
    },
    {
        "slug": "zuri-vibes",
        "name": "Zuri Vibes",
        "role": "Artist",
        "genre": "Dancehall",
        "location": "Miami, FL",
        "bio": "Dancehall energy with pop crossover potential. Let’s create something loud.",
        "links": {"instagram": "@zurivibes", "email": "zuri@example.com"},
        "photo": "avatars/default.svg",
    },
]

# Temporary “inbox” (in memory). Later we’ll replace this with a database.
MESSAGES = []

def get_artist_by_slug(slug: str):
    for a in ARTISTS:
        if a["slug"] == slug:
            return a
    return None

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/discover")
def discover():
    q = request.args.get("q", "").strip().lower()

    if q:
        filtered = [
            a for a in ARTISTS
            if q in a["name"].lower()
            or q in a["role"].lower()
            or q in a["genre"].lower()
            or q in a["location"].lower()
        ]
    else:
        filtered = ARTISTS

    return render_template("index.html", artists=filtered, q=request.args.get("q", ""))
    q = request.args.get("q", "").strip().lower()

    if q:
        filtered = [
            a for a in ARTISTS
            if q in a["name"].lower()
            or q in a["role"].lower()
            or q in a["genre"].lower()
            or q in a["location"].lower()
        ]
    else:
        filtered = ARTISTS

    return render_template("index.html", artists=filtered, q=request.args.get("q", ""))

@app.route("/profile/<slug>")
def profile(slug):
    artist = get_artist_by_slug(slug)
    if not artist:
        abort(404)
    return render_template("profile.html", artist=artist)

@app.route("/message/<slug>", methods=["GET", "POST"])
def message(slug):
    artist = get_artist_by_slug(slug)
    if not artist:
        abort(404)

    if request.method == "POST":
        sender_name = request.form.get("sender_name", "").strip()
        sender_email = request.form.get("sender_email", "").strip()
        body = request.form.get("body", "").strip()

        errors = []
        if len(sender_name) < 2:
            errors.append("Please enter your name.")
        if "@" not in sender_email or "." not in sender_email:
            errors.append("Please enter a valid email.")
        if len(body) < 5:
            errors.append("Message is too short.")

        if errors:
            return render_template("message.html", artist=artist, errors=errors, form=request.form)

        MESSAGES.append({
            "to_slug": artist["slug"],
            "to_name": artist["name"],
            "sender_name": sender_name,
            "sender_email": sender_email,
            "body": body,
        })

        return redirect(url_for("message_sent", slug=artist["slug"]))

    return render_template("message.html", artist=artist, errors=[], form={})

@app.route("/message/<slug>/sent")
def message_sent(slug):
    artist = get_artist_by_slug(slug)
    if not artist:
        abort(404)
    return render_template("message_sent.html", artist=artist)
@app.route("/inbox")
def inbox():
    # newest first
    msgs = list(reversed(MESSAGES))
    return render_template("inbox.html", messages=msgs)

if __name__ == "__main__":
    app.run(debug=True)

def require_login():
    if "user_id" not in session:
        return False
    return True

@app.route("/dashboard")
def dashboard():
    if not require_login():
        return redirect(url_for("login"))

    db = get_db()
    creator = db.execute(
        "SELECT * FROM creators WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (session["user_id"],)
    ).fetchone()

    return render_template("dashboard.html", creator=creator)

@app.route("/join", methods=["GET", "POST"])
def join():
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        role = request.form.get("role", "").strip()
        genre = request.form.get("genre", "").strip()
        location = request.form.get("location", "").strip()
        instagram = request.form.get("instagram", "").strip()
        bio = request.form.get("bio", "").strip()

        errors = []
        if len(display_name) < 2: errors.append("Display name is required.")
        if len(role) < 2: errors.append("Role is required.")
        if len(genre) < 2: errors.append("Genre is required.")
        if len(location) < 2: errors.append("Location is required.")
        if len(bio) < 10: errors.append("Bio should be at least 10 characters.")

        if errors:
            return render_template("join.html", errors=errors, form=request.form)

        db = get_db()
        db.execute("""
            INSERT INTO creators (user_id, display_name, role, genre, location, instagram, bio, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["user_id"], display_name, role, genre, location, instagram, bio, "avatars/default.svg"))
        db.commit()

        return redirect(url_for("dashboard"))

    return render_template("join.html", errors=[], form={})

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    creator = db.execute(
        "SELECT * FROM creators WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (session["user_id"],)
    ).fetchone()

    return render_template("dashboard.html", creator=creator)

