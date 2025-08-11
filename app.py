import os
import base64
import requests
from io import BytesIO
from dotenv import load_dotenv

import streamlit as st
from streamlit import runtime
from streamlit.runtime.scriptrunner import get_script_run_ctx
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
from PIL import Image

# -----------------------------
# ENV & CONFIG
# -----------------------------

# Load environment variables
load_dotenv()

# Get Gemini API Key from secrets (Streamlit Cloud compatible)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("🔑 GEMINI_API_KEY not found in secrets. Please add it to `secrets.toml` or Streamlit Cloud.")
    st.stop()

# Set page config
st.set_page_config(
    layout="wide",
    page_title="📚 Study Assistant",
    page_icon="📚",
    initial_sidebar_state="collapsed"
)

# -----------------------------
# THEME & STYLING
# -----------------------------

# Initialize theme in session state
if "theme" not in st.session_state:
    st.session_state.theme = "light"  # default

def get_theme_colors():
    if st.session_state.theme == "dark":
        return {
            "bg": "#1E1E1E",
            "card_bg": "#2D2D2D",
            "text": "#E0E0E0",
            "subtle_text": "#BBBBBB",
            "accent": "#667EEA",
            "success": "#4CAF50",
            "border": "#444444"
        }
    else:
        return {
            "bg": "#FFFFFF",
            "card_bg": "#F8F9FA",
            "text": "#212529",
            "subtle_text": "#666666",
            "accent": "#667EEA",
            "success": "#4CAF50",
            "border": "#DDDDDD"
        }

# Inject custom CSS with dynamic theme
def inject_theme_css():
    colors = get_theme_colors()
    st.markdown(
        f"""
        <style>
            .main {{ background-color: {colors['bg']}; color: {colors['text']}; }}
            .stApp {{ background-color: {colors['bg']}; }}
            .stTextInput > div > div > input, .stTextInput > div > div > textarea {{
                color: {colors['text']};
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
            }}
            .stButton>button {{
                background-color: {colors['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0.6em 1.2em;
                font-weight: 600;
            }}
            .stSelectbox > div > div {{
                background-color: {colors['card_bg']};
                color: {colors['text']};
            }}
            .stMarkdown, .stText {{ color: {colors['text']}; }}
            .stSpinner > div > div {{ border-top-color: {colors['accent']} !important; }}
            hr {{ border-color: {colors['border']}; }}
            .sidebar .sidebar-content {{ background-color: {colors['bg']}; }}
            code {{ background-color: {colors['card_bg']}; color: {colors['accent']}; }}
        </style>
        """,
        unsafe_allow_html=True
    )

inject_theme_css()

# -----------------------------
# SESSION STATE INIT
# -----------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "subject" not in st.session_state:
    st.session_state.subject = ""
if "study_mode" not in st.session_state:
    st.session_state.study_mode = ""

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def pdf_page_to_image(pdf_bytes, page_number):
    """Convert PDF page to PIL Image."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=120)
        image = Image.open(BytesIO(pix.tobytes("png")))
        doc.close()
        return image
    except Exception as e:
        st.error(f"❌ Error converting PDF page: {str(e)}")
        return None

def generate_summary_prompt(subject):
    return f"""You are an experienced, excellent and great {subject} teacher who is loved by all students because you make {subject} incredibly easy to understand. You have a special talent for creating clear, simple summaries that help students grasp even the most complex {subject} concepts.

Your teaching approach:
- Explain {subject} concepts in the simplest possible language
- Break down complex terms into easy-to-understand explanations
- Use simple examples and analogies related to {subject}
- Highlight key points students must remember
- Write in a friendly, encouraging tone

Task: Provide an easy-to-understand summary of this {subject} slide/page. Focus on:
1. Main concept in simple language
2. Break down difficult terms
3. Key points to remember
4. Simple examples if helpful

Keep it concise, clear, and exam-friendly. Start directly with the summary."""

def generate_topic_explanation_prompt(subject, topic):
    return f"""You are a world-renowned {subject} professor. Explain the topic: "{topic}" in {subject} for a college student preparing for exams.

Provide a comprehensive explanation covering:
1. Definition & Importance
2. Key Concepts & Components
3. Formulas (if applicable)
4. Step-by-Step Processes
5. 2-3 Practical Examples
6. Common Mistakes & Tips
7. Exam Focus Points

Additionally, if there are important diagrams, charts, or visual representations related to this topic:
- Describe them clearly (e.g., 'a diagram showing X vs Y')
- Explain what they represent
- Suggest what the student should draw or visualize

If visuals are relevant, also suggest a Google search query like:
🔍 VISUAL: [search term for image]

Make your explanation so clear and complete that the student feels confident for their exam. Start directly with the explanation."""

def generate_subject_tips(subject):
    tips = {
        "mathematics": f"Hey there, future mathematician! 🔢 {subject} is like solving puzzles. Every problem builds your logical thinking. Don’t rush — practice and patience win. You've got this! 💪",
        "physics": f"Welcome to the amazing world of Physics! 🌟 You're discovering how the universe works. Focus on concepts, not just equations. I believe in you! 🚀",
        "chemistry": f"Get ready to become a chemistry wizard! ⚗️ Every reaction tells a story. Connect the dots, and it becomes exciting. I'm here to help! 🧪✨",
        "biology": f"Welcome to the world of life science! 🌱 Biology is about YOU and all living things. Stay curious — every biologist started like you! 🔬🦋",
        "computer science": f"Welcome, future programmer! 💻 CS is creating with logic. Don't fear bugs — they're lessons. Code your future! 🚀👨‍💻",
        "history": f"Time to travel through time! 🏛️ History is real people’s stories. Focus on connections, not just dates. You're making history too! ⏳"
    }
    subject_lower = subject.lower().strip()
    for key in tips:
        if key in subject_lower:
            return tips[key]
    return f"Hello, brilliant student! 🌟 You're studying {subject} — that takes courage and curiosity. Every expert started where you are. Be patient, ask questions, and celebrate progress. You’ve got what it takes! 💪📚"

# -----------------------------
# GEMINI API CALLS
# -----------------------------

def generate_slide_summary(image_pil, subject):
    try:
        buffered = BytesIO()
        image_pil.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        prompt = generate_summary_prompt(subject)
        parts = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state.chat_history[-4:]]
        parts.append({
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": img_base64}},
                {"text": prompt}
            ]
        })

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": parts},
            timeout=30
        )

        if response.status_code == 200:
            reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            st.session_state.chat_history.append({"role": "model", "content": reply})
            return reply
        else:
            return f"❌ Error: {response.status_code} - {response.text}"

    except requests.exceptions.Timeout:
        return "❌ Request timed out. Please try again."
    except Exception as e:
        return f"❌ Error: {str(e)}"

def generate_topic_explanation(subject, topic):
    try:
        prompt = generate_topic_explanation_prompt(subject, topic)
        parts = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state.chat_history[-2:]]
        parts.append({"role": "user", "parts": [{"text": prompt}]})

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": parts},
            timeout=45
        )

        if response.status_code == 200:
            reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            st.session_state.chat_history.append({"role": "user", "content": f"Explain topic: {topic} in {subject}"})
            st.session_state.chat_history.append({"role": "model", "content": reply})
            return reply
        else:
            return f"❌ Error: {response.status_code} - {response.text}"

    except requests.exceptions.Timeout:
        return "❌ Request timed out. Try a simpler query."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# -----------------------------
# UI: HEADER & SUBJECT INPUT
# -----------------------------

st.markdown("<h1 style='text-align: center;'>📚 Study Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Easy PDF Summaries & Topic Explanations</p>", unsafe_allow_html=True)
st.markdown("---")

# Theme Toggle
col_t1, col_t2 = st.columns([6, 1])
with col_t2:
    if st.button("🌓 Dark Mode" if st.session_state.theme == "light" else "☀️ Light Mode", key="theme_toggle"):
        st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"
        st.rerun()

# Subject Input
st.markdown("### 📖 What subject are you studying today?")
subject_input = st.text_input(
    "Enter your subject:",
    placeholder="e.g., Mathematics, Physics, Computer Science...",
    value=st.session_state.subject,
    help="This helps me tailor explanations to your subject!"
)

if subject_input != st.session_state.subject:
    st.session_state.subject = subject_input
    st.session_state.chat_history = []
    st.session_state.study_mode = ""
    st.rerun()

# -----------------------------
# STUDY MODE SELECTION
# -----------------------------

if st.session_state.subject.strip():
    st.markdown(f"### 🎯 How would you like to study **{st.session_state.subject}** today?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Upload PDF for Page-by-Page Summary", use_container_width=True):
            st.session_state.study_mode = "pdf_summary"
            st.rerun()
    with col2:
        if st.button("🧠 Ask About Specific Topic", use_container_width=True):
            st.session_state.study_mode = "topic_explanation"
            st.rerun()
else:
    st.info("👆 Please enter your subject to begin!")

# -----------------------------
# PDF SUMMARY MODE
# -----------------------------

if st.session_state.study_mode == "pdf_summary" and st.session_state.subject.strip():
    st.markdown(f"### 📄 Upload your **{st.session_state.subject}** PDF")
    uploaded_file = st.file_uploader("Choose your PDF file", type=["pdf"], label_visibility="collapsed")

    if uploaded_file:
        st.success(f"✅ {st.session_state.subject} PDF loaded successfully!")

        try:
            pdf_bytes = uploaded_file.read()
            reader = PdfReader(BytesIO(pdf_bytes))
            num_pages = len(reader.pages)

            selected_page = st.selectbox(
                "Go to slide:",
                options=[f"Slide {i}" for i in range(1, num_pages + 1)],
                index=st.session_state.current_page - 1
            )
            page_num = int(selected_page.split()[-1])
            st.session_state.current_page = page_num

            col1, col2 = st.columns([1, 1])

            with col1:
                st.subheader(f"📄 Slide {page_num}")
                image = pdf_page_to_image(pdf_bytes, page_num - 1)
                if image:
                    st.image(image, use_container_width=True)
                else:
                    st.error("Could not render this page.")

                # Navigation
                nav1, nav2, nav3 = st.columns([1, 2, 1])
                with nav1:
                    if st.button("⬅️ Previous", disabled=(page_num <= 1)):
                        st.session_state.current_page = max(1, page_num - 1)
                        st.rerun()
                with nav2:
                    st.markdown(f"<p style='text-align:center;margin:10px 0;'>Page {page_num} of {num_pages}</p>", unsafe_allow_html=True)
                with nav3:
                    if st.button("Next ➡️", disabled=(page_num >= num_pages)):
                        st.session_state.current_page = min(num_pages, page_num + 1)
                        st.rerun()

            with col2:
                st.subheader(f"📝 Easy {st.session_state.subject} Summary")
                if image:
                    with st.spinner(f"Creating summary for Slide {page_num}..."):
                        summary = generate_slide_summary(image, st.session_state.subject)

                    colors = get_theme_colors()
                    st.markdown(
                        f"""
                        <div style="
                            background-color: {colors['card_bg']};
                            padding: 1.5rem;
                            border-radius: 15px;
                            border-left: 5px solid {colors['success']};
                            color: {colors['text']};
                            font-size: 16px;
                            line-height: 1.7;
                        ">
                            <strong>📚 Summary:</strong><br>{summary.replace(chr(10), '<br>')}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.error("Cannot generate summary — image not available.")

            # Progress bar
            st.markdown("---")
            progress = page_num / num_pages
            st.progress(progress, text=f"Progress: {int(progress*100)}%")

        except Exception as e:
            st.error(f"❌ Error processing PDF: {str(e)}")

# -----------------------------
# TOPIC EXPLANATION MODE
# -----------------------------

elif st.session_state.study_mode == "topic_explanation" and st.session_state.subject.strip():
    st.markdown(f"### 🧠 Ask About Any **{st.session_state.subject}** Topic")
    st.markdown(f"<p style='color: #666;'>Get comprehensive, exam-ready explanations with visual suggestions!</p>", unsafe_allow_html=True)

    topic_input = st.text_input(
        f"What {st.session_state.subject} topic would you like explained?",
        placeholder="e.g., Photosynthesis, Newton's Laws, Neural Networks...",
        help="I'll explain concepts, formulas, and suggest helpful visuals!"
    )

    if st.button("🚀 Get Comprehensive Explanation", disabled=not topic_input.strip()):
        with st.spinner(f"Preparing explanation for '{topic_input}'..."):
            explanation = generate_topic_explanation(st.session_state.subject, topic_input)

        colors = get_theme_colors()
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, {colors['accent']} 0%, #764ba2 100%);
                padding: 3px;
                border-radius: 20px;
                margin: 20px 0;
            ">
                <div style="
                    background-color: {colors['card_bg']};
                    padding: 25px;
                    border-radius: 17px;
                    color: {colors['text']};
                    font-size: 16px;
                    line-height: 1.8;
                ">
                    <h3 style="color: {colors['accent']}; text-align: center;">🎓 {topic_input} in {st.session_state.subject}</h3>
                    <div style="white-space: pre-line; color: {colors['text']};">
                        {explanation.replace('🔍 VISUAL:', '<br><br><strong>🖼️ Suggested Visual:</strong>')}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("### 💡 Want to learn more?")
        st.info(f"Ask about another {st.session_state.subject} topic — I’ll break it down with clarity and visuals!")

# -----------------------------
# MOTIVATIONAL TIP
# -----------------------------

if st.session_state.study_mode and st.session_state.subject.strip():
    tip = generate_subject_tips(st.session_state.subject)
    colors = get_theme_colors()
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {colors['accent']} 0%, #764ba2 100%);
            padding: 2px;
            border-radius: 15px;
            margin: 25px 0 15px 0;
        ">
            <div style="
                background-color: {colors['card_bg']};
                padding: 20px;
                border-radius: 13px;
                color: {colors['text']};
            ">
                <strong>💪 Message from Your {st.session_state.subject} Teacher</strong><br>
                <em style="color: {colors['subtle_text']};">{tip}</em>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# BACK TO MODE SELECTION
# -----------------------------

if st.session_state.study_mode:
    st.markdown("---")
    if st.button("🔄 Choose Different Study Mode"):
        st.session_state.study_mode = ""
        st.rerun()

# -----------------------------
# FOOTER
# -----------------------------

st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666; font-size: 14px;">
        <p>📚 Study Assistant | Made with ❤️ for students</p>
        <p><small>Upload PDFs or ask about topics — I’ll help you understand everything clearly.</small></p>
    </div>
    """,
    unsafe_allow_html=True
)