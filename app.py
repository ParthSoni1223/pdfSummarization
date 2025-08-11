import os
import streamlit as st
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import base64
import requests
from PIL import Image
from io import BytesIO
import fitz  # PyMuPDF
import re
import html

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Study Assistant AI", page_icon="🤖")

# --- 2. LOAD ENVIRONMENT & API KEY ---
load_dotenv()
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# --- 3. SESSION STATE & THEME ---
def init_session_state():
    defaults = {
        "study_mode": "❓ Select...", "subject": "", "pdf_bytes": None,
        "num_pages": 0, "current_page": 0, "theme_light": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def load_css(is_light):
    """Loads a comprehensive and polished CSS for a state-of-the-art UI."""
    # Base styles applicable to both themes
    st.markdown("""
        <style>
            /* Main button style */
            .stButton>button {
                border-radius: 25px;
                border: 2px solid #3b82f6;
                padding: 10px 20px;
                font-weight: bold;
                transition: all 0.3s ease-in-out;
            }
            /* Text input style */
            .stTextInput>div>div>input {
                border-radius: 15px;
                padding: 12px;
                border: 2px solid #e5e7eb;
                transition: all 0.3s ease-in-out;
            }
            .stTextInput>div>div>input:focus {
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
            }
        </style>
    """, unsafe_allow_html=True)

    if not is_light: # Inject dark theme styles
        dark_theme_css = """
        <style>
            /* Base dark theme overrides */
            .stApp { background-color: #0f172a; color: #cbd5e1; }
            .st-emotion-cache-16txtl3 { background-color: #1e293b; } /* Sidebar */
            h1, h2, h3, h4, h5, h6 { color: #f1f5f9 !important; }
            p, li, .st-emotion-cache-zt5z0s, .st-emotion-cache-1wivap2 { color: #cbd5e1 !important; }

            /* Dark theme for widgets */
            .stTextInput>div>div>input {
                background-color: #334155;
                color: #f1f5f9;
                border-color: #475569;
            }
            .stTextInput>div>div>input::placeholder {
                color: #94a3b8;
            }
            .st-emotion-cache-1wivap2 { background-color: rgba(59, 130, 246, 0.2) !important; } /* Info box */
            
            /* Custom summary box */
            .summary-box { background-color: #1e293b; border-left: 5px solid #60a5fa; padding: 1rem 1.25rem; border-radius: 8px; }
        </style>"""
        st.markdown(dark_theme_css, unsafe_allow_html=True)

# --- 4. PROMPTS (High-Quality versions) ---
def get_summary_prompt(subject):
    return f"""As an experienced {subject} teacher making complex topics simple, provide a clear summary of this slide. 1. **Main Concept:** Explain the core idea in simple language. 2. **Visuals:** If there are any diagrams, describe what they show. 3. **Key Takeaways:** Use bullet points for critical points. 4. **Define Terms:** Explain any complex jargon. Your goal is maximum clarity."""

def get_topic_explanation_prompt(subject, topic):
    return f"""As a professor making {subject} easy for college students, create a comprehensive study guide on "{topic}". Use simple language, analogies, and step-by-step points. Where a diagram is useful, insert a tag like ```A diagram of {topic}```. The goal is clarity and confidence."""

# --- 5. BACKEND FUNCTIONS (No changes needed here) ---
@st.cache_data(show_spinner=False)
def generate_gemini_response(_prompt, _image_pil=None, _page_number=None):
    # (The robust generate_gemini_response function remains here)
    if not GEMINI_API_KEY:
        st.error("Gemini API key is not set.", icon=" Gass")
        return None
    try:
        headers = {"Content-Type": "application/json"}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        parts = [{"text": _prompt}]
        if _image_pil:
            buffered = BytesIO()
            _image_pil.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            parts.insert(0, {"inline_data": {"mime_type": "image/png", "data": img_base64}})
        contents = {"contents": [{"role": "user", "parts": parts}]}
        response = requests.post(url, headers=headers, json=contents, timeout=60)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        st.error(f"An error occurred with the AI model: {e}", icon="🤖")
    return None

@st.cache_data
def get_pdf_page_image(_pdf_bytes, page_number):
    # (The robust get_pdf_page_image function remains here)
    try:
        doc = fitz.open(stream=_pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=200)
        return Image.open(BytesIO(pix.tobytes("png")))
    except Exception as e:
        st.error(f"Error rendering PDF page: {e}", icon="📄")
    return None

def render_ai_response(text):
    image_pattern = r"```(.*?)```"
    parts = re.split(image_pattern, text, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if i % 2 == 1:
            if image_query := part.strip():
                st.image(f"https://source.unsplash.com/1200x600/?{image_query}", caption=f"🖼️ {image_query.capitalize()}", use_container_width=True)
        elif part.strip():
            st.markdown(part, unsafe_allow_html=True)

# --- 6. UI VIEW FUNCTIONS (With UI/UX Enhancements) ---
def render_pdf_summary_view():
    st.header("📄 PDF Page Summarizer")
    # (This function is already robust, no changes needed)
    uploaded_file = st.file_uploader("Upload your PDF document", type=["pdf"], key="pdf_uploader")
    if uploaded_file:
        st.session_state.pdf_bytes = uploaded_file.getvalue()
        try:
            reader = PdfReader(BytesIO(st.session_state.pdf_bytes))
            st.session_state.num_pages = len(reader.pages)
        except Exception:
            st.error("This PDF is unreadable. It may be corrupted or password-protected.", icon="❌")
            st.session_state.pdf_bytes = None
            st.session_state.num_pages = 0

    if st.session_state.get("pdf_bytes") and st.session_state.get("num_pages", 0) > 0:
        page_num = st.slider("Select a page to analyze:", 1, st.session_state.num_pages, st.session_state.current_page + 1)
        st.session_state.current_page = page_num - 1
        st.divider()
        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.subheader(f"Page {page_num}")
            image = get_pdf_page_image(st.session_state.pdf_bytes, st.session_state.current_page)
            if image:
                st.image(image, use_container_width=True)
        with col2:
            st.subheader("🤖 AI-Powered Summary")
            if image:
                with st.spinner("AI is analyzing the page..."):
                    prompt = get_summary_prompt(st.session_state.subject)
                    summary = generate_gemini_response(prompt, _image_pil=image, _page_number=page_num)
                    if summary:
                        st.markdown(f'<div class="summary-box">{summary}</div>', unsafe_allow_html=True)

def render_topic_explanation_view():
    """The UI for Topic Explainer, upgraded with a "card" layout."""
    with st.container(border=True):
        st.markdown("### 🧠 Comprehensive Topic Explainer")
        st.write("Get a detailed, easy-to-understand explanation on any topic.")
        
        topic_input = st.text_input(
            "What topic do you want to understand?",
            placeholder="e.g., Quantum Computing, Photosynthesis...",
            label_visibility="collapsed"
        )
        
        if st.button("🚀 Explain Topic", use_container_width=True, type="primary"):
            if topic_input.strip():
                with st.spinner(f"AI is preparing a deep-dive on '{topic_input}'..."):
                    prompt = get_topic_explanation_prompt(st.session_state.subject, topic_input)
                    explanation = generate_gemini_response(prompt)
                    if explanation:
                        st.divider()
                        render_ai_response(explanation)
            else:
                st.warning("Please enter a topic to explain.", icon="✍️")

# --- 7. MAIN APP ---
init_session_state()

with st.sidebar:
    st.title("⚙️ Controls")
    st.divider()
    st.session_state.theme_light = st.toggle("Toggle Theme", value=st.session_state.theme_light, help="Switch between light and dark modes.")
    st.divider()
    st.session_state.subject = st.text_input("1. What's your subject?", value=st.session_state.subject)
    if st.session_state.subject:
        st.session_state.study_mode = st.radio("2. Choose a study mode:", ("❓ Select...", "📄 Summarize PDF", "🧠 Explain a Topic"), key="mode_selector")
    st.divider()
    st.info("Built with Gemini & Streamlit")

load_css(st.session_state.theme_light)

st.title(f"🎓 {st.session_state.subject or 'Study'} Assistant AI")

if st.session_state.study_mode == "📄 Summarize PDF":
    render_pdf_summary_view()
elif st.session_state.study_mode == "🧠 Explain a Topic":
    render_topic_explanation_view()
else:
    st.info("Select your subject and a study mode from the sidebar to begin!", icon="👈")