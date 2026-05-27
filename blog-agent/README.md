# AI Blog Agent 🚀

**One command. One topic. Full article + diagram + image + video short.**

---

## What it produces (per topic)

| File | What it is |
|------|-----------|
| `article.md` | Full 2000-word article in Markdown — paste into Medium, Hashnode |
| `diagram.html` | Architecture/flow diagram — open in browser, screenshot for article |
| `social_posts.txt` | LinkedIn post + Twitter/X thread — copy and post |
| `video_script.txt` | 60-second YouTube Shorts script with hook formula |
| `narration.mp3` | AI voice reading the script (Microsoft Edge TTS — free) |
| `short_video.mp4` | Assembled vertical video — upload to YouTube Shorts + Instagram Reels |
| `seo.txt` | SEO title, meta description, keywords |
| `devto_ready.json` | Auto-published to Dev.to (if API key set) |

---

## Setup (one time only)

### 1. Make sure your .env file has these keys:
```
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
DEVTO_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
BLOG_NICHE=DevOps, Kubernetes, AI Automation
AUTHOR_NAME=YourName
```

### 2. Install dependencies:
```bash
pip install -r requirements.txt
```

---

## Run it

```bash
python agent.py
```

You will be asked:
1. **Topic** — e.g. `How Kubernetes handles container failures automatically`
2. **Auto-publish to Dev.to?** — y/n
3. **Generate video short?** — y/n (needs moviepy + edge-tts)

All outputs go into: `output/YYYYMMDD_HHMM_your-topic/`

---

## Tips for best results

- **Be specific with topics:**
  - ❌ "Kubernetes"
  - ✅ "How to set up Kubernetes HPA to auto-scale pods based on CPU usage"

- **Best topics for your niche:**
  - "Best Claude Prompts for DevOps Engineers in 2025"
  - "How MCPs Work in Windsurf IDE — Complete Guide"
  - "Build a RAG App with FastAPI and LangChain Step by Step"
  - "Kubernetes AI Automation — How to Debug Pods with Claude"
  - "Edge AI on Raspberry Pi — Full Setup Guide"

- **Video tips:**
  - First answer `y` to video on your first run to test
  - Takes ~2 minutes to render
  - Upload `short_video.mp4` directly to YouTube Shorts app on phone

---

## Costs

| Tool | Cost |
|------|------|
| Gemini API | FREE (1000 req/day) |
| Groq API | FREE (1000 req/day) |
| Edge-TTS voices | FREE (Microsoft) |
| Pollinations.ai images | FREE (no key needed) |
| MoviePy video | FREE (open source) |
| Dev.to publishing | FREE |
| **Total** | **₹0/month** |
