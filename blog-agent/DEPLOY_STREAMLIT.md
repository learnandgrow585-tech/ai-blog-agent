# Deploy AI Blog Agent — Streamlit Community Cloud

> **No installs required.** Everything happens in your browser and online.  
> This is the same zero-install approach used to deploy your AI website on Vercel.

---

## What You'll Get

A live URL like `https://your-app.streamlit.app` — open it from any browser,
type a topic, and the agent writes, voices, and publishes a full blog post for you.

---

## Step 1 — Push the `blog-agent` folder to GitHub

You already have the `My-AI-Workspace` repository on GitHub.
The `blog-agent/` folder just needs to be inside it (same as `ai-website/` is).

### If `blog-agent/` is NOT yet in GitHub:

1. Go to **github.com → Your Repository → My-AI-Workspace**
2. Click **Add file → Upload files**
3. Drag-and-drop the entire `blog-agent/` folder from your laptop
4. Scroll down → **Commit changes**

### If it's already there (partial):

1. Open each new/changed file in GitHub web UI  
2. Click the ✏️ pencil icon → paste the new content → **Commit changes**

**Files that must be in the repo:**

```
blog-agent/
├── streamlit_app.py          ← main app file
├── agent_core.py             ← pipeline logic
├── requirements.txt          ← dependencies (Streamlit Cloud reads this)
├── .streamlit/
│   ├── config.toml           ← dark theme + server settings
│   └── secrets.toml.example  ← template (safe to commit, has no real keys)
└── .env.example              ← also safe to commit
```

> **Never upload `.env` or `.streamlit/secrets.toml`** — those contain your real API keys.

---

## Step 2 — Create a Streamlit Community Cloud account

1. Go to **[share.streamlit.io](https://share.streamlit.io)**
2. Click **Sign up** → **Continue with GitHub**
3. Authorize Streamlit to access your GitHub repositories
4. You'll land on your Streamlit Cloud dashboard

---

## Step 3 — Deploy the app

1. On your Streamlit Cloud dashboard, click **New app**
2. Fill in the form:

   | Field | Value |
   |-------|-------|
   | **Repository** | `YOUR_GITHUB_USERNAME/My-AI-Workspace` |
   | **Branch** | `main` |
   | **Main file path** | `blog-agent/streamlit_app.py` |
   | **App URL** (optional) | choose a custom slug, e.g. `ai-blog-agent` |

3. Click **Deploy!**

Streamlit Cloud will:
- Clone your repo
- Read `blog-agent/requirements.txt` and install all packages
- Start the app — takes about 2-3 minutes first time

---

## Step 4 — Add your API keys (Secrets)

This is the equivalent of setting Environment Variables in Vercel.

1. After deploy, click the **⋮ (three-dot menu)** next to your app → **Settings**
2. Click the **Secrets** tab
3. Paste the contents of `secrets.toml.example` into the text area
4. Replace every `PASTE_YOUR_..._HERE` with your real keys (see keys below)
5. Click **Save** — the app restarts automatically

### Your API Keys

| Secret | Where to get it | Required? |
|--------|-----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | **Yes** (primary AI) |
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) | Fallback AI |
| `DEVTO_API_KEY` | dev.to → Settings → Extensions → API Key | For Dev.to publishing |
| `MEDIUM_INTEGRATION_TOKEN` | medium.com → Settings → Security → Integration tokens | For Medium publishing |
| `HASHNODE_API_KEY` | hashnode.com → Account Settings → Developer → API Keys | For Hashnode publishing |
| `GITHUB_TOKEN` | [github.com/settings/tokens/new](https://github.com/settings/tokens/new) → select **repo** scope | For website auto-publish |
| `GITHUB_REPO` | e.g. `yourname/My-AI-Workspace` | For website auto-publish |
| `GITHUB_BLOG_PATH` | `ai-website/content/blog` | For website auto-publish |

### Minimal secrets to get started (just AI generation):

```toml
GEMINI_API_KEY  = "AIza..."
GEMINI_MODEL    = "gemini-2.5-flash"
BLOG_NICHE      = "DevOps, Kubernetes, AI Automation"
AUTHOR_NAME     = "AI Insights"
```

Add publishing keys later when you're ready.

---

## Step 5 — Open your app

Click **Open app** (top right on your Streamlit dashboard) or go to:
```
https://YOUR_SLUG.streamlit.app
```

You'll see the AI Blog Agent with 4 tabs:
- **Generate** — type a topic and run the full pipeline
- **Results** — download article, audio, video, diagrams
- **Publish** — one-click publish to your platforms
- **History** — all articles from this session

---

## Updating the app

Any time you push a new version of any file to GitHub:
1. Streamlit Cloud detects the change automatically
2. Or: click **⋮ → Reboot app** to force a refresh

---

## Troubleshooting

### "Module not found: edge_tts"
The app is still installing packages. Wait 2 minutes and reload.

### "ModuleNotFoundError: No module named 'agent_core'"
The **Main file path** in Streamlit settings is wrong.  
Make sure it's set to `blog-agent/streamlit_app.py` (not just `streamlit_app.py`).

### Voice / video steps time out
Streamlit Cloud free tier has a 1 GB RAM limit and processes time out after ~60s per step.  
**Fix:** Toggle OFF "Generate Video" for regular articles (video = heavy). Voice generation is fine.

### "Error: GEMINI_API_KEY not set"
Your secrets haven't been saved yet. Go to app Settings → Secrets → paste and save.

### App goes to sleep after inactivity
Free tier hibernates after ~7 days without traffic. Just open the URL and click **Wake app**.

---

## Your App URLs Summary

| Service | URL |
|---------|-----|
| AI Website | `https://your-site.vercel.app` (already live) |
| Blog Agent | `https://your-slug.streamlit.app` (after this deploy) |
| GitHub Repo | `https://github.com/YOUR_USERNAME/My-AI-Workspace` |

---

## What happens when you click "Publish to Website"

The agent calls the GitHub API directly (using your `GITHUB_TOKEN`):
1. Converts the article to markdown with proper frontmatter
2. Commits it to `ai-website/content/blog/` in your GitHub repo
3. Vercel detects the new commit → rebuilds your website in ~30 seconds
4. The new blog post appears live at `https://your-site.vercel.app/blog/your-topic`

No local git needed. No terminal. Just click.
