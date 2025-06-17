import os
import streamlit as st
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import base64
import requests
from PIL import Image
from io import BytesIO
import fitz

# Load API key
load_dotenv()
GEMINI_API_KEY = "AIzaSyDktmzdFPVFY_7ph7-aP_AlQ4Huy4Nnn6I"  # Replace with your actual API key

st.set_page_config(layout="wide", page_title="📚 Study Assistant", page_icon="📚")
st.title("📚 Study Assistant: Easy PDF Summaries")

# Session state init
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "subject" not in st.session_state:
    st.session_state.subject = ""

# Subject input section
st.markdown("### 📖 What subject are you studying today?")
subject_input = st.text_input(
    "Enter your subject:",
    placeholder="e.g., Mathematics, Physics, Computer Science, Biology, Chemistry, History, Economics...",
    value=st.session_state.subject,
    help="This helps me create better summaries tailored to your subject!"
)

# Update session state when subject changes
if subject_input != st.session_state.subject:
    st.session_state.subject = subject_input
    # Reset chat history when subject changes to avoid context mixing
    st.session_state.chat_history = []

# Upload PDF (only show if subject is entered)
uploaded_file = None
if st.session_state.subject.strip():
    st.markdown(f"### 📄 Upload your **{st.session_state.subject}** PDF")
    uploaded_file = st.file_uploader("Choose your PDF file", type=["pdf"])
else:
    st.info("👆 Please enter your subject first to get personalized summaries!")

# Convert PDF to image
def pdf_page_to_image(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=150)
        image = Image.open(BytesIO(pix.tobytes("png")))
        doc.close()
        return image
    except Exception as e:
        st.error(f"Error converting PDF page: {str(e)}")
        return None

# Enhanced subject-specific summary prompt generator
def generate_summary_prompt(subject):
    subject_lower = subject.lower().strip()
    
    # Create a dynamic, summary-focused prompt
    summary_prompt = f"""You are an experienced, excellent and great {subject} teacher who is loved by all students because you make {subject} incredibly easy to understand. You have a special talent for creating clear, simple summaries that help students grasp even the most complex {subject} concepts.

Your teaching approach:
- You explain {subject} concepts in the simplest possible language
- You break down complex {subject} terms into easy-to-understand explanations  
- You create summaries that make students say "Oh, now I get it!"
- You use simple examples and analogies related to {subject}
- You focus on the key points that students need to remember
- You make sure every student understands completely before moving on

Task: Please provide an easy-to-understand summary of this {subject} slide/page. Your summary should:
1. Explain the main concept in simple language
2. Break down any difficult {subject} terms or vocabulary
3. Highlight the key points students must remember
4. Use simple examples if helpful
5. Make it so clear that any student can understand it completely

Keep the summary concise but comprehensive - students should understand everything after reading your explanation. Write in a friendly, encouraging tone that makes learning {subject} enjoyable.

Start directly with your summary - no introduction needed."""
    
    return summary_prompt

# Gemini API call for summary generation
def generate_slide_summary(image_pil, subject):
    try:
        buffered = BytesIO()
        image_pil.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Generate subject-specific summary prompt
        summary_prompt = generate_summary_prompt(subject)
        
        # Include previous context for better understanding
        parts = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state.chat_history[-4:]]  # Keep last 4 exchanges for context
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
                    "text": summary_prompt
                }
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
            return f"❌ Error getting summary: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return "❌ Request timed out. Please try again."
    except Exception as e:
        return f"❌ Error generating summary: {str(e)}"

# Main app logic
if uploaded_file and st.session_state.subject.strip():
    st.success(f"✅ Great! Your {st.session_state.subject} PDF is loaded successfully!")
    
    try:
        pdf_bytes = uploaded_file.read()
        reader = PdfReader(BytesIO(pdf_bytes))
        num_pages = len(reader.pages)
        
        # Navigation controls
        st.markdown("---")
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        
        with nav_col1:
            if st.button("⬅️ Previous Page", disabled=st.session_state.current_page <= 1):
                st.session_state.current_page = max(1, st.session_state.current_page - 1)
                st.rerun()
        
        with nav_col2:
            # Page selector dropdown
            page_options = [f"Page {i}" for i in range(1, num_pages + 1)]
            selected_option = st.selectbox(
                "Select page:",
                options=page_options,
                index=st.session_state.current_page - 1,
                key="page_selector"
            )
            selected_page = int(selected_option.split()[-1])
            if selected_page != st.session_state.current_page:
                st.session_state.current_page = selected_page
                st.rerun()
        
        with nav_col3:
            if st.button("Next Page ➡️", disabled=st.session_state.current_page >= num_pages):
                st.session_state.current_page = min(num_pages, st.session_state.current_page + 1)
                st.rerun()
        
        # Progress bar
        progress = st.session_state.current_page / num_pages
        st.progress(progress, text=f"Progress: {st.session_state.current_page}/{num_pages} pages ({progress:.1%} complete)")
        
        st.markdown("---")
        
        # Main content area
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"📄 {st.session_state.subject} - Page {st.session_state.current_page}")
            
            # Convert and display PDF page
            image = pdf_page_to_image(pdf_bytes, st.session_state.current_page - 1)
            if image:
                st.image(image, use_container_width=True, caption=f"Page {st.session_state.current_page}")
            else:
                st.error("Could not display this page. Please try another page.")
        
        with col2:
            st.subheader(f"📝 Easy {st.session_state.subject} Summary")
            
            # Generate summary button
            if st.button(f"🔍 Get Summary for Page {st.session_state.current_page}", type="primary", use_container_width=True):
                if image:
                    with st.spinner(f"Creating an easy-to-understand {st.session_state.subject} summary..."):
                        summary = generate_slide_summary(image, st.session_state.subject)
                    
                    # Display summary in a nice container
                    st.markdown(
                        f"""
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2px; border-radius: 15px; margin: 10px 0;">
                            <div style="background-color: white; padding: 20px; border-radius: 13px; color: #333; font-size: 16px; line-height: 1.8;">
                                <div style="font-weight: bold; color: #667eea; margin-bottom: 15px; font-size: 18px;">
                                    📚 {st.session_state.subject} Summary - Page {st.session_state.current_page}
                                </div>
                                <div style="border-left: 4px solid #667eea; padding-left: 15px;">
                                    {summary.replace('\n', '<br>')}
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # Add to chat history for context
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": f"This was page {st.session_state.current_page} from my {st.session_state.subject} study material. Please provide an easy summary."
                    })
                    
                    # Download summary option
                    st.download_button(
                        label="💾 Download Summary",
                        data=f"Page {st.session_state.current_page} - {st.session_state.subject} Summary\n\n{summary}",
                        file_name=f"{st.session_state.subject}_Page_{st.session_state.current_page}_Summary.txt",
                        mime="text/plain"
                    )
                else:
                    st.error("Cannot generate summary - page could not be loaded.")
        
        # Study tips section
        st.markdown("---")
        st.markdown(
            f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745;">
                <h4 style="color: #28a745; margin-top: 0;">📚 Study Tips for {st.session_state.subject}</h4>
                <ul style="margin-bottom: 0;">
                    <li><strong>Take it slow:</strong> Read each summary carefully and make sure you understand before moving to the next page</li>
                    <li><strong>Make notes:</strong> Write down key points from each summary in your own words</li>
                    <li><strong>Review regularly:</strong> Come back to difficult pages and re-read the summaries</li>
                    <li><strong>Ask questions:</strong> If something is unclear, try getting the summary again or ask your teacher</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        st.info("Please try uploading your PDF again.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666; font-size: 14px;">
        <p>📚 Study Assistant - Making learning easy and fun! 🎓</p>
        <p><small>Navigate through pages using the buttons above and get easy summaries for better understanding.</small></p>
    </div>
    """,
    unsafe_allow_html=True
)