# RepoToPodcast
🎙️ Repo-to-Podcast &amp; Code Intelligence Studio

Repo-to-Podcast Studio is an advanced AI-powered developer tool that transforms any public GitHub repository into an engaging, multi-part episodic podcast series. Designed for developers, engineering teams, and technical content creators, it bridges the gap between static codebases and dynamic auditory learning while offering deep technical inspection suites.

🚀 Key Features
Dual-Host Podcast Generation: Automatically directs and synthesizes a natural, 2-person conversational podcast script (featuring hosts Alex and Sam) discussing your repository’s mission, architecture, and use cases.

Customizable Voice Accents & Tones: Choose from multiple co-host regional accents (British, Australian, Indian, American) and tune the podcast style (Casual Developer Breakdown, Deep Technical Architecture, or Elevator Pitch).

Episodic Audio Chapters: Breaks down the repository into dedicated audio segments (Introduction, Architecture & Workflow, Use Cases) complete with standalone audio players and individual or bulk ZIP downloads.

System Architecture & Workflow Analysis: Instantly inspects file trees and repository metadata to generate structured architectural and design pattern breakdowns.

Code Bug & Risk Scanner: Reviews repository structure and documentation to surface potential code smells, anti-patterns, or configuration gaps.

Automated User Setup Guides: Compiles clear, step-by-step instructions for cloning, dependency installation, and local execution.

Interactive Codebase Assistant: A context-aware chat assistant that lets you query specific logic, files, or configurations directly within the repository.

🛠️ Tech Stack
Frontend & Dashboard: Streamlit (Wide-layout Studio UI)

Audio Synthesis: Google Text-to-Speech (gTTS) with custom stream buffering and multi-accent routing

LLM Integration: Universal OpenAI-compatible API client supporting Groq and OpenRouter endpoints (Llama 3, Claude 3.5 Sonnet, GPT-OSS)

Version Control & Parsing: GitHub REST API (Metadata, Tree structure, and README extraction)

📦 Getting Started Locally
Clone the Repository:

Bash
git clone https://github.com/your-username/Repo-to-Podcast.git
cd Repo-to-Podcast
Install Dependencies:

Bash
pip install streamlit requests gtts
Run the Application:

Bash
streamlit run app.py
