import os
import tempfile
import urllib.parse

import streamlit as st
from langchain_community.document_loaders import PyPDFLoader

from src.agent import run_agent
from src.fetch_location import get_location_by_ip
from src.job_api import SUPPORTED_SITES
from src.llm_config import fetch_models, get_settings, missing_settings

st.set_page_config(
    page_title="FreeJobAgent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=300, show_spinner=False)
def load_models(base_url: str, api_key: str) -> list[str]:
    return fetch_models(base_url=base_url, api_key=api_key)


settings = get_settings()
missing = missing_settings(settings)

# ── Sidebar: logo ──
with st.sidebar:
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width="stretch")

# ── Main Content Header ──
st.title("🎯 FreeJobAgent")
st.markdown("Upload your resume and get job recommendations based on your skills and experience.")

# ── Environment Validation Check ──
if missing:
    st.error(
        f"Missing required environment variable(s): {', '.join(missing)}.\n\n"
        "Please create a `.env` file in the project root (you can copy `.env.example`) "
        "and configure the required settings."
    )
    st.code(
        "LLM_API_KEY=your_api_key_here\n"
        "LLM_BASE_URL=https://api.openai.com/v1\n"
        "# Optional: model preselected in the UI (the model list is fetched from LLM_BASE_URL/models)\n"
        "# LLM_MODEL=gpt-4o-mini",
        language="bash",
    )
    st.stop()

# ── Sidebar Model Configuration ──
parsed_url = urllib.parse.urlparse(settings["base_url"])
host = parsed_url.netloc or parsed_url.path or settings["base_url"]

with st.sidebar:
    st.markdown("### LLM")
    st.markdown(f"**Endpoint:** `{host}`")

    models_list = []
    fetch_failed = False
    fetch_error = ""
    try:
        models_list = load_models(settings["base_url"], settings["api_key"])
    except Exception as e:  # ConfigError or unexpected network/parse errors
        fetch_failed = True
        fetch_error = str(e)

    if not fetch_failed and models_list:
        default_index = 0
        if settings["default_model"] in models_list:
            default_index = models_list.index(settings["default_model"])
        selected_model = st.selectbox(
            "Model",
            options=models_list,
            index=default_index,
        )
    else:
        if fetch_failed:
            st.warning(f"Could not load models: {fetch_error}")
        selected_model = st.text_input(
            "Model name",
            value=settings["default_model"],
            placeholder="e.g. gpt-4o-mini",
        )

    if st.button("🔄 Refresh models"):
        load_models.clear()
        st.rerun()

    active_model = (selected_model or "").strip()
    if not active_model:
        st.caption("No model selected.")

    with st.expander("About & how it works"):
        st.markdown(
            "Upload your resume and get AI-powered job recommendations scraped from "
            f"**{', '.join(site.title() for site in SUPPORTED_SITES[:3])}** using JobSpy (free, open-source).\n\n"
            "1. Upload your PDF resume\n"
            "2. AI analyzes your profile\n"
            "3. Jobs are scraped in real time\n"
            "4. Get tailored recommendations"
        )

# ── Resume Upload & Processing ──
uploaded_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

if uploaded_file is not None:
    tmp_path = None
    resume_text = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        loader = PyPDFLoader(tmp_path)
        docs = loader.load()
        resume_text = "\n".join(doc.page_content for doc in docs).strip()
    except Exception as e:
        st.error(f"Failed to read PDF file: {e}")
        st.stop()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not resume_text:
        st.error("The uploaded PDF has no extractable text. Please upload a PDF with readable text.")
        st.stop()

    st.success(f"✅ Uploaded: **{uploaded_file.name}**")
    st.info(f"📄 Parsed {len(docs)} page(s) from your resume.")

    with st.spinner("Detecting your location..."):
        user_location = get_location_by_ip()
    st.info(f"📍 Detected Location: **{user_location}**")

    # ── Job Preferences ──
    st.markdown("### Job Search Preferences")
    col1, col2, col3 = st.columns(3)

    with col1:
        work_type = st.selectbox(
            "Work Type",
            options=["Detect Automatically", "1=On-site", "2=Remote", "3=Hybrid"],
        )
    with col2:
        experience_level = st.selectbox(
            "Experience Level",
            options=[
                "Detect Automatically",
                "1=Internship",
                "2=Entry level",
                "3=Associate",
                "4=Mid-Senior level",
                "5=Director",
            ],
        )
    with col3:
        location_pref = st.text_input(
            "Preferred Location",
            value=user_location,
            placeholder="e.g. New York, NY (edit if needed)",
        )

    # ── Search Execution ──
    search_disabled = not bool(active_model)
    if search_disabled:
        st.warning("Job search is disabled because no model is specified. Please select or enter a model in the sidebar.")

    if st.button("🔍 Find Matching Jobs", type="primary", width="stretch", disabled=search_disabled):
        preferences = {
            "work_type": work_type,
            "experience_level": experience_level,
            "location": location_pref.strip() if location_pref.strip() else "Detect Automatically",
        }

        with st.spinner("🤖 AI is analyzing your resume and searching jobs..."):
            try:
                result = run_agent(
                    resume_text=resume_text,
                    user_location=user_location,
                    preferences=preferences,
                    model=active_model,
                    api_key=settings["api_key"],
                    base_url=settings["base_url"],
                )
                st.session_state["job_search_result"] = result
            except Exception as e:
                st.error(str(e))

    if "job_search_result" in st.session_state and st.session_state["job_search_result"]:
        st.subheader("🎯 Job Recommendations")
        st.markdown(st.session_state["job_search_result"])

else:
    st.info("👆 Upload your resume (PDF) to get started.")
    st.markdown("""
    ### What you get:
    - 🎯 **Personalized job matches** based on your resume
    - 📊 **Salary insights** from job listings
    - 💡 **Application tips** tailored to your profile
    """)
