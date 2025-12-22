from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "dev-only-change-me"  # later we’ll move to .env

DB_PATH = Path("ftb.db")

# Seed artists (your demo data)
ARTISTS = [
    {
        "id": 1,
        "name": "Jayla Rivers",
        "role": "Vocalist",
        "genre": "R&B",
        "city": "New Orleans",
        "tags": ["harmonies", "hooks", "studio-ready"],
        "bio": "Warm tone, strong harmonies, and quick turnaround on features.",
        "type": "seed",
    },
    {
        "id": 2,
        "name": "Marcus “M-Keys” Allen",
        "role": "Producer",
        "genre": "Hip-Hop",
        "city": "Atlanta",
        "tags": ["808s", "melodic beats", "mixing"],
        "bio": "Dark bounce + catchy melodies. Beats, mixes, and full song builds.",
        "type": "seed",
    },
    {
        "id": 3,
        "name": "Tasha Green",
        "role": "Songwriter",
        "genre": "R&B",
        "city": "Houston",
        "tags": ["toplines", "storytelling", "melodies"],
        "bio": "Writes hooks and verses that feel personal and radio-ready.",
        "type": "seed",
    },
    {
        "id": 4,
        "name": "Deon Carter",
        "role": "Guitarist",
        "genre": "Gospel",
        "city": "Chicago",
        "tags": ["live", "session", "tour"],
        "bio": "Clean tone, quick charting, and strong live performance chops.",
        "type": "seed",
    },
    {
        "id": 5,
        "name": "Kiki Monroe",
        "role": "Rapper",
        "genre": "Hip-Hop",
        "city": "Dallas",
        "tags": ["freestyle", "performance", "features"],
        "bio": "Big energy performer. Fast writer and strong delivery.",
        "type": "seed",
    },
]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            role TEXT DEFAULT '',
            genre TEXT DEFAULT '',
            city TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            tags_csv TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

init_db()

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return row

def user_rows_as_artists():
    conn = db()
    rows = conn.execute("""
        SELECT id, display_name, role, genre, city, bio, tags_csv
        FROM users
        WHERE display_name != ''
    """).fetchall()
    conn.close()

    out = []
    for r in rows:
        tags = [t.strip() for t in (r["tags_csv"] or "").split(",") if t.strip()]
        out.append({
            "id": r["id"],
            "name": r["display_name"],
            "role": r["role"] or "Artist",
            "genre": r["genre"] or "—",
            "city": r["city"] or "—",
            "bio": r["bio"] or "",
            "tags": tags,
            "type": "user",
        })
    return out

def matches_query(artist: dict, q: str) -> bool:
    haystack = " ".join([
        artist.get("name", ""),
        artist.get("role", ""),
        artist.get("genre", ""),
        artist.get("city", ""),
        " ".join(artist.get("tags", [])),
        artist.get("bio", ""),
    ]).lower()
    return q.lower() in haystack


# ---------- PAGES ----------
@app.route("/landing")
def landing():
    return render_template("landing.html", user=current_user())

@app.route("/", methods=["GET"])
def home():
    q = (request.args.get("q") or "").strip()

    all_artists = ARTISTS + user_rows_as_artists()

    if q:
        results = [a for a in all_artists if matches_query(a, q)]
        title = f'Results for “{q}”'
    else:
        results = all_artists
        title = "Discover Artists"

    return render_template("index.html", artists=results, title=title, q=q, user=current_user())


# ---------- AUTH ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("signup"))

        conn = db()
        try:
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("That email is already registered. Try logging in.")
            return redirect(url_for("login"))

        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
        conn.close()

        session["user_id"] = user_id
        return redirect(url_for("profile"))

    return render_template("signup.html", user=current_user())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        conn = db()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if not row or not check_password_hash(row["password_hash"], password):
            flash("Email or password is incorrect.")
            return redirect(url_for("login"))

        session["user_id"] = row["id"]
        return redirect(url_for("profile"))

    return render_template("login.html", user=current_user())

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("landing"))


# ---------- PROFILE ----------
@app.route("/profile", methods=["GET", "POST"])
def profile():
    user = current_user()
    if not user:
        return redirect(url_for("landing"))

    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        role = (request.form.get("role") or "").strip()
        genre = (request.form.get("genre") or "").strip()
        city = (request.form.get("city") or "").strip()
        bio = (request.form.get("bio") or "").strip()
        tags_csv = (request.form.get("tags_csv") or "").strip()

        conn = db()
        conn.execute("""
            UPDATE users
            SET display_name=?, role=?, genre=?, city=?, bio=?, tags_csv=?
            WHERE id=?
        """, (display_name, role, genre, city, bio, tags_csv, user["id"]))
        conn.commit()
        conn.close()

        flash("Profile updated. You’re in the search now 😌")
        return redirect(url_for("home"))

    return render_template("profile.html", user=user)


# ---------- OPTIONAL: USER DETAIL PAGE ----------
@app.route("/u/<int:user_id>")
def user_detail(user_id):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)

    tags = [t.strip() for t in (row["tags_csv"] or "").split(",") if t.strip()]
    artist = {
        "id": row["id"],
        "name": row["display_name"] or "Unnamed Artist",
        "role": row["role"] or "Artist",
        "genre": row["genre"] or "—",
        "city": row["city"] or "—",
        "bio": row["bio"] or "",
        "tags": tags,
        "type": "user",
    }
    return render_template("artist.html", artist=artist, user=current_user())


if __name__ == "__main__":
    app.run(debug=True)

