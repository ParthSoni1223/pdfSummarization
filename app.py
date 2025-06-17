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
        pix = page.get_pixmap(dpi=120)  # Reduced DPI for smaller display
        image = Image.open(BytesIO(pix.tobytes("png")))
        doc.close()
        return image
    except Exception as e:
        st.error(f"Error converting PDF page: {str(e)}")
        return None

# Enhanced subject-specific summary prompt generator
def generate_summary_prompt(subject):
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

# Generate subject-specific motivational tips
def generate_subject_tips(subject):
    tips_prompts = {
        "mathematics": f"Hey there, future mathematician! 🔢 {subject} is like solving puzzles - each problem teaches you to think logically and systematically. Remember, every mathematician started exactly where you are now. Don't worry if some concepts seem tricky at first; that's completely normal! The key is practice and patience. I've seen thousands of students master {subject}, and you're no different. Take it one step at a time, celebrate small victories, and soon you'll be amazed at how much you've learned. You've got this! 💪",
        
        "physics": f"Welcome to the amazing world of Physics! 🌟 You're about to discover how the universe works - from tiny atoms to massive galaxies! Physics might seem challenging, but remember, you use physics every day without realizing it. Every great physicist started with curiosity, just like you. Don't get discouraged by complex equations; focus on understanding the concepts first. I believe in you completely! With consistent effort and the right guidance, you'll master physics and maybe even discover something new about our world! 🚀",
        
        "chemistry": f"Get ready to become a chemistry wizard! ⚗️ Chemistry is everywhere around us - in the food we eat, the air we breathe, and even in our bodies! I know it can seem overwhelming with all those formulas and reactions, but trust me, once you start connecting the dots, it becomes incredibly exciting. Every chemist started with basic curiosity about how things work. You have that same spark! Take your time, practice regularly, and don't hesitate to ask questions. I'm here to make chemistry as clear and fun as possible! 🧪✨",
        
        "biology": f"Welcome to the fascinating world of life science! 🌱 Biology is the study of YOU and everything living around you - how amazing is that? From tiny cells to complex ecosystems, you're about to explore the incredible mechanisms of life. Biology might have lots of terms to remember, but don't worry - I'll help you understand each concept step by step. Remember, every famous biologist started with wonder about living things, just like you. Stay curious, be patient with yourself, and enjoy this incredible journey of discovery! 🔬🦋",
        
        "computer science": f"Welcome to the digital age, future programmer! 💻 Computer Science is like learning a new language that lets you create amazing things - apps, games, websites, and even AI! Don't worry if coding seems confusing at first; every expert programmer started with 'Hello World' just like you will. The beauty of programming is that there's always a logical solution to every problem. Be patient, practice regularly, and don't be afraid to make mistakes - they're how we learn! You're entering one of the most exciting fields in the world. Let's code your future together! 🚀👨‍💻",
        
        "history": f"Time to travel through time, young historian! 🏛️ History isn't just dates and events - it's incredible stories of real people who shaped our world! Every historical figure you'll study was once a person with dreams, fears, and challenges, just like you. Understanding history helps you understand the present and shape the future. Don't worry about memorizing everything at once; focus on understanding the connections and stories. I promise to make history come alive for you! Remember, you're not just learning about the past - you're preparing to make history yourself! 📚⏳"
    }
    
    # Default tip for any subject not specifically listed
    default_tip = f"Hello, brilliant student! 🌟 You've chosen to study {subject}, and that shows your dedication to learning! Every expert in {subject} started exactly where you are right now - with curiosity and determination. Don't worry if some concepts seem challenging; that's completely normal and part of the learning process. I'm here to break down every complex idea into simple, understandable pieces. Remember, there's no such thing as a 'stupid question' in my classroom. Take your time, be patient with yourself, and celebrate every small victory. You have everything it takes to master {subject}! Let's make this learning journey amazing together! 💪📚"
    
    subject_lower = subject.lower().strip()
    for key in tips_prompts:
        if key in subject_lower:
            return tips_prompts[key]
    
    return default_tip

# Gemini API call for summary generation
def generate_slide_summary(image_pil, subject):
    try:
        buffered = BytesIO()
        image_pil.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Generate subject-specific summary prompt
        summary_prompt = generate_summary_prompt(subject)
        
        # Include previous context for better understanding
        parts = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state.chat_history[-4:]]
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

        # Dropdown (updates current_page) - like original
        page_options = [f"Slide {i}" for i in range(1, num_pages + 1)]
        selected_option = st.selectbox(
            "Go to slide:",
            options=page_options,
            index=st.session_state.current_page - 1
        )
        selected_page = int(selected_option.split()[-1])
        st.session_state.current_page = selected_page

        # Show PDF and explanation - like original layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"📄 Slide {selected_page}")
            image = pdf_page_to_image(pdf_bytes, selected_page - 1)
            if image:
                st.image(image, use_container_width=True)
            else:
                st.error("Could not display this page.")
                
            # Navigation buttons below image - like original
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
            st.subheader(f"📝 Easy {st.session_state.subject} Summary")
            
            # Auto-generate summary like original (no button click needed)
            if image:
                with st.spinner(f"Creating an easy-to-understand {st.session_state.subject} summary..."):
                    summary = generate_slide_summary(image, st.session_state.subject)
                
                # Display summary in styled container
                st.markdown(
                    f"""
                    <div style="background-color:#f0f8ff;padding:1.5rem;border-radius:15px;border-left:5px solid #4CAF50; color:#2c3e50; font-size:16px; line-height:1.6;">
                    <div style="font-weight:bold; color:#2c5282; margin-bottom:10px;">📚 {st.session_state.subject} Summary:</div>
                    {summary.replace(chr(10), '<br>')}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Add to chat history for context
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": f"This was slide {selected_page} from my {st.session_state.subject} study material. Please provide an easy summary."
                })
            else:
                st.error("Cannot generate summary - page could not be loaded.")

        # Progress bar below main content - like original
        st.markdown("---")
        progress = selected_page / num_pages
        st.progress(progress, text=f"Study Progress: {selected_page}/{num_pages} slides ({progress:.1%})")
        
        # Subject-specific motivational tips from experienced teacher
        motivational_tip = generate_subject_tips(st.session_state.subject)
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2px; border-radius: 15px; margin: 20px 0;">
                <div style="background-color: white; padding: 20px; border-radius: 13px; color: #333; font-size: 16px; line-height: 1.7;">
                    <div style="font-weight: bold; color: #667eea; margin-bottom: 15px; font-size: 18px;">
                        💪 Message from Your {st.session_state.subject} Teacher
                    </div>
                    <div style="font-style: italic; color: #555;">
                        {motivational_tip}
                    </div>
                </div>
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
        <p><small>Navigate through slides and get automatic easy summaries for better understanding.</small></p>
    </div>
    """,
    unsafe_allow_html=True
)