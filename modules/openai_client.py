import os
import streamlit as st
import openai

def get_openai_client():
    """
    Mengembalikan OpenAI client dengan API Key otomatis dari secrets.
    Dipanggil oleh semua modul yang butuh STT/TTS/OpenAI API.
    """
    api_key = None

    # 1. Cek Streamlit secrets
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
    
    # 2. Fallback ke environment variable
    elif "OPENAI_API_KEY" in os.environ:
        api_key = os.environ["OPENAI_API_KEY"]

    if not api_key:
        raise ValueError(
            "ERROR: OPENAI_API_KEY tidak ditemukan!\n"
            "Set di .streamlit/secrets.toml atau environment variable."
        )

    openai.api_key = api_key
    return openai
