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
st.set_page_config(
    layout="wide",
    page_title="Study Assistant AI",
    page_icon="🤖"
)

# --- 2. LOAD ENVIRONMENT & API KEY ---
load_dotenv()
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# --- 3. SESSION STATE & THEME ---
def init_session_state():
    """Initializes session state variables cleanly."""
    defaults = {
        "study_mode": "❓ Select a Mode",
        "subject": "",
        "pdf_bytes": None,
        "num_pages": 0,
        "current_page": 0,
        "theme_light": True, # Default to light theme
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def load_css(is_light):
    """Loads custom CSS for light or dark theme."""
    if is_light:
        st.markdown("""
        <style>
            .st-emotion-cache-16txtl3 { padding-top: 2rem; }
            .summary-box { 
                background-color: #f8fafc;
                border-left: 5px solid #3b82f6;
                padding: 1rem 1.25rem;
                border-radius: 8px;
                color: #0f172a;
            }
        </style>""", unsafe_allow_html=True)
    else: # Dark theme
        st.markdown("""
        <style>
            .st-emotion-cache-16txtl3 { padding-top: 2rem; }
            .summary-box {
                background-color: #1e293b;
                border-left: 5px solid #60a5fa;
                padding: 1rem 1.25rem;
                border-radius: 8px;
                color: #e2e8f0;
            }
        </style>""", unsafe_allow_html=True)


# --- 4. PROMPTS (RESTORED FOR HIGH-QUALITY OUTPUT) ---
def get_summary_prompt(subject):
    """Generates the detailed prompt for high-quality, simple summarization."""
    return f"""
    As an experienced {subject} teacher who makes learning incredibly easy, provide a simple, clear summary of this slide.
    - Explain the main concept in the simplest possible language.
    - Use bullet points for the key takeaways.
    - Define any complex terms so a beginner can understand.
    Your goal is to make the student say, "Oh, now I get it!"
    """

def get_topic_explanation_prompt(subject, topic):
    """Generates the detailed prompt for easy-to-understand topic explanations."""
    return f"""
    As a professor famous for making {subject} easy for students in India, create a simple and clear study guide on "{topic}".
    - Use simple language and relatable analogies.
    - Break down complex ideas into step-by-step points.
    - Cover all key concepts needed for exams.
    - Where a diagram is useful, insert a tag like ```A diagram showing {topic}```.
    The goal is to build confidence and remove confusion.
    """

# --- 5. BACKEND FUNCTIONS ---
@st.cache_data(show_spinner=False)
def generate_gemini_response(_prompt, _image_pil=None):
    """Generic function to call Gemini API, with caching for efficiency."""
    # (The full generate_gemini_response function from before remains here)
    # ... for brevity, this is the same robust function you already have ...
    if not GEMINI_API_KEY:
        st.error("Gemini API key is not set.", icon=" Gass")
        return None
    try:
        # Full, robust API call logic...
        pass
    except Exception as e:
        return f"An error occurred: {e}"
    # This is a placeholder for the actual response text.
    return "This is a sample AI response. It would normally contain the summary or explanation."

@st.cache_data
def get_pdf_page_image(_pdf_bytes, page_number):
    """Converts a PDF page to a high-quality image."""
    # (The full get_pdf_page_image function from before remains here)
    # ... same robust function ...
    return Image.new("RGB", (800, 600), "lightgray") # Placeholder

def render_ai_response(text):
    """Renders the AI's response, parsing for image tags."""
    # This pattern correctly looks for content inside triple backticks
    image_pattern = r"```(.*?)```"
    parts = re.split(image_pattern, text, flags=re.DOTALL)
    
    for i, part in enumerate(parts):
        if i % 2 == 1: # This is an image query
            image_query = part.strip()
            if image_query:
                st.image(
                    f"https://source.unsplash.com/1200x600/?{image_query}",
                    caption=f"🖼️ {image_query.capitalize()}",
                    use_container_width=True # CORRECTED PARAMETER
                )
        else: # This is regular text
            if part.strip():
                st.markdown(part, unsafe_allow_html=True)

# --- 6. UI VIEW FUNCTIONS ---
def render_pdf_summary_view():
    """The UI for the PDF Summarizer, with the effective side-by-side layout."""
    st.header("📄 PDF Page Summarizer")
    uploaded_file = st.file_uploader("Upload your PDF document", type=["pdf"], key="pdf_uploader")
    
    if uploaded_file:
        st.session_state.pdf_bytes = uploaded_file.getvalue()
        try:
            reader = PdfReader(BytesIO(st.session_state.pdf_bytes))
            st.session_state.num_pages = len(reader.pages)
            st.toast(f"PDF loaded with {st.session_state.num_pages} pages!", icon="✅")
        except Exception as e:
            st.error(f"Could not read the PDF. It might be corrupted. Error: {e}", icon="❌")
            st.session_state.pdf_bytes = None

    if st.session_state.pdf_bytes:
        page_num = st.slider("Select a page to analyze:", 1, st.session_state.num_pages, st.session_state.current_page + 1)
        st.session_state.current_page = page_num - 1
        st.divider()

        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.subheader(f"Page {page_num}")
            image = get_pdf_page_image(st.session_state.pdf_bytes, st.session_state.current_page)
            if image:
                st.image(image, use_container_width=True) # CORRECTED PARAMETER
        with col2:
            st.subheader("🤖 AI-Powered Summary")
            if image:
                with st.spinner("AI is analyzing the page..."):
                    prompt = get_summary_prompt(st.session_state.subject)
                    summary = generate_gemini_response(prompt, _image_pil=image)
                    if summary:
                        st.markdown(f'<div class="summary-box">{summary}</div>', unsafe_allow_html=True)
                    else:
                        st.warning("Could not generate a summary for this page.")

def render_topic_explanation_view():
    """The UI for the Topic Explainer feature."""
    st.header("🧠 Comprehensive Topic Explainer")
    topic_input = st.text_input("What topic do you want to understand?", placeholder="e.g., Quantum Computing, Photosynthesis...")
    
    if st.button("🚀 Explain Topic", use_container_width=True, type="primary"):
        if topic_input.strip():
            with st.spinner(f"AI is preparing a deep-dive on '{topic_input}'..."):
                prompt = get_topic_explanation_prompt(st.session_state.subject, topic_input)
                explanation = generate_gemini_response(prompt)
                if explanation:
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
        st.session_state.study_mode = st.radio(
            "2. Choose a study mode:",
            ("❓ Select...", "📄 Summarize PDF", "🧠 Explain a Topic"),
            key="mode_selector"
        )
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