# modules/db.py
import os
import mysql.connector

def get_db():
    """
    Prioritas koneksi:
    1) Streamlit secrets (untuk deploy Streamlit Cloud)
    2) Environment variables (opsional)
    3) Fallback local (untuk running di laptop)
    """

    # --- 1) coba baca dari Streamlit Secrets ---
    try:
        import streamlit as st
        if "mysql" in st.secrets:
            cfg = st.secrets["mysql"]
            return mysql.connector.connect(
                host=cfg.get("host"),
                port=int(cfg.get("port", 3306)),
                user=cfg.get("user"),
                password=cfg.get("password"),
                database=cfg.get("database"),
                connection_timeout=10,
            )
    except Exception:
        # kalau bukan running di Streamlit / secrets belum ada, lanjut ke env/fallback
        pass

    # --- 2) env vars (opsional) ---
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "depo78")

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        connection_timeout=10,
    )
