# modules/listen_web.py
import streamlit as st
from st_audiorec import st_audiorec
import tempfile
import speech_recognition as sr
import hashlib

def listen_web(show_ui: bool = False, skip_process: bool = False) -> str:
    # Info kecil (opsional)
    if show_ui:
        st.caption("Tekan **Start Recording**, lalu bicara. Tekan **Stop** jika selesai.")

    st.session_state.setdefault("stt_last_hash", None)
    st.session_state.setdefault("stt_last_text", "")

    # Wrapper class untuk CSS (biar tombol Download gampang disembunyikan)
    st.markdown('<div class="depo-voice-recorder">', unsafe_allow_html=True)

    # ✅ recorder UI HARUS tetap dirender
    audio_bytes = st_audiorec()

    st.markdown("</div>", unsafe_allow_html=True)

    # ✅ kalau diminta skip, jangan proses apa-apa (tapi UI tetap tampil)
    if skip_process:
        return ""

    if audio_bytes is None:
        return ""
    if not isinstance(audio_bytes, (bytes, bytearray)) or len(audio_bytes) < 2000:
        return ""

    audio_hash = hashlib.md5(audio_bytes).hexdigest()
    if st.session_state.stt_last_hash == audio_hash:
        return st.session_state.stt_last_text or ""

    st.session_state.stt_last_hash = audio_hash
    st.session_state.stt_last_text = ""

    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        with open(tmp.name, "wb") as f:
            f.write(audio_bytes)

        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp.name) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data, language="id-ID").strip()
        except (sr.UnknownValueError, sr.RequestError):
            text = ""

        if text:
            st.session_state.stt_last_text = text
            return text

        st.session_state.stt_last_text = ""
        return ""

    except Exception:
        st.session_state.stt_last_text = ""
        return ""
