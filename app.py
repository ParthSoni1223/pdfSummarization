import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import os

st.set_page_config(page_title="PDF Summarizer", page_icon="📄")

st.title("📄 PDF Page-by-Page Summarizer with Gemini")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.read())

    api_key = os.getenv("GOOGLE_API_KEY", st.secrets.get("GOOGLE_API_KEY", ""))
    if not api_key:
        st.error("❌ Google API Key not found. Set it as env variable or Streamlit secret.")
    else:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-pro")
        
        doc = fitz.open("temp.pdf")
        st.success(f"✅ Uploaded PDF with {len(doc)} pages")

        summaries = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text()
            st.markdown(f"### 📃 Page {i}")
            if text.strip():
                response = model.generate_content(f"Summarize this page:\n\n{text}")
                st.write(response.text.strip())
                summaries.append(f"Page {i}:\n{response.text.strip()}\n\n")
            else:
                st.warning("Page is empty or image-based.")

        # Optionally download all summaries
        if summaries:
            full_summary = "\n".join(summaries)
            st.download_button("⬇️ Download Full Summary", full_summary, file_name="summary.txt")
