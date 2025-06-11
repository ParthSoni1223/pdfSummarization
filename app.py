import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import os

# Set up Streamlit page
st.set_page_config(page_title="PDF Summarizer", page_icon="📄")
st.title("📄 PDF Page-by-Page Summarizer with Gemini 1.5 Pro")

# Upload PDF
uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:
    # Save uploaded PDF temporarily
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.read())

    # Configure Gemini API
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

    try:
        # Use latest stable Gemini model
        model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")

        # Read the PDF
        doc = fitz.open("temp.pdf")
        st.success(f"✅ Uploaded PDF with {len(doc)} pages")

        summaries = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text()
            st.markdown(f"### 📃 Page {i}")
            if text.strip():
                with st.spinner(f"Summarizing page {i}..."):
                    response = model.generate_content(f"Summarize this page of a legal PDF document:\n\n{text}")
                    summary = response.text.strip()
                    st.write(summary)
                    summaries.append(f"Page {i}:\n{summary}\n\n")
            else:
                st.warning(f"⚠️ Page {i} is empty or image-based.")

        # Provide download button for full summary
        if summaries:
            full_summary = "\n".join(summaries)
            st.download_button("⬇️ Download Full Summary", full_summary, file_name="summary.txt")

    except Exception as e:
        st.error(f"❌ An error occurred: {e}")
