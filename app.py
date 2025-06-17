import os
import streamlit as st
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import base64
import requests
from PIL import Image
from io import BytesIO
# from pdf2image import convert_from_bytes
from streamlit_javascript import st_javascript
import fitz

# Load API key
load_dotenv()
GEMINI_API_KEY = "AIzaSyDktmzdFPVFY_7ph7-aP_AlQ4Huy4Nnn6I"  # Replace with your actual API key

st.set_page_config(layout="wide")
st.title("📚 Study Assistant: Slide-by-Slide PDF Explanation")

# Capture arrow key event
js_event = st_javascript("""
new Promise((resolve) => {
    document.addEventListener("keydown", function(event) {
        if (event.key === "ArrowRight") {
            resolve("next");
        } else if (event.key === "ArrowLeft") {
            resolve("prev");
        }
    });
});
""")

# Session state init
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "subject" not in st.session_state:
    st.session_state.subject = ""

# Subject input section
st.markdown("### 📖 Before we begin, tell us what you're studying!")
subject_input = st.text_input(
    "What subject are you going to study today?",
    placeholder="e.g., Mathematics, Physics, Computer Science, Biology, History...",
    value=st.session_state.subject,
    help="This helps me tailor my explanations specifically for your subject!"
)

# Update session state when subject changes
if subject_input != st.session_state.subject:
    st.session_state.subject = subject_input
    # Reset chat history when subject changes to avoid context mixing
    st.session_state.chat_history = []

# Upload PDF (only show if subject is entered)
uploaded_file = None
if st.session_state.subject.strip():
    st.markdown(f"### 📄 Great! Now upload your **{st.session_state.subject}** PDF")
    uploaded_file = st.file_uploader("Upload your PDF notes/slides", type=["pdf"])
else:
    st.info("👆 Please enter your subject first to get started!")

# Convert PDF to image
def pdf_page_to_image(pdf_bytes, page_number):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_number)
    pix = page.get_pixmap(dpi=150)
    image = Image.open(BytesIO(pix.tobytes("png")))
    return image

# Enhanced subject-specific prompt generator
def generate_subject_prompt(subject):
    subject_lower = subject.lower().strip()
    
    # Create a dynamic, engaging prompt based on the subject
    base_prompt = f"""You are an exceptional and beloved {subject} professor with years of teaching experience. Students absolutely love your classes because you make {subject} concepts crystal clear, engaging, and easy to understand. You have a gift for breaking down complex {subject} topics into digestible pieces that stick with students long after they leave your classroom.

Your teaching style is:
- Enthusiastic and passionate about {subject}
- Patient and understanding with students at all levels
- Expert at using analogies and real-world examples from {subject}
- Skilled at connecting current concepts to previously learned {subject} fundamentals
- Always encouraging and supportive

Now, please explain this {subject} slide with your signature teaching approach. Break down any difficult {subject} terminology and guide the student step-by-step as if you're teaching an intermediate-level {subject} student. Keep it concise since there are many slides to cover, but make sure your explanation is thorough enough to truly understand the concept.

Start directly with your explanation - no AI preamble needed. Make {subject} fun and accessible!"""
    
    return base_prompt

# Gemini call with enhanced subject-specific prompting
def explain_slide_threaded(image_pil, subject):
    buffered = BytesIO()
    image_pil.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    # Generate subject-specific prompt
    subject_prompt = generate_subject_prompt(subject)
    
    parts = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state.chat_history]
    parts.append({
        "role": "user",
        "parts": [
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": img_base64
                }
            },
            {
                "text": subject_prompt
            }
        ]
    })
    
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        json={"contents": parts}
    )
    
    if response.status_code == 200:
        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        st.session_state.chat_history.append({"role": "model", "content": reply})
        return reply
    else:
        return f"❌ Error from Gemini: {response.text}"

# Once uploaded
if uploaded_file and st.session_state.subject.strip():
    st.success(f"Perfect! Your {st.session_state.subject} PDF is ready for analysis! 🎉")
    pdf_bytes = uploaded_file.read()
    reader = PdfReader(BytesIO(pdf_bytes))
    num_pages = len(reader.pages)

    # React to arrow keys (before dropdown to sync)
    if js_event == "next" and st.session_state.current_page < num_pages:
        st.session_state.current_page += 1
    elif js_event == "prev" and st.session_state.current_page > 1:
        st.session_state.current_page -= 1

    # Dropdown (updates current_page)
    page_options = [f"Slide {i}" for i in range(1, num_pages + 1)]
    selected_option = st.selectbox(
        "Navigate to slide:",
        options=page_options,
        index=st.session_state.current_page - 1
    )
    selected_page = int(selected_option.split()[-1])
    st.session_state.current_page = selected_page

    # Show PDF and explanation
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"📄 {st.session_state.subject} - Slide {selected_page}")
        image = pdf_page_to_image(pdf_bytes, selected_page - 1)
        st.image(image, use_container_width=True)
        
        # Navigation buttons
        nav_col1, nav_col2, nav_col3 = st.columns(3)
        with nav_col1:
            if st.button("⬅️ Previous", disabled=selected_page <= 1):
                st.session_state.current_page = max(1, selected_page - 1)
                st.rerun()
        with nav_col2:
            st.write(f"Page {selected_page} of {num_pages}")
        with nav_col3:
            if st.button("Next ➡️", disabled=selected_page >= num_pages):
                st.session_state.current_page = min(num_pages, selected_page + 1)
                st.rerun()

    with col2:
        st.subheader(f"🧠 Your {st.session_state.subject} Professor Explains")
        with st.spinner(f"Your favorite {st.session_state.subject} professor is analyzing this slide..."):
            explanation = explain_slide_threaded(image, st.session_state.subject)
        
        st.markdown(
            f"""
            <div style="background-color:#f0f8ff;padding:1.5rem;border-radius:15px;border-left:5px solid #4CAF50; color:#2c3e50; font-size:16px; line-height:1.6;">
            <div style="font-weight:bold; color:#2c5282; margin-bottom:10px;">📚 {st.session_state.subject} Explanation:</div>
            {explanation}
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Add slide to chat history for context
        st.session_state.chat_history.append({
            "role": "user",
            "content": f"This was slide {selected_page} from my {st.session_state.subject} study material. Please explain it in detail."
        })

    # Show study progress
    st.markdown("---")
    progress = selected_page / num_pages
    st.progress(progress, text=f"Study Progress: {selected_page}/{num_pages} slides ({progress:.1%})")
    
    # Keyboard shortcuts reminder
    st.markdown(
        """
        <div style="background-color:#fff3cd;padding:10px;border-radius:8px;margin-top:10px;border:1px solid #ffeaa7;">
        <small><strong>💡 Pro Tip:</strong> Use ← → arrow keys to navigate slides quickly!</small>
        </div>
        """,
        unsafe_allow_html=True
    )