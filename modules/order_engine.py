# modules/order_engine.py

import streamlit as st
import os

from modules.nlp_core import (
    load_catalog_from_csv,
    load_voice_phrases,
    init_voice_phrases_or_exit,
    register_catalog,
    parse_orders_verbose,   # pakai engine CP12 langsung
)

# ============================
# HELPER: RESOLVE PATH
# ============================
def resolve_path(filename: str) -> str:
    """
    Menghasilkan absolute path file dataset
    berdasarkan lokasi project → aman untuk Streamlit.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))   # .../modules
    root_dir = os.path.abspath(os.path.join(base_dir, ".."))  # naik 1 folder
    abs_path = os.path.join(root_dir, filename)
    return abs_path


# ============================
# INIT NLP CP12 (sekali per session)
# ============================
def init_nlp():
    """
    Inisialisasi:
    - voice_phrases (untuk say_phrase di CP12)
    - alias index (lewat register_catalog)
    CATATAN:
    - Di sini kita TIDAK lagi menyimpan catalog ke session_state;
      catalog akan dimuat ulang di process_command() setiap kali dipanggil
      supaya tidak tergantung state yang bisa kosong.
    """

    # Jangan double-init
    if st.session_state.get("nlp_initialized"):
        return

    catalog_path = resolve_path("catalog_depo78_clean.csv")
    phrases_path = resolve_path("voice_phrases.csv")

    # Inisialisasi VOICE_PHRASES global untuk say_phrase()
    init_voice_phrases_or_exit(phrases_path)

    # (optional) kalau mau tetap simpan ke session_state:
    # voice_phrases = load_voice_phrases(phrases_path)
    # st.session_state["voice_phrases"] = voice_phrases

    catalog = load_catalog_from_csv(catalog_path)
    st.session_state["catalog"] = catalog

    register_catalog(catalog)
    st.session_state["nlp_initialized"] = True

# ============================
# PROCESS COMMAND (WRAPPER CP12)
# ============================
# modules/order_engine.py

def process_command(user, text: str):
    # Pastikan NLP sudah ter-init
    if not st.session_state.get("nlp_initialized"):
        init_nlp()

    # Pakai catalog yang sama dengan yang dipakai register_catalog()
    catalog = st.session_state.get("catalog")
    if not catalog:
        st.error("Catalog belum ada di session_state. Jalankan init_nlp() dulu.")
        return []

    # (OPSIONAL tapi aman) rebuild index jika kamu sering edit CSV saat app hidup
    register_catalog(catalog)

    parsed_raw = parse_orders_verbose(text, catalog)

    # DEBUG (hapus kalau sudah normal)
    # st.write("DEBUG parsed_raw:", parsed_raw)

    results = []
    for info in parsed_raw or []:
        results.append(
            {
                "chunk": info.get("chunk") or info.get("text") or text,
                "qty": info.get("qty"),  # bisa None kalau user belum sebut qty
                "has_explicit_qty": info.get("has_explicit_qty", False),
                "chosen_item": info.get("chosen_item"),
                "need_action": info.get("need_action"),   # ✅ tambahan
                "meta": info,
            }
        )
    return results
