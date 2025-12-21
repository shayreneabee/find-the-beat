from flask import Flask, render_template, request

app = Flask(__name__)

ARTISTS = [
    {
        "id": 1,
        "name": "Jayla Rivers",
        "role": "Vocalist",
        "genre": "R&B",
        "city": "New Orleans",
        "tags": ["harmonies", "hooks", "studio-ready"],
        "bio": "Warm tone, strong harmonies, and quick turnaround on features.",
    },
    {
        "id": 2,
        "name": "Marcus “M-Keys” Allen",
        "role": "Producer",
        "genre": "Hip-Hop",
        "city": "Atlanta",
        "tags": ["808s", "melodic beats", "mixing"],
        "bio": "Dark bounce + catchy melodies. Beats, mixes, and full song builds.",
    },
    {
        "id": 3,
        "name": "Tasha Green",
        "role": "Songwriter",
        "genre": "R&B",
        "city": "Houston",
        "tags": ["toplines", "storytelling", "melodies"],
        "bio": "Writes hooks and verses that feel personal and radio-ready.",
    },
    {
        "id": 4,
        "name": "Deon Carter",
        "role": "Guitarist",
        "genre": "Gospel",
        "city": "Chicago",
        "tags": ["live", "session", "tour"],
        "bio": "Clean tone, quick charting, and strong live performance chops.",
    },
    {
        "id": 5,
        "name": "Kiki Monroe",
        "role": "Rapper",
        "genre": "Hip-Hop",
        "city": "Dallas",
        "tags": ["freestyle", "performance", "features"],
        "bio": "Big energy performer. Fast writer and strong delivery.",
    },
]


def matches_query(artist: dict, q: str) -> bool:
    haystack = " ".join(
        [
            artist["name"],
            artist["role"],
            artist["genre"],
            artist["city"],
            " ".join(artist.get("tags", [])),
            artist.get("bio", ""),
        ]
    ).lower()
    return q.lower() in haystack


@app.route("/", methods=["GET"])
def home():
    q = (request.args.get("q") or "").strip()
    if q:
        results = [a for a in ARTISTS if matches_query(a, q)]
        title = f'Results for “{q}”'
    else:
        results = ARTISTS
        title = "Discover Artists"

    return render_template("index.html", artists=results, title=title, q=q)


if __name__ == "__main__":
    app.run(debug=True)

