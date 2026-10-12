import io
import os
import re
import tempfile
import zipfile
import requests
import streamlit as st
from gtts import gTTS

# Page configuration
st.set_page_config(
    page_title="Repo-to-Podcast & Code Studio",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Modern CSS
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.6rem;
        background: -webkit-linear-gradient(45deg, #FF4B4B, #FF8E53);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: 800;
        margin-bottom: 0.1rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6c757d;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #FF4B4B 0%, #FF6B6B 100%);
        color: white;
        font-weight: 700;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.25);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #ff3333 0%, #ff5252 100%);
        box-shadow: 0 6px 16px rgba(255, 75, 75, 0.4);
        transform: translateY(-1px);
    }
    .segment-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 1.2rem;
    }
    .metric-container {
        background-color: #f8fafc;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    </style>
""",
    unsafe_allow_html=True,
)


def get_secret(key: str) -> str:
    val = os.environ.get(key)
    if val:
        return val
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return ""


def fetch_github_repo_data(owner: str, repo: str):
    headers = {"Accept": "application/vnd.github.v3+json"}
    github_token = get_secret("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(repo_url, headers=headers)

    if response.status_code == 404:
        return None, "Repository not found. Please check public URL/permissions."
    elif response.status_code == 403:
        return (
            None,
            "API rate limit exceeded. Add a GITHUB_TOKEN in your environment or secrets.",
        )
    elif response.status_code != 200:
        return None, f"GitHub API Error: {response.status_code}"

    repo_info = response.json()

    readme_content = ""
    readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    readme_resp = requests.get(readme_url, headers=headers)
    if readme_resp.status_code == 200:
        download_url = readme_resp.json().get("download_url")
        if download_url:
            r_download = requests.get(download_url)
            if r_download.status_code == 200:
                readme_content = r_download.text[:7000]

    tree_content = []
    tree_url = (
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
    )
    tree_resp = requests.get(tree_url, headers=headers)
    if tree_resp.status_code != 200:
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
        tree_resp = requests.get(tree_url, headers=headers)

    if tree_resp.status_code == 200:
        tree_data = tree_resp.json().get("tree", [])
        tree_content = [
            item["path"] for item in tree_data if item["type"] == "blob"
        ][:90]

    return {
        "name": repo_info.get("name"),
        "description": repo_info.get("description"),
        "stars": repo_info.get("stargazers_count"),
        "language": repo_info.get("language"),
        "readme": readme_content,
        "files": tree_content,
    }, None


def call_llm(
    prompt: str, api_key: str, model_name: str, fallback_text: str = ""
) -> str:
    if not api_key:
        return "⚠️ Please enter your API Key in the sidebar configuration to use AI features."

    if api_key.startswith("sk-or-"):
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://streamlit.io",
            "X-Title": "Repo-to-Podcast Studio",
            "Content-Type": "application/json",
        }
    else:
        endpoint = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    try:
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500,
        }
        res = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        if res.status_code == 200:
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            if content and len(content.strip()) > 5:
                return content
        else:
            return f"⚠️ API Error ({res.status_code}): {res.text}"
    except Exception as e:
        return f"⚠️ Connection failed: {str(e)}"

    return fallback_text


def clean_text_for_speech(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("_", " ")
    text = (
        text.replace("**", "")
        .replace("__", "")
        .replace("*", "")
        .replace("`", "")
        .replace("#", "")
        .replace(">", "")
    )
    cleaned = text.strip()
    if not cleaned:
        return "Welcome to the repository overview podcast episode."
    return cleaned


def text_to_speech_dual_voice(script_text: str, host_accent: str) -> str:
    lines = script_text.split("\n")
    combined_audio_buffer = io.BytesIO()

    accent_map = {
        "British (UK)": "co.uk",
        "American (US)": "com",
        "Australian": "com.au",
        "Indian": "co.in",
    }
    tld = accent_map.get(host_accent, "co.uk")

    valid_lines_count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue

        speaker = "Alex"
        if "Sam" in line[:15] or "[Reviewer Sam]" in line:
            speaker = "Sam"
        elif "Alex" in line[:15] or "[Host Alex]" in line:
            speaker = "Alex"

        spoken_text = clean_text_for_speech(line)
        if not spoken_text:
            continue

        spoken_text += " ... "
        valid_lines_count += 1

        host_tld = "com" if speaker == "Alex" else tld

        try:
            tts = gTTS(text=spoken_text, lang="en", tld=host_tld, slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            combined_audio_buffer.write(fp.read())
        except Exception:
            pass

    audio_bytes = combined_audio_buffer.getvalue()
    if not audio_bytes or valid_lines_count == 0:
        fallback_tts = gTTS(
            text="Welcome to this repository review podcast episode.",
            lang="en",
            slow=False,
        )
        fb_fp = io.BytesIO()
        fallback_tts.write_to_fp(fb_fp)
        fb_fp.seek(0)
        audio_bytes = fb_fp.read()

    final_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    final_temp.write(audio_bytes)
    final_temp.close()
    return final_temp.name


def main():
    st.markdown(
        '<div class="main-header">🎙️ Repo-to-Podcast & Code Studio</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Transform any GitHub repository into an elite dual-host podcast series with deep code intelligence.</div>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("🎛️ Studio Controls")
        st.subheader("🤖 AI Credentials")
        default_key = get_secret("GROQ_API_KEY")
        user_api_key = st.text_input(
            "API Key (Groq / OpenRouter)",
            value=default_key,
            type="password",
            help="Enter your API key.",
        )

        model_name = st.selectbox(
            "Select AI Model",
            [
                "meta-llama/llama-3.3-70b-instruct",
                "openai/gpt-oss-120b",
                "anthropic/claude-3.5-sonnet",
                "llama-3.3-70b-versatile",
            ],
            help="Choose active model.",
        )

        st.markdown("---")
        st.subheader("🎙️ Podcast Parameters")
        focus_style = st.selectbox(
            "Style Tone",
            [
                "Casual & Enthusiastic Developer Breakdown",
                "Deep Technical Architecture & Component Review",
                "Quick Elevator Pitch for Students & Beginners",
            ],
        )

        host_accent = st.selectbox(
            "Co-Host Accent (Sam)",
            ["British (UK)", "Australian", "Indian", "American (US)"],
        )

    with st.form("repo_form"):
        c1, c2 = st.columns([5, 1])
        with c1:
            repo_url = st.text_input(
                "GitHub Repository URL",
                placeholder="https://github.com/owner/repository-name",
                label_visibility="collapsed",
            )
        with c2:
            submitted = st.form_submit_button("Generate Suite 🚀")

    if submitted:
        if not repo_url or "github.com/" not in repo_url:
            st.error("Please enter a valid public GitHub repository URL.")
            return

        parts = repo_url.strip("/").split("/")
        if len(parts) < 2:
            st.error("Invalid URL format. Use https://github.com/owner/repo")
            return

        owner, repo = parts[-2], parts[-1]
        st.session_state["repo_name"] = repo

        with st.spinner(
            f"🔍 Fetching codebase metadata for {owner}/{repo}..."
        ):
            repo_data, err = fetch_github_repo_data(owner, repo)
            if err:
                st.error(err)
                return
            st.session_state["repo_data"] = repo_data

        with st.spinner(
            "✍️ Directing multi-part podcast scripts & intelligence reports..."
        ):
            name = repo_data["name"]
            desc = repo_data["description"] or "No description provided."
            lang = repo_data["language"] or "Multi-language"
            file_list = ", ".join(repo_data["files"][:40])
            readme = repo_data["readme"][:4000]

            fb_p1 = f"[Host Alex]: Welcome to Repopodcast, reviewing {name}.\n[Reviewer Sam]: Built in {lang} with mission: {desc}."
            fb_p2 = f"[Host Alex]: Let's look at the architecture of {name}.\n[Reviewer Sam]: It contains core files like {file_list[:100]}."
            fb_p3 = f"[Host Alex]: What are the primary use cases?\n[Reviewer Sam]: It solves practical developer workflows cleanly."

            p1_prompt = f"""Write an engaging 2-person dialogue script using exact tags [Host Alex]: and [Reviewer Sam]: for Part 1: Introduction and Project Mission. Tone: {focus_style}. Name: {name}, Desc: {desc}, Language: {lang}."""
            p2_prompt = f"""Write an engaging 2-person dialogue script using exact tags [Host Alex]: and [Reviewer Sam]: for Part 2: Architecture & Workflow. Files: {file_list}."""
            p3_prompt = f"""Write an engaging 2-person dialogue script using exact tags [Host Alex]: and [Reviewer Sam]: for Part 3: Use Cases & Summary. README snippet: {readme[:1000]}."""

            script_p1 = call_llm(p1_prompt, user_api_key, model_name, fb_p1)
            script_p2 = call_llm(p2_prompt, user_api_key, model_name, fb_p2)
            script_p3 = call_llm(p3_prompt, user_api_key, model_name, fb_p3)

            st.session_state["scripts"] = {
                "Part 1: Intro": script_p1,
                "Part 2: Architecture": script_p2,
                "Part 3: Use Cases": script_p3,
            }

        with st.spinner("🔊 Synthesizing dual-voice audio tracks..."):
            audio_paths = {}
            for title, script_text in st.session_state["scripts"].items():
                audio_paths[title] = text_to_speech_dual_voice(
                    script_text, host_accent
                )
            st.session_state["audio_paths"] = audio_paths

        st.success("🎉 Podcast studio suite generated successfully!")

    if "audio_paths" in st.session_state:
        repo_ctx = st.session_state["repo_data"]
        current_repo_name = st.session_state.get("repo_name", "repository")

        st.markdown("---")

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f"<div class='metric-container'>📦 <b>Repository</b><br>{repo_ctx.get('name')}</div>",
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"<div class='metric-container'>💻 <b>Primary Language</b><br>{repo_ctx.get('language', 'Multi-language')}</div>",
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f"<div class='metric-container'>⭐ <b>GitHub Stars</b><br>{repo_ctx.get('stars', 0)}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("")

        tab_podcast, tab_arch, tab_bugs, tab_setup, tab_chat = st.tabs(
            [
                "🎙️ Podcast Episodes (USP)",
                "🏗️ Architecture & Workflow",
                "🐛 Code Bugs & Review",
                "📖 User Setup Guide",
                "💬 Interactive Assistant",
            ]
        )

        # TAB 1: Podcast Episodes (The USP)
        with tab_podcast:
            st.subheader("🎧 Dual-Host Episodic Podcast Series")
            st.write(
                "Listen to individual podcast chapters or download them all at once as a ZIP archive."
            )

            audio_paths = st.session_state["audio_paths"]
            scripts = st.session_state["scripts"]

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for part_title, audio_path in audio_paths.items():
                    filename = f"{current_repo_name}_{part_title.lower().replace(':', '').replace(' ', '_')}.mp3"
                    if os.path.exists(audio_path):
                        with open(audio_path, "rb") as af:
                            zip_file.writestr(filename, af.read())
            zip_buffer.seek(0)

            st.download_button(
                label="📦 Download All Podcast Episodes (.zip)",
                data=zip_buffer,
                file_name=f"{current_repo_name}_podcast_series.zip",
                mime="application/zip",
            )
            st.markdown("---")

            for part_title, audio_path in audio_paths.items():
                st.markdown(
                    f'<div class="segment-card"><h4>📌 {part_title}</h4>',
                    unsafe_allow_html=True,
                )
                st.audio(audio_path, format="audio/mp3")

                with st.expander(f"View Script for {part_title}"):
                    st.markdown(scripts[part_title])

                with open(audio_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Download {part_title} MP3",
                        data=f,
                        file_name=f"{current_repo_name}_{part_title.lower().replace(':', '').replace(' ', '_')}.mp3",
                        mime="audio/mp3",
                        key=f"dl_{part_title}",
                    )
                st.markdown("</div>", unsafe_allow_html=True)

        # TAB 2: Architecture & Workflow
        with tab_arch:
            st.subheader("System Architecture & Workflow Breakdown")
            if st.button("Generate Architecture Analysis 🏗️"):
                with st.spinner("Analyzing codebase design..."):
                    prompt = f"""Analyze this repository and provide an expert breakdown of its system architecture, design patterns, and operational workflow.
Repository Name: {repo_ctx.get('name')}
Language: {repo_ctx.get('language')}
Files: {repo_ctx.get('files')}
README: {repo_ctx.get('readme')[:4000]}"""
                    fallback_arch = f"### Architecture Overview\n- **Project**: {repo_ctx.get('name')}\n- **Language**: {repo_ctx.get('language')}\n- **Structure**: Modular component organization."
                    st.session_state["arch_res"] = call_llm(
                        prompt, user_api_key, model_name, fallback_arch
                    )

            if "arch_res" in st.session_state:
                st.markdown(st.session_state["arch_res"])
                st.download_button(
                    "📥 Export Architecture Report",
                    data=st.session_state["arch_res"],
                    file_name=f"{current_repo_name}_architecture.md",
                    mime="text/markdown",
                )

        # TAB 3: Code Bugs & Review
        with tab_bugs:
            st.subheader("Potential Bugs & Code Review")
            if st.button("Scan Code Risks & Bugs 🔍"):
                with st.spinner("Scanning structure for code smells and bugs..."):
                    prompt = f"""Review this repository structure and documentation to identify potential bugs, anti-patterns, or error-handling gaps users should know about.
Repository Name: {repo_ctx.get('name')}
Files: {repo_ctx.get('files')}
README: {repo_ctx.get('readme')[:4000]}"""
                    fallback_bugs = "### Code Review & Risks\n- No major syntax blockers identified.\n- Ensure environment variables and dependencies are correctly configured."
                    st.session_state["bugs_res"] = call_llm(
                        prompt, user_api_key, model_name, fallback_bugs
                    )

            if "bugs_res" in st.session_state:
                st.markdown(st.session_state["bugs_res"])
                st.download_button(
                    "📥 Export Bug Review",
                    data=st.session_state["bugs_res"],
                    file_name=f"{current_repo_name}_bug_review.md",
                    mime="text/markdown",
                )

        # TAB 4: User Setup Guide
        with tab_setup:
            st.subheader("Step-by-Step Installation & User Setup Guide")
            if st.button("Generate Setup Guide 📖"):
                with st.spinner("Compiling setup guide..."):
                    prompt = f"""Write a clear, step-by-step installation and user setup guide for this repository, including prerequisites, cloning, dependencies, and local execution.
Repository Name: {repo_ctx.get('name')}
Language: {repo_ctx.get('language')}
Files: {repo_ctx.get('files')}
README: {repo_ctx.get('readme')[:4000]}"""
                    fallback_setup = f"### Setup Guide\n1. Clone the repository:\n   `git clone https://github.com/owner/{repo_ctx.get('name')}`\n2. Install dependencies.\n3. Run the application."
                    st.session_state["setup_res"] = call_llm(
                        prompt, user_api_key, model_name, fallback_setup
                    )

            if "setup_res" in st.session_state:
                st.markdown(st.session_state["setup_res"])
                st.download_button(
                    "📥 Export Setup Guide",
                    data=st.session_state["setup_res"],
                    file_name=f"{current_repo_name}_setup_guide.md",
                    mime="text/markdown",
                )

        # TAB 5: Interactive Assistant (Fixed to avoid static canned answers)
        with tab_chat:
            st.subheader("💬 Interactive Repository Assistant")
            st.write(
                "Ask any specific question about the codebase, files, setup, or features below!"
            )

            if "messages" not in st.session_state:
                st.session_state["messages"] = []

            for message in st.session_state["messages"]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if user_query := st.chat_input(
                "Ask a question about the code, bugs, or setup..."
            ):
                st.session_state["messages"].append(
                    {"role": "user", "content": user_query}
                )
                with st.chat_message("user"):
                    st.markdown(user_query)

                with st.spinner("Thinking..."):
                    chat_prompt = f"""You are an expert software engineer assistant. Answer the user's specific question accurately and dynamically based on this repository's codebase details:
Repository Name: {repo_ctx.get('name')}
Language: {repo_ctx.get('language')}
Description: {repo_ctx.get('description')}
Files: {repo_ctx.get('files')}
README: {repo_ctx.get('readme')[:5000]}

User Question: {user_query}"""

                    answer = call_llm(
                        chat_prompt,
                        user_api_key,
                        model_name,
                        fallback_text=(
                            f"⚠️ Unable to query AI model. Please check your API key in the sidebar. "
                            f"(Query regarding '{user_query}' for {repo_ctx.get('name')})"
                        ),
                    )

                st.session_state["messages"].append(
                    {"role": "assistant", "content": answer}
                )
                with st.chat_message("assistant"):
                    st.markdown(answer)


if __name__ == "__main__":
    main()