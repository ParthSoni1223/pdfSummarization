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

# --- PAGE CONFIGURATION ---
# Set page config at the very top, and only once.
st.set_page_config(layout="wide", page_title="🎓 Study Assistant", page_icon="📚")

# --- LOAD API KEY ---
# It's good practice to handle this early on.
load_dotenv()
# Use st.secrets for deployment, but have a fallback for local development.
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# --- SESSION STATE INITIALIZATION ---
# A function to keep initialization clean.
def init_session_state():
    """Initializes session state variables if they don't exist."""
    defaults = {
        "chat_history": [],
        "current_page": 0,
        "subject": "",
        "study_mode": "",
        "pdf_bytes": None,
        "num_pages": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- PROMPT ENGINEERING ---
# Consolidating all prompts in one area for easy management.

def get_summary_prompt(subject):
    """Generates a subject-specific prompt for summarizing a PDF page."""
    return f"""
    You are a world-class {subject} educator, renowned for making complex topics simple.
    Your task is to provide a clear, concise, and easy-to-understand summary of the provided slide image.

    Your summary must:
    1.  **Main Concept:** Start with a simple, one-sentence explanation of the page's core idea.
    2.  **Key Points:** Use bullet points to highlight the most critical information students must remember.
    3.  **Simple Explanations:** Define any jargon or complex terms in plain language.
    4.  **Tone:** Write in a friendly, encouraging, and supportive tone.

    Analyze the image and provide the summary directly. Do not add any introductory or concluding phrases.
    """

def get_topic_explanation_prompt(subject, topic):
    """Generates a detailed, exam-focused prompt for explaining a topic."""
    return f"""
    You are a distinguished {subject} professor creating an ultimate exam study guide for college students.
    Your explanation must be comprehensive, clear, and structured for deep understanding and high exam scores.

    **Topic to Explain:** "{topic}"

    **Instructions:**
    Provide a detailed explanation covering the following sections. Use markdown for formatting (bolding, lists).

    ### 1. Introduction & Core Concept
    - What is '{topic}'? Define it clearly.
    - Why is it important in the field of {subject}?

    ### 2. Key Principles & Mechanisms
    - Break down the fundamental components or theories.
    - Explain any technical terms in simple language.

    ### 3. Important Formulas or Equations (if applicable)
    - List the essential formulas.
    - Briefly explain each variable.

    ### 4. Step-by-Step Process or Application (if applicable)
    - Outline any relevant processes in a numbered list.

    ### 5. Practical Examples
    - Provide 1-2 clear, real-world or hypothetical examples to illustrate the concept.
    
    ### 6. Visual Aid Descriptions
    - **Crucially, where a diagram or visual would be helpful, insert a placeholder tag in the format ``.** For example: `` or ``. This helps visualize the concept.
    
    ### 7. Exam Focus Points & Common Mistakes
    - What are the most tested aspects of this topic?
    - What common pitfalls should students avoid?

    Structure your response logically. Start directly with the explanation.
    """

# --- API & UTILITY FUNCTIONS ---

@st.cache_data(show_spinner=False)
def generate_gemini_response(_prompt, _image_pil=None, _chat_history=None):
    """
    Generic function to call Gemini API. Caches the result.
    Using _ on args tells Streamlit's caching to hash the function arguments by value.
    """
    if not GEMINI_API_KEY:
        st.error("Gemini API key is not set. Please add it to your environment or Streamlit secrets.")
        return None

    try:
        headers = {"Content-Type": "application/json"}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        parts = []
        if _image_pil:
            buffered = BytesIO()
            _image_pil.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            parts.append({"inline_data": {"mime_type": "image/png", "data": img_base64}})
        
        parts.append({"text": _prompt})
        
        # Build contents with chat history
        contents = []
        if _chat_history:
             for message in _chat_history:
                 # Ensure correct role mapping
                 role = "user" if message["role"] == "user" else "model"
                 contents.append({"role": role, "parts": [{"text": message["content"]}]})
        
        # Add the current prompt
        contents.append({"role": "user", "parts": parts})

        response = requests.post(
            url, headers=headers, json={"contents": contents}, timeout=60
        )
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        
        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return reply

    except requests.exceptions.Timeout:
        st.error("API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}. Check your connection and API key.")
    except (KeyError, IndexError) as e:
        st.error(f"Failed to parse API response. The response might be empty or malformed. Details: {response.text}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
    
    return None

@st.cache_data
def get_pdf_page_image(_pdf_bytes, page_number):
    """Converts a specific page of a PDF bytes stream to a PIL Image. Caches the result."""
    try:
        doc = fitz.open(stream=_pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=150)  # Increased DPI slightly for better clarity
        image = Image.open(BytesIO(pix.tobytes("png")))
        doc.close()
        return image
    except Exception as e:
        st.error(f"Error converting PDF page {page_number + 1}: {e}")
        return None

def render_response(text):
    """
    Renders the Gemini response, replacing image placeholders with st.image calls.
    This is the key to solving the image generation request.
    """
    # Use html.escape to prevent Markdown/HTML injection from the text itself.
    # We will handle formatting safely.
    safe_text = html.escape(text)
    
    # Regex to find our image tags:     image_pattern = r"\"
    parts = re.split(image_pattern, safe_text)
    
    # Pre-wrap ensures newlines are respected without manual <br> tags
    st.markdown(
        f"""
        <div class="response-container">
            {parts[0]}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            image_query = parts[i]
            text_after = parts[i+1]
            st.image(f"https://source.unsplash.com/800x400/?{image_query}", caption=f"🖼️ {image_query.capitalize()}")
            st.markdown(
                f"""
                <div class="response-container">
                    {text_after}
                </div>
                """,
                unsafe_allow_html=True
            )

# --- UI COMPONENTS ---

def display_pdf_summary_view():
    """UI for the PDF summarizer mode."""
    st.markdown(f"### 📄 Upload your **{st.session_state.subject}** PDF")
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

    if uploaded_file:
        st.session_state.pdf_bytes = uploaded_file.getvalue()
        reader = PdfReader(BytesIO(st.session_state.pdf_bytes))
        st.session_state.num_pages = len(reader.pages)
    
    if st.session_state.pdf_bytes:
        st.success(f"✅ PDF loaded with {st.session_state.num_pages} pages.")
        
        # Page selection slider is more intuitive for PDFs
        page_num_selected = st.slider(
            "Select a page to summarize:", 
            1, 
            st.session_state.num_pages, 
            st.session_state.current_page + 1
        )
        st.session_state.current_page = page_num_selected - 1

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"📄 Page {st.session_state.current_page + 1} of {st.session_state.num_pages}")
            image = get_pdf_page_image(st.session_state.pdf_bytes, st.session_state.current_page)
            if image:
                st.image(image, use_container_width=True)
            else:
                st.error("Could not display this page.")
        
        with col2:
            st.subheader(f"📝 Easy {st.session_state.subject} Summary")
            if image:
                with st.spinner(f"AI is summarizing page {st.session_state.current_page + 1}..."):
                    prompt = get_summary_prompt(st.session_state.subject)
                    # Pass only the last 2 messages for context to keep it relevant
                    history_context = st.session_state.chat_history[-2:]
                    summary = generate_gemini_response(prompt, _image_pil=image, _chat_history=history_context)
                
                if summary:
                    # Update chat history
                    st.session_state.chat_history.append({"role": "user", "content": f"Summarize page {st.session_state.current_page + 1}"})
                    st.session_state.chat_history.append({"role": "model", "content": summary})
                    
                    st.markdown(f'<div class="summary-box">{summary}</div>', unsafe_allow_html=True)
                else:
                    st.warning("Could not generate summary for this page.")

def display_topic_explanation_view():
    """UI for the Topic Explainer mode."""
    st.markdown(f"### 🧠 Ask About Any **{st.session_state.subject}** Topic")
    st.markdown(f"Get a comprehensive, exam-focused explanation with visual aids.")

    topic_input = st.text_input(
        f"Enter a {st.session_state.subject} topic:",
        placeholder="e.g., Photosynthesis, Quantum Mechanics, Machine Learning...",
    )

    if st.button("🚀 Explain Topic", disabled=not topic_input.strip()):
        with st.spinner(f"AI is preparing a deep-dive on '{topic_input}'..."):
            prompt = get_topic_explanation_prompt(st.session_state.subject, topic_input)
            explanation = generate_gemini_response(prompt)
        
        if explanation:
            # Update chat history
            st.session_state.chat_history.append({"role": "user", "content": f"Explain: {topic_input}"})
            st.session_state.chat_history.append({"role": "model", "content": explanation})
            
            # This custom function renders the response with images
            render_response(explanation)
        else:
            st.error("Failed to generate an explanation. Please try a different topic or try again.")


# --- MAIN APP LOGIC ---

# Call session state init once
init_session_state()

# Custom CSS for a cleaner look
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background-color: #f0f2f6;
    }
    /* Summary box styling */
    .summary-box {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1E90FF;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        font-size: 16px;
        line-height: 1.6;
        white-space: pre-wrap; /* Respects newlines from the model output */
    }
    /* Topic explanation container styling */
    .response-container {
        background-color: #ffffff;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem; /* Space between text blocks */
        font-size: 17px;
        line-height: 1.7;
        color: #333;
        white-space: pre-wrap; /* This is safer than replacing \n with <br> */
    }
    /* Add some space for the image caption */
    .stImage > figcaption {
        margin-top: 8px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎓 Study Assistant")
st.markdown("Your personal AI tutor for PDF summaries and deep topic explanations.")

st.markdown("---")

# --- Step 1: Subject Selection ---
st.markdown("### 📖 Step 1: What are you studying?")
subject_input = st.text_input(
    "Enter a subject to tailor the AI's expertise:",
    placeholder="e.g., Biology, Computer Science, Economics...",
    value=st.session_state.subject,
    help="Providing a subject helps the AI give you more accurate and relevant answers."
)

if subject_input != st.session_state.subject:
    st.session_state.subject = subject_input
    # Reset downstream state if subject changes
    st.session_state.study_mode = ""
    st.session_state.chat_history = []
    st.rerun()

# --- Step 2: Study Mode Selection ---
if st.session_state.subject.strip():
    st.markdown(f"### 🎯 Step 2: How do you want to study **{st.session_state.subject}**?")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Summarize my PDF", use_container_width=True, type="primary" if st.session_state.study_mode != "topic_explanation" else "secondary"):
            st.session_state.study_mode = "pdf_summary"
            st.rerun()
    with col2:
        if st.button("🧠 Explain a Topic", use_container_width=True, type="primary" if st.session_state.study_mode == "topic_explanation" else "secondary"):
            st.session_state.study_mode = "topic_explanation"
            st.rerun()
            
    st.markdown("---")

    # --- Step 3: Main Interaction ---
    if st.session_state.study_mode == "pdf_summary":
        display_pdf_summary_view()
    elif st.session_state.study_mode == "topic_explanation":
        display_topic_explanation_view()

# --- FOOTER ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #555; font-size: 14px;">
        <p><b>Study Assistant AI</b> | Built with Gemini & Streamlit</p>
        <p><small>Making exam preparation simpler and more effective.</small></p>
    </div>
    """,
    unsafe_allow_html=True
)
