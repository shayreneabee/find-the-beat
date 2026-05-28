# Find the Beat 🎵

A full-stack web application that allows musicians and creatives to connect, collaborate, and showcase their work.

## 🚀 Features
- User authentication stored in SQLite
- Editable musician profiles tied to `users.id`
- Search by name, role, genre, city/state, tags, services, and instrument
- Public profile pages with profile media and uploaded performances
- Performance/video uploads stored in the database with uploader ownership
- User-to-user messaging with inbox, conversation threads, replies, and read status
- Profile picture and intro video uploads

## 🛠 Tech Stack
- Backend: Python (Flask)
- Database: SQLite
- Frontend: HTML, CSS, Jinja templates

## 📸 Screenshots
(Add screenshots here)

## ▶️ How to Run Locally
1. Clone the repo
2. Create a virtual environment
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   flask --app app run
   ```

The app initializes the SQLite database automatically. You can also run:

```bash
flask --app app init-db
```

## Test Accounts

Seed Shay and Rod:

```bash
flask --app app seed-test-users
```

Both test accounts use:

```text
password123
```

- Shay: `shay@example.com`
- Rod: `rod@example.com`

Recommended manual test:

1. Log in as Shay and complete her profile.
2. Log out.
3. Log in as Rod, complete his profile, and upload a performance.
4. Log out.
5. Log back in as Shay.
6. Search for Rod from Profiles.
7. Open Rod's public profile.
8. Open/watch Rod's uploaded performance.
9. Message Rod from his profile.
10. Log in as Rod and confirm the message appears in Inbox.

## Database Tables

- `users`: account and profile fields, including email, password hash, display name, role, genre, city/state, bio, tags/services, profile image, profile video, timestamps.
- `performances`: uploaded performances tied to `user_id`, including title, description, video filename, thumbnail filename, and timestamp.
- `messages`: user-to-user messages with `sender_id`, `recipient_id`, body, read/unread flag, and timestamp.

## Render Notes

Use a Web Service for this Flask app.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Set `SECRET_KEY` to a real secret value.
- For persistent uploads and SQLite, set up a Render persistent disk and point `INSTANCE_DIR`, `UPLOAD_DIR`, and `DATABASE_PATH` to disk-backed paths.

## 🌐 Live Demo
(Add link later if deployed)

## 📌 Future Improvements
- Real-time messaging
- Better search filtering
- Cloud deployment (AWS/Render)
