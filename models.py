from datetime import datetime
from extensions import db


class Profile(db.Model):
    __tablename__ = "profile"

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="artist")  # artist/producer/venue/etc
    bio = db.Column(db.Text, nullable=True)

    photo_filename = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    performances = db.relationship("Performance", backref="profile", lazy=True)


class Performance(db.Model):
    __tablename__ = "performance"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)

    video_filename = db.Column(db.String(255), nullable=True)
    thumb_filename = db.Column(db.String(255), nullable=True)

    profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)

    subject = db.Column(db.String(140), nullable=True)
    body = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
