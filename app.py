import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import os

# Title
st.title("📄 PDF Page-by-Page Summarizer with Gemini Vision")

# File uploader
uploaded_file = st.file_uploader("Upload your PDF", type=["pdf"])

if uploaded_file:
    # Save PDF to temp file
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.read())

    # Get Google API key from environment or Streamlit secrets
    api_key = os.getenv("GOOGLE_API_KEY", st.secrets.get("GOOGLE_API_KEY", ""))
    if not api_key:
        st.error("Google API Key not found. Set it as an environment variable or in Streamlit secrets.")
    else:
        genai.configure(api_key=api_key)

        # Open PDF
        pdf_document = fitz.open("temp.pdf")
        st.success(f"Uploaded {len(pdf_document)} pages PDF!")

        # Iterate over pages
        for page_num, page in enumerate(pdf_document, start=1):
            text = page.get_text()
            st.subheader(f"📃 Page {page_num}")
            if text.strip():
                # Summarize with Gemini
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(f"Summarize this text:\n{text}")
                st.write(response.text)
            else:
                st.warning("This page has no text content.")
