import streamlit as st

st.set_page_config(
    page_title="Depo 78",
    page_icon="🛒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# INIT AUTH
if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged_in": False, "user": None}

# LANGSUNG PINDAH KE LOGIN
st.switch_page("pages/1_Login.py")
st.stop()
