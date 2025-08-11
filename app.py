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
    layout="centered",
    page_title="Study Assistant AI",
    page_icon="🤖"
)

# --- 2. LOAD ENVIRONMENT & API KEY ---
load_dotenv()
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# --- 3. SESSION STATE ---
def init_session_state():
    """Initializes session state variables cleanly."""
    if "study_mode" not in st.session_state:
        st.session_state.study_mode = "❓ Select a Mode"
    if "subject" not in st.session_state:
        st.session_state.subject = ""
    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None
    if "num_pages" not in st.session_state:
        st.session_state.num_pages = 0
    if "current_page" not in st.session_state:
        st.session_state.current_page = 0

# --- 4. PROMPT & API FUNCTIONS (BACKEND LOGIC) ---
def get_summary_prompt(subject):
    """Generates a prompt focused on simple, clear summarization."""
    return f"""
    As a world-class {subject} educator focused on making topics easy, provide a simple summary of this slide. 
    Explain the main concept in plain language and list the key points a student absolutely must remember.
    """

def get_topic_explanation_prompt(subject, topic):
    """Generates a prompt for a simple, yet comprehensive topic explanation."""
    return f"""
    As a distinguished {subject} professor explaining things to a student in India, create a simple and easy-to-understand study guide on "{topic}".
    - Use clear, simple language and analogies.
    - Cover the core concepts and key principles step-by-step.
    - Where a diagram is useful, insert a tag like ```diagram of a relevant diagram```.
    - The goal is clarity and confidence, not complex jargon.
    """

@st.cache_data(show_spinner=False)
def generate_gemini_response(_prompt, _image_pil=None):
    """Generic function to call Gemini API, with caching for efficiency."""
    if not GEMINI_API_KEY:
        st.error("Gemini API key is not set. Please add it to your secrets.", icon=" Gass")
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
    except requests.exceptions.Timeout:
        st.error("API request timed out. Please try again.", icon="⏱️")
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}", icon="🌐")
    except (KeyError, IndexError):
        st.error("Failed to parse API response. The model may be unavailable.", icon="🔧")
    return None

# --- 5. UTILITY FUNCTIONS ---
@st.cache_data
def get_pdf_page_image(_pdf_bytes, page_number):
    """Converts a PDF page to a high-quality image."""
    try:
        doc = fitz.open(stream=_pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=200) # Higher DPI for clarity
        return Image.open(BytesIO(pix.tobytes("png")))
    except Exception as e:
        st.error(f"Error reading PDF page: {e}", icon="📄")
        return None

def render_ai_response(text):
    """Renders the AI's response, parsing for image tags."""
    # This pattern correctly looks for content inside triple backticks
    image_pattern = r"```(.*?)```"
    parts = re.split(image_pattern, text, flags=re.DOTALL)
    
    for i, part in enumerate(parts):
        # The content inside the backticks is always at an odd index (1, 3, 5...)
        if i % 2 == 1:
            image_query = part.strip()
            if image_query:
                st.image(
                    f"https://source.unsplash.com/1200x600/?{image_query}",
                    caption=f"🖼️ {image_query.capitalize()}",
                    use_column_width=True
                )
        # The regular text is at an even index (0, 2, 4...)
        else:
            if part.strip():
                st.markdown(part)
    
    for i, part in enumerate(parts):
        if i % 2 == 1: # This is an image query
            image_query = part.strip()
            if image_query:
                st.image(f"https://source.unsplash.com/1200x600/?{image_query}", caption=f"🖼️ {image_query.capitalize()}", use_column_width=True)
        else: # This is regular text
            if part.strip():
                st.markdown(part)

# --- 6. UI VIEW FUNCTIONS ---
def render_pdf_summary_view():
    """The UI for the PDF Summarizer feature."""
    st.subheader("📄 PDF Page Summarizer")
    uploaded_file = st.file_uploader("Upload your PDF document", type=["pdf"], key="pdf_uploader")
    
    if uploaded_file:
        st.session_state.pdf_bytes = uploaded_file.getvalue()
        try:
            reader = PdfReader(BytesIO(st.session_state.pdf_bytes))
            st.session_state.num_pages = len(reader.pages)
        except Exception:
            st.error("Could not read the PDF file. It might be corrupted.", icon="❌")
            st.session_state.pdf_bytes = None

    if st.session_state.pdf_bytes:
        page_num = st.slider("Select a page:", 1, st.session_state.num_pages, st.session_state.current_page + 1)
        st.session_state.current_page = page_num - 1
        
        image = get_pdf_page_image(st.session_state.pdf_bytes, st.session_state.current_page)
        if image:
            col1, col2 = st.columns(2)
            with col1:
                st.image(image, caption=f"Page {page_num}", use_column_width=True)
            with col2:
                with st.spinner("AI is analyzing the page..."):
                    prompt = get_summary_prompt(st.session_state.subject)
                    summary = generate_gemini_response(prompt, _image_pil=image)
                    if summary:
                        st.markdown(summary)
                    else:
                        st.warning("Could not generate a summary for this page.")

def render_topic_explanation_view():
    """The UI for the Topic Explainer feature."""
    st.subheader("🧠 Comprehensive Topic Explainer")
    topic_input = st.text_input("What topic do you want to understand?", placeholder="e.g., Quantum Computing, Photosynthesis...")
    
    if st.button("🚀 Explain Topic", use_container_width=True, type="primary"):
        if not topic_input.strip():
            st.warning("Please enter a topic.", icon="✍️")
        else:
            with st.spinner(f"AI is preparing a deep-dive on '{topic_input}'..."):
                prompt = get_topic_explanation_prompt(st.session_state.subject, topic_input)
                explanation = generate_gemini_response(prompt)
                if explanation:
                    render_ai_response(explanation)
                else:
                    st.error("Failed to generate an explanation. Please try again.")

def render_welcome_view():
    """The initial welcome screen."""
    st.subheader("Welcome to Your AI Study Assistant!")
    st.write("Please select your subject in the sidebar to get started.")
    st.info("Choose a study mode after selecting your subject.", icon="ℹ️")

# --- 7. MAIN APP ---
def main():
    """Main function to run the Streamlit app."""
    init_session_state()
    
    # --- Sidebar for Controls ---
    with st.sidebar:
        st.title("🤖 Study Assistant")
        st.write("---")
        
        st.session_state.subject = st.text_input(
            "What's your subject?",
            value=st.session_state.subject,
            placeholder="e.g., Biology, Physics..."
        )
        
        if st.session_state.subject:
            st.session_state.study_mode = st.radio(
                f"How to study **{st.session_state.subject}**?",
                ("❓ Select a Mode", "📄 Summarize PDF", "🧠 Explain a Topic"),
                key="mode_selector"
            )
        st.write("---")
        st.info("Built with Gemini & Streamlit")

    # --- Main Content Area ---
    st.title(f"🎓 {st.session_state.subject or 'Study'} Central")
    
    if st.session_state.study_mode == "📄 Summarize PDF":
        render_pdf_summary_view()
    elif st.session_state.study_mode == "🧠 Explain a Topic":
        render_topic_explanation_view()
    else:
        render_welcome_view()

if __name__ == "__main__":
    main()