import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai

st.set_page_config(page_title="PDF Summarizer", page_icon="📄")
st.title("📄 PDF Page-by-Page Summarizer with Gemini")

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# List models for debugging
models = genai.list_models()
st.markdown("### 🔍 Available Models")
for m in models:
    st.write(m.name)

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.read())

    model = genai.GenerativeModel(model_name="models/gemini-pro")  # Replace if needed

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

    if summaries:
        full_summary = "\n".join(summaries)
        st.download_button("⬇️ Download Full Summary", full_summary, file_name="summary.txt")
