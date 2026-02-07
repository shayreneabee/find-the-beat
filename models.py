from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)

    genre = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    photo_url = db.Column(db.Text, nullable=True)
    video_url = db.Column(db.Text, nullable=True)

    # 🔐 Owner key (private edit link)
    edit_key = db.Column(db.String(120), nullable=True)

    # 🔑 Simple login code (ties profiles to a user code)
    owner_code = db.Column(db.String(64), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)



