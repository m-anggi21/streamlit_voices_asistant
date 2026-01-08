# modules/auth_web.py
import hashlib
from modules.db import get_db

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def login_web(username: str, password: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    pw_hash = hash_password(password)
    username_norm = (username or "").strip()

    cursor.execute("""
        SELECT
            users_id, nama, username, cluster, blok, no_rumah, gender, notelp, role, password_hash
        FROM users
        WHERE username = %s AND password_hash = %s
        LIMIT 1
    """, (username_norm, pw_hash))

    user = cursor.fetchone()
    cursor.close()
    db.close()

    if not user:
        return False, None

    auth_user = {
        "users_id": user["users_id"],
        "nama": user.get("nama"),
        "username": user.get("username"),
        "cluster": user.get("cluster"),
        "blok": user.get("blok"),
        "no_rumah": user.get("no_rumah"),
        "gender": user.get("gender"),
        "notelp": user.get("notelp"),
        "role": user.get("role") or "user",
    }
    return True, auth_user


def signup_web(nama, username, cluster, blok, no_rumah, gender, notelp, password):
    db = get_db()
    cursor = db.cursor()

    username_norm = (username or "").strip()

    # cek username duplikat (pakai users_id sesuai tabel)
    cursor.execute("SELECT users_id FROM users WHERE username=%s LIMIT 1", (username_norm,))
    if cursor.fetchone():
        cursor.close()
        db.close()
        return False, "Username sudah digunakan."

    pw_hash = hash_password(password)

    # role dipaksa 'user' (admin tidak boleh dari signup)
    cursor.execute("""
        INSERT INTO users
            (nama, username, cluster, blok, no_rumah, gender, notelp, role, password_hash)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        nama, username_norm, cluster, blok, no_rumah, gender, notelp, "user", pw_hash
    ))

    db.commit()
    cursor.close()
    db.close()
    return True, "Akun berhasil dibuat."
