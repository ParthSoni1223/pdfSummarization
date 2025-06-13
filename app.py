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

# Upload PDF
uploaded_file = st.file_uploader("Upload your PDF notes/slides", type=["pdf"])

# Session state init
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 1

# Convert PDF to image
def pdf_page_to_image(pdf_bytes, page_number):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_number)
    pix = page.get_pixmap(dpi=150)
    image = Image.open(BytesIO(pix.tobytes("png")))
    return image

# Gemini call
def explain_slide_threaded(image_pil):
    buffered = BytesIO()
    image_pil.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

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
                "text": (
                    "You are a friendly and patient tutor. Please explain this slide, assuming I have some background knowledge. "
                    "Break down difficult words and guide me step-by-step like you're teaching an intermediate. "
                    "Keep it brief as I have a lot of slides. Start with the explanation. No AI preamble."
                )
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
if uploaded_file:
    st.success("PDF uploaded successfully!")
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
        "Go to slide:",
        options=page_options,
        index=st.session_state.current_page - 1
    )
    selected_page = int(selected_option.split()[-1])
    st.session_state.current_page = selected_page

    # Show PDF and explanation
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"📄 Slide {selected_page}")
        image = pdf_page_to_image(pdf_bytes, selected_page - 1)
        st.image(image, use_container_width=True)

    with col2:
        st.subheader("🧠 Explanation")
        with st.spinner("Sending to Gemini for explanation with full context..."):
            explanation = explain_slide_threaded(image)
        st.markdown(
            f"""
            <div style="background-color:#f7f7f7;padding:1rem;border-radius:10px;border:1px solid #ccc; color:#111111; font-size:16px;">
            {explanation}
            """,
            unsafe_allow_html=True
        )
        st.session_state.chat_history.append({
            "role": "user",
            "content": f"This was slide {selected_page}. Please explain it in detail."
        })