import streamlit as st
import os
from modules.auth_web import login_web

st.set_page_config(
    page_title="Login - Depo 78",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Load CSS terpisah
def load_css(path="assets/styles.css"):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        css_path = os.path.join(base_dir, path)
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass

load_css()

# Session init
if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged_in": False, "user": None}

st.session_state.setdefault("show_pw", False)

# UI
st.markdown("<div class='depo-title'>Selamat Datang di Toko Depo78</div>", unsafe_allow_html=True)
st.markdown("<div class='depo-card'>", unsafe_allow_html=True)

username = st.text_input("Username", key="login_username", placeholder="Masukkan username")

# ====== PASSWORD (ikon mata di DALAM field kanan) ======
st.session_state.setdefault("show_pw", False)

password = st.text_input(
    "Password",
    key="login_password",
    placeholder="Masukkan password",
    type="default" if st.session_state.show_pw else "password",
)

# Render checkbox agar bisa "di-klik" oleh ikon overlay
st.checkbox("show_pw_hidden", key="show_pw")

# Overlay ikon mata di dalam field password (kanan)
st.markdown("""

<script>
(function() {
  const doc = window.parent.document;

  // checkbox show_pw (yang kita render tapi disembunyikan)
  const cb = doc.querySelector('input[type="checkbox"]');
  if (!cb) return;

  // ambil semua text input: Username = pertama, Password = kedua
  const textInputs = doc.querySelectorAll('div[data-testid="stTextInput"]');
  if (!textInputs || textInputs.length < 2) return;

  const pwBox = textInputs[1];

  // pasang ikon kalau belum ada
  if (!pwBox.querySelector('.pw-eye-overlay')) {
    const eye = doc.createElement('div');
    eye.className = 'pw-eye-overlay';
    eye.innerHTML = '👁️';
    eye.onclick = () => cb.click();
    pwBox.appendChild(eye);
  }
})();
</script>
""", unsafe_allow_html=True)

if st.button("Login", use_container_width=True):
    if not username.strip() or not password.strip():
        st.error("Username/password wajib diisi.")
    else:
        ok, user = login_web(username.strip(), password)
        if not ok:
            st.error("Username atau password salah.")
        else:
            st.session_state.auth["is_logged_in"] = True
            st.session_state.auth["user"] = user

            # Redirect berdasarkan role (AMAN karena user sudah ada)
            if user.get("role") == "admin":
                st.switch_page("pages/4_Admin_Dashboard.py")
            else:
                st.switch_page("pages/3_User_Order.py")

st.markdown(
    "<div style='margin-top:10px; text-align:left;'>"
    "<a class='depo-link' href='?page=forgot'>Forgot Password?</a>"
    "</div>",
    unsafe_allow_html=True,
)

col_text, col_btn = st.columns([6, 40], gap="small")

with col_text:
    st.markdown(
        "<div style='margin-top:8px;'>Belum punya akun?</div>",
        unsafe_allow_html=True
    )

with col_btn:
    if st.button("Daftar di sini", key="goto_signup", type="secondary"):
        st.switch_page("pages/2_Signup.py")

st.markdown("</div>", unsafe_allow_html=True)

# Routing link
q = st.query_params
page = q.get("page", "")

if page == "signup":
    st.query_params.clear()
    st.switch_page("pages/2_Signup.py")

if page == "forgot":
    st.query_params.clear()
    st.switch_page("pages/5_Forgot_Password.py")
