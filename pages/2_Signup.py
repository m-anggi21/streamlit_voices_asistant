# pages/2_Signup.py
import streamlit as st
import os
from modules.auth_web import signup_web

st.set_page_config(
    page_title="Signup - Depo 78",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Load CSS terpisah (pakai style.css yang sama)
def load_css(path="assets/styles.css"):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        css_path = os.path.join(base_dir, path)
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass

load_css()

st.markdown("<div class='depo-title'>Buat Akun Depo78</div>", unsafe_allow_html=True)
st.markdown("<div class='depo-card'>", unsafe_allow_html=True)

CLUSTERS = [
    "Manhattan", "Venetian", "vineyards",
    "Monte Carlo", "Banyan", "Blossom",
    "Royal Blossom", "Grand Canyon","Mirage"
]

nama = st.text_input("Nama Lengkap", placeholder="Masukkan nama lengkap")
username = st.text_input("Username", placeholder="Buat username")
cluster = st.selectbox("Pilih Cluster", CLUSTERS)
blok = st.text_input("Blok Rumah", placeholder="Misal: B")
no_rumah = st.text_input("Nomor Rumah", placeholder="Misal: 21")
gender = st.selectbox("Gender", ["L", "P"])
notelp = st.text_input("Nomor Telepon", placeholder="08xxxxxxxxxx")
pw = st.text_input("Password", type="password", placeholder="Masukkan password")
pw2 = st.text_input("Konfirmasi Password", type="password", placeholder="Ulangi password")

if st.button("Daftar", use_container_width=True):
    if not nama.strip() or not username.strip() or not blok.strip() or not no_rumah.strip() or not notelp.strip() or not pw.strip() or not pw2.strip():
        st.error("Semua field wajib diisi.")
    elif pw != pw2:
        st.error("Password tidak cocok!")
    else:
        ok, msg = signup_web(nama, username, cluster, blok, no_rumah, gender, notelp, pw)
        if ok:
            st.success(msg)
            st.switch_page("pages/1_Login.py")
        else:
            st.error(msg)

col_text, col_btn = st.columns([6, 40], gap="small")

with col_text:
    st.markdown(
        "<div style='margin-top:8px; text-align:left;'>Sudah punya akun?</div>",
        unsafe_allow_html=True
    )

with col_btn:
    if st.button("Login di sini", key="goto_login", type="secondary"):
        st.switch_page("pages/1_Login.py")

st.markdown("</div>", unsafe_allow_html=True)

# routing link ke login
q = st.query_params
page = q.get("page", "")
if page == "login":
    st.query_params.clear()
    st.switch_page("pages/1_Login.py")
