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

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Study Assistant AI", page_icon="🤖")

# --- 2. LOAD ENVIRONMENT & API KEY ---
load_dotenv()
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# --- 3. SESSION STATE & THEME ---
def init_session_state():
    """Initializes session state variables cleanly."""
    defaults = {
        "chat_history": [], "current_page": 0, "subject": "", "study_mode": "❓ Select...",
        "pdf_bytes": None, "num_pages": 0, "theme_light": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def load_css(is_light):
    """Loads comprehensive CSS for a true light/dark theme experience."""
    if not is_light:
        dark_theme_css = """
        <style>
            .stApp { background-color: #0f172a; color: #e2e8f0; }
            .st-emotion-cache-16txtl3 { background-color: #1e293b; } /* Sidebar */
            h1, h2, h3, h4, h5, h6, p, li, .st-emotion-cache-zt5z0s, .st-emotion-cache-1wivap2, .st-emotion-cache-10trblm {
                color: #e2e8f0 !important;
            }
            .st-emotion-cache-1wivap2 { background-color: rgba(59, 130, 246, 0.2) !important; } /* Info box */
        </style>"""
        st.markdown(dark_theme_css, unsafe_allow_html=True)

# --- 4. PROMPTS (From your excellent original code) ---
def get_summary_prompt(subject):
    """Generates the detailed, high-quality prompt for PDF summarization."""
    return f"""
    You are an experienced {subject} teacher who makes learning incredibly easy. Your task is to provide a simple, clear summary of the provided slide image.
    Your summary must:
    1.  **Main Concept:** Explain the core idea in the simplest possible language.
    2.  **Visuals:** If there are any diagrams, charts, or important visuals, describe what they show and why they are important for a student to understand.
    3.  **Key Takeaways:** Use bullet points to list the most critical points a student must remember.
    4.  **Define Terms:** Explain any complex jargon so a beginner can understand.
    Write in a friendly, encouraging tone. Your goal is to make the student say, "Oh, now I get it!"
    """

def get_topic_explanation_prompt(subject, topic):
    """Generates the detailed, student-focused prompt for topic explanations."""
    return f"""
    You are a world-renowned {subject} professor, famous for making topics easy. Create a comprehensive, exam-focused study guide on "{topic}".
    Your explanation must be well-structured, easy to understand, and cover all key concepts, formulas (if any), practical examples, and common mistakes.
    If a visual diagram would significantly help explain a concept, insert a tag like ```A diagram of {topic}```. Use this sparingly and only when necessary.
    """

# --- 5. BACKEND FUNCTIONS (Logic restored from your original code, with caching fix) ---
@st.cache_data(show_spinner=False)
def generate_slide_summary(_subject, _image_pil, _page_number):
    """
    Calls Gemini API for a unique summary for a specific page.
    Uses _page_number to ensure the cache works correctly.
    """
    if not GEMINI_API_KEY:
        st.error("Gemini API key is not set.")
        return None
    try:
        buffered = BytesIO()
        _image_pil.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        prompt = get_summary_prompt(_subject)
        
        # Using chat history for context, as in your original code
        contents = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state.chat_history[-4:]]
        contents.append({
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": img_base64}},
                {"text": prompt}
            ]
        })
        
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": contents},
            timeout=60
        )
        response.raise_for_status()
        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        st.session_state.chat_history.append({"role": "user", "content": f"Summary for page {_page_number}"})
        st.session_state.chat_history.append({"role": "model", "content": reply})
        return reply
    except Exception as e:
        st.error(f"An error occurred with the AI model: {e}", icon="🤖")
        return None

@st.cache_data(show_spinner=False)
def generate_topic_explanation(_subject, _topic):
    """
    Calls Gemini API for a unique explanation for a specific topic.
    Uses _subject and _topic to ensure the cache works correctly.
    """
    if not GEMINI_API_KEY:
        st.error("Gemini API key is not set.")
        return None
    try:
        prompt = get_topic_explanation_prompt(_subject, _topic)
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": contents},
            timeout=90
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        st.error(f"An error occurred with the AI model: {e}", icon="🤖")
        return None

@st.cache_data
def get_pdf_page_image(_pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=_pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=200)
        return Image.open(BytesIO(pix.tobytes("png")))
    except Exception as e:
        st.error(f"Error rendering PDF page: {e}", icon="📄")
        return None

def render_ai_response_with_images(text):
    """Renders AI text and generates images ONLY for topic explanations."""
    image_pattern = r"```(.*?)```"
    parts = re.split(image_pattern, text, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if i % 2 == 1:
            if image_query := part.strip():
                st.image(f"https://source.unsplash.com/1200x600/?{image_query}", caption=f"🖼️ {image_query.capitalize()}", use_container_width=True)
        elif part.strip():
            st.markdown(part)

# --- 6. UI VIEW FUNCTIONS ---
def render_pdf_summary_view():
    st.header("📄 PDF Page Summarizer")
    uploaded_file = st.file_uploader("Upload your PDF document", type=["pdf"], key="pdf_uploader")
    
    if uploaded_file:
        st.session_state.pdf_bytes = uploaded_file.getvalue()
        try:
            reader = PdfReader(BytesIO(st.session_state.pdf_bytes))
            st.session_state.num_pages = len(reader.pages)
        except Exception:
            st.error("This PDF is unreadable. It may be corrupted or password-protected.", icon="❌")
            st.session_state.pdf_bytes, st.session_state.num_pages = None, 0

    if st.session_state.get("pdf_bytes") and st.session_state.get("num_pages", 0) > 0:
        page_num = st.slider("Select a page to analyze:", 1, st.session_state.num_pages, st.session_state.current_page + 1)
        st.session_state.current_page = page_num - 1
        st.divider()

        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.subheader(f"Page {page_num}")
            image = get_pdf_page_image(st.session_state.pdf_bytes, st.session_state.current_page)
            if image: st.image(image, use_container_width=True)
        with col2:
            st.subheader("🤖 AI-Powered Summary")
            if image:
                with st.spinner("AI is analyzing the page..."):
                    summary = generate_slide_summary(st.session_state.subject, image, page_num)
                    if summary: st.markdown(summary)
    elif uploaded_file:
        st.error("The uploaded PDF does not contain any readable pages.", icon="⚠️")

def render_topic_explanation_view():
    st.header("🧠 Comprehensive Topic Explainer")
    with st.container(border=True):
        st.markdown("##### Get a detailed, easy-to-understand explanation on any topic.")
        topic_input = st.text_input("What topic do you want to understand?", placeholder="e.g., Quantum Computing...", label_visibility="collapsed")
        if st.button("🚀 Explain Topic", use_container_width=True, type="primary"):
            if topic_input.strip():
                with st.spinner(f"AI is creating an explanation for '{topic_input}'..."):
                    explanation = generate_topic_explanation(st.session_state.subject, topic_input)
                    if explanation:
                        st.divider()
                        render_ai_response_with_images(explanation)
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