from app import DB_PATH, init_db


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
