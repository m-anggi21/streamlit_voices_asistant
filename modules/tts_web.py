# modules/tts_web.py
import base64
import streamlit as st
from io import BytesIO

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except Exception:
    GTTS_AVAILABLE = False


def _init_tts_state():
    st.session_state.setdefault("tts_queue", [])


def tts_reset_queue():
    """Panggil ini sebelum mulai proses perintah user (sekali per command)."""
    _init_tts_state()
    st.session_state.tts_queue = []


def speak(text: str, lang: str = "id"):
    """
    ENQUEUE text ke antrian TTS.
    (Tidak render audio di sini)
    """
    if not text or not GTTS_AVAILABLE:
        return
    _init_tts_state()
    st.session_state.tts_queue.append((text, lang))


def _tts_to_b64(text: str, lang: str) -> str:
    lang_code = "id" if (lang or "id").lower().startswith("id") else "en"
    fp = BytesIO()
    tts = gTTS(text=text, lang=lang_code)
    tts.write_to_fp(fp)
    fp.seek(0)
    return base64.b64encode(fp.read()).decode("utf-8")


def tts_flush(show_controls: bool = True):
    """
    Render hanya 1 audio dari queue.
    Setelah audio selesai, halaman reload -> flush akan render audio berikutnya.
    """
    _init_tts_state()

    if not st.session_state.tts_queue:
        return

    text, lang = st.session_state.tts_queue.pop(0)

    try:
        b64 = _tts_to_b64(text, lang)
        controls = "controls" if show_controls else ""

        html = f"""
        <audio {controls} autoplay playsinline
               onended="window.location.reload();"
               src="data:audio/mp3;base64,{b64}">
        </audio>
        """

        # penting: jangan pakai st.audio di sini, karena autoplay & queue lebih stabil pakai HTML
        st.markdown(html, unsafe_allow_html=True)

    except Exception as e:
        st.warning(f"TTS error: {e}")
