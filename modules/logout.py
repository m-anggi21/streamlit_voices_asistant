import streamlit as st

def do_logout(redirect_page="app.py"):
    """
    Logout global:
    - hapus auth
    - reset session penting
    - redirect ke halaman login
    """
    # hapus auth
    st.session_state.pop("auth", None)

    # optional: bersihkan state lain jika perlu
    for k in list(st.session_state.keys()):
        if k not in ("_stcore",):
            st.session_state.pop(k, None)

    st.session_state["_force_logout"] = True
