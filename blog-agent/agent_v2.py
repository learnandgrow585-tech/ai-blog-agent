"""
╔══════════════════════════════════════════════════════════════════════╗
║          AI BLOG AGENT v2 — Full Money Pipeline                     ║
║                                                                     ║
║  Input : One topic                                                  ║
║  Output: Article + Diagram + Image + SEO + Video + Voice +          ║
║          Social Posts + Auto-published everywhere + Dashboard       ║
║                                                                     ║
║  NEW in v2:                                                         ║
║    ✦ Affiliate links auto-inserted into articles                    ║
║    ✦ Auto-publish to Medium                                         ║
║    ✦ Auto-publish to Hashnode                                       ║
║    ✦ Auto-copy to your website (Next.js content/blog)               ║
║    ✦ Publish log + HTML dashboard                                   ║
║    ✦ Background music in videos                                     ║
╚══════════════════════════════════════════════════════════════════════╝

Usage:
    python agent_v2.py
"""

import os, sys, json, re, time, subprocess, shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── constants ────────────────────────────────────────────────────────
LOG_FILE      = Path("publish_log.json")
DASHBOARD_FILE= Path("dashboard.html")
ASSETS_DIR    = Path("assets")
ASSETS_DIR.mkdir(exist_ok=True)

# ─── colour helpers ───────────────────────────────────────────────────
def pr(msg, color="white"):
    colors = {"green":"\033[92m","yellow":"\033[93m","cyan":"\033[96m",
              "red":"\033[91m","bold":"\033[1m","white":"\033[0m","reset":"\033[0m"}
    print(f"{colors.get(color,'')}{msg}{colors['reset']}")

def banner(text):
    pr(f"\n{'─'*62}", "cyan")
    pr(f"  {text}", "bold")
    pr(f"{'─'*62}", "cyan")

# ─── AI client setup ──────────────────────────────────────────────────
def get_ai_client():
    gemini_key = os.getenv("GEMINI_API_KEY","")
    groq_key   = os.getenv("GROQ_API_KEY","")

    if gemini_key and "PASTE" not in gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(os.getenv("GEMINI_MODEL","gemini-2.5-flash"))
            pr("✓ Using Gemini 2.5 Flash (primary)", "green")
            return ("gemini", model)
        except Exception as e:
            pr(f"⚠ Gemini failed: {e} — trying Groq", "yellow")

    if groq_key and "PASTE" not in groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            pr("✓ Using Groq Llama (fallback)", "green")
            return ("groq", client)
        except Exception as e:
            pr(f"✗ Groq also failed: {e}", "red")

    pr("✗ No working AI key. Edit your .env file and add GEMINI_API_KEY.", "red")
    sys.exit(1)

def ai_generate(client_tuple, prompt, max_tokens=8000):
    kind, client = client_tuple
    if kind == "gemini":
        resp = client.generate_content(prompt)
        return resp.text
    else:
        resp = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL","llama-3.3-70b-versatile"),
            messages=[{"role":"user","content":prompt}],
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content

def clean_json(raw):
    raw = raw.strip()
    raw = re.sub(r'^```json\s*','',raw)
    raw = re.sub(r'^```\s*','',raw)
    raw = re.sub(r'\s*```$','',raw)
    return raw.strip()

# ═══════════════════════════════════════════════════════════════════════
# STEP 1 — GENERATE FULL ARTICLE
# ═══════════════════════════════════════════════════════════════════════
def generate_article(ai, topic):
    banner("STEP 1 — Writing the article...")
    niche  = os.getenv("BLOG_NICHE","DevOps, Kubernetes, AI Automation")
    author = os.getenv("AUTHOR_NAME","Author")

    prompt = f"""You are a senior {niche} engineer writing a detailed technical tutorial.

TOPIC: {topic}

Write a comprehensive, original article following these rules:
1. Start with a strong hook — a real problem engineers face
2. Use proper Markdown: one H1, multiple H2 and H3
3. Include at minimum 2 working code blocks with comments
4. Include a "Common Mistakes to Avoid" section
5. Include a "Key Takeaways" section at the end
6. Length: 1800–2500 words
7. Tone: conversational but technically precise
8. DO NOT use "In today's world" or "In this article we will"
9. Write from real engineering experience
10. Naturally mention relevant AI tools where they fit (ChatGPT, Claude, Cursor, GitHub Copilot, etc.)

Return ONLY valid JSON, no markdown fences:
{{
  "title": "SEO-optimized title (55-60 chars)",
  "meta_description": "Compelling meta description (150-155 chars)",
  "focus_keyword": "primary keyword phrase",
  "slug": "url-friendly-slug",
  "tags": ["tag1","tag2","tag3","tag4","tag5"],
  "read_time_minutes": 8,
  "content": "FULL ARTICLE IN MARKDOWN HERE",
  "excerpt": "2-3 sentence teaser for social sharing"
}}"""

    pr("  ⏳ Generating article (30–60 seconds)...", "yellow")
    raw = clean_json(ai_generate(ai, prompt))

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        data = json.loads(match.group()) if match else {
            "title":topic,"content":raw,"tags":[],
            "slug":topic.lower().replace(" ","-"),
            "meta_description":"","focus_keyword":topic,
            "read_time_minutes":8,"excerpt":""
        }

    pr(f"  ✓ Article: {len(data.get('content','').split())} words", "green")
    pr(f"  ✓ Title  : {data.get('title','')}", "green")
    return data

# ═══════════════════════════════════════════════════════════════════════
# STEP 2 — INSERT AFFILIATE LINKS
# ═══════════════════════════════════════════════════════════════════════
def insert_affiliate_links(article_data):
    banner("STEP 2 — Inserting affiliate links...")

    # Map env vars to tool names that might appear in the article
    affiliate_map = {
        "ChatGPT":       os.getenv("AFFILIATE_CHATGPT",""),
        "Claude":        os.getenv("AFFILIATE_CLAUDE",""),
        "Cursor":        os.getenv("AFFILIATE_CURSOR",""),
        "Midjourney":    os.getenv("AFFILIATE_MIDJOURNEY",""),
        "ElevenLabs":    os.getenv("AFFILIATE_ELEVENLABS",""),
        "Perplexity":    os.getenv("AFFILIATE_PERPLEXITY",""),
        "Notion AI":     os.getenv("AFFILIATE_NOTION",""),
        "Notion":        os.getenv("AFFILIATE_NOTION",""),
        "Zapier":        os.getenv("AFFILIATE_ZAPIER",""),
        "n8n":           os.getenv("AFFILIATE_N8N",""),
        "GitHub Copilot":os.getenv("AFFILIATE_GITHUB_COPILOT",""),
        "Vercel":        os.getenv("AFFILIATE_VERCEL",""),
        "DigitalOcean":  os.getenv("AFFILIATE_DIGITALOCEAN",""),
        "Runway":        os.getenv("AFFILIATE_RUNWAY",""),
        "Jasper":        os.getenv("AFFILIATE_JASPER",""),
        "Grammarly":     os.getenv("AFFILIATE_GRAMMARLY",""),
    }

    content = article_data.get("content","")
    inserted = 0

    for tool_name, url in affiliate_map.items():
        if not url or not tool_name:
            continue
        # Only link first occurrence of each tool, skip if already linked
        # Pattern: tool name NOT already inside a markdown link
        pattern = r'(?<!\[)(?<!\()' + re.escape(tool_name) + r'(?!\])'
        if re.search(pattern, content):
            # Replace first occurrence only
            replacement = f"[{tool_name}]({url})"
            content, n = re.subn(pattern, replacement, content, count=1)
            if n > 0:
                inserted += 1

    article_data["content"] = content
    pr(f"  ✓ Affiliate links inserted: {inserted} tools linked", "green")
    return article_data

# ═══════════════════════════════════════════════════════════════════════
# STEP 3 — GENERATE MERMAID DIAGRAM
# ═══════════════════════════════════════════════════════════════════════
def generate_diagram(ai, topic, article_content):
    banner("STEP 3 — Creating architecture diagram...")

    prompt = f"""Based on this article about "{topic}", create ONE Mermaid.js diagram.

Choose the most appropriate type:
- flowchart TD  (for processes / pipelines)
- sequenceDiagram  (for system interactions)
- graph LR  (for architecture)

Rules:
- Maximum 12 nodes, short labels (3-5 words max)
- Valid Mermaid syntax only

Return ONLY raw Mermaid code, no fences, no explanation.

Article summary: {article_content[:800]}"""

    pr("  ⏳ Generating diagram...", "yellow")
    diagram = clean_json(ai_generate(ai, prompt, max_tokens=500))
    pr("  ✓ Diagram created", "green")
    return diagram.strip()

# ═══════════════════════════════════════════════════════════════════════
# STEP 4 — HEADER IMAGE (Pollinations.ai — FREE, no API key)
# ═══════════════════════════════════════════════════════════════════════
def generate_image_url(topic, title):
    banner("STEP 4 — Generating header image...")
    prompt = (
        f"professional tech blog header, {topic}, "
        "dark background, glowing circuit patterns, blue cyan accent, "
        "modern minimalist, 16:9, no text"
    )
    encoded = prompt.replace(" ","%20").replace(",","%2C")
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&nologo=true"
    pr("  ✓ Image URL ready (Pollinations.ai — free)", "green")
    return url

# ═══════════════════════════════════════════════════════════════════════
# STEP 5 — SEO METADATA
# ═══════════════════════════════════════════════════════════════════════
def generate_seo(ai, article_data, topic):
    banner("STEP 5 — SEO optimization...")

    prompt = f"""Generate SEO metadata for this article.

Title: {article_data.get('title','')}
Focus keyword: {article_data.get('focus_keyword',topic)}
Tags: {article_data.get('tags',[])}

Return ONLY valid JSON:
{{
  "seo_title": "optimized title (max 60 chars)",
  "meta_description": "compelling description (max 155 chars)",
  "og_title": "Open Graph title",
  "schema_keywords": ["kw1","kw2","kw3","kw4","kw5"],
  "internal_link_suggestions": ["next article idea 1","idea 2","idea 3"],
  "seo_score_estimate": 84
}}"""

    pr("  ⏳ Optimizing SEO...", "yellow")
    raw = clean_json(ai_generate(ai, prompt, max_tokens=600))
    try:
        seo = json.loads(raw)
    except:
        seo = {
            "seo_title": article_data.get("title",""),
            "meta_description": article_data.get("meta_description",""),
            "og_title": article_data.get("title",""),
            "schema_keywords": article_data.get("tags",[]),
            "internal_link_suggestions": [],
            "seo_score_estimate": 75
        }

    pr(f"  ✓ SEO score estimate: {seo.get('seo_score_estimate',75)}/100", "green")
    return seo

# ═══════════════════════════════════════════════════════════════════════
# STEP 6 — SOCIAL MEDIA POSTS
# ═══════════════════════════════════════════════════════════════════════
def generate_social_posts(ai, article_data, topic):
    banner("STEP 6 — Writing social media posts...")

    prompt = f"""Write social media posts for this article.

Title: {article_data.get('title','')}
Excerpt: {article_data.get('excerpt','')}
Tags: {article_data.get('tags',[])}

Return ONLY valid JSON:
{{
  "linkedin_post": "Professional post 150-200 words, hook opening, question at end, hashtags",
  "twitter_thread": [
    "Tweet 1: Strong hook (max 280 chars)",
    "Tweet 2: Core insight (max 280 chars)",
    "Tweet 3: Key point (max 280 chars)",
    "Tweet 4: Another takeaway (max 280 chars)",
    "Tweet 5: CTA + link placeholder (max 280 chars)"
  ],
  "dev_to_tags": ["tag1","tag2","tag3","tag4"],
  "hashnode_tags": ["tag1","tag2","tag3"]
}}"""

    pr("  ⏳ Writing social posts...", "yellow")
    raw = clean_json(ai_generate(ai, prompt, max_tokens=1200))
    try:
        social = json.loads(raw)
    except:
        social = {"linkedin_post":"","twitter_thread":[],"dev_to_tags":[],"hashnode_tags":[]}

    pr(f"  ✓ LinkedIn post ready", "green")
    pr(f"  ✓ Twitter thread: {len(social.get('twitter_thread',[]))} tweets", "green")
    return social

# ═══════════════════════════════════════════════════════════════════════
# STEP 7 — VIDEO SCRIPT (Hook Formula)
# ═══════════════════════════════════════════════════════════════════════
def generate_video_script(ai, article_data, topic):
    banner("STEP 7 — Writing 60-second video script...")

    prompt = f"""Write a 60-second YouTube/Instagram Shorts script.

Topic: {topic}
Title: {article_data.get('title','')}
Key insight: {article_data.get('excerpt','')}

CRITICAL STRUCTURE (do not skip any section):
- Second 0-3  : ONE shocking/counter-intuitive statement
- Second 3-15 : Explain the PROBLEM (make viewer feel pain)
- Second 15-45: THE ANSWER in 3 clear steps. Specific, not vague.
- Second 45-55: Show ONE quick win they get immediately
- Second 55-60: "Full guide in bio. Follow for daily {os.getenv('BLOG_NICHE','AI')} tips."

Style: Short sentences. Max 10 words each. NO filler words.

Return ONLY valid JSON:
{{
  "hook_line": "Single most powerful opening line",
  "script_lines": ["Line 1 (0-3s)","Line 2","...","Last line (CTA)"],
  "full_script": "Full script as one readable paragraph",
  "duration_seconds": 58,
  "on_screen_text": ["Text overlay 1","Text overlay 2","Text overlay 3"],
  "thumbnail_text": "Bold thumbnail text (max 6 words)"
}}"""

    pr("  ⏳ Writing video script...", "yellow")
    raw = clean_json(ai_generate(ai, prompt, max_tokens=1000))
    try:
        script = json.loads(raw)
    except:
        script = {
            "hook_line": f"Most engineers don't know this about {topic}",
            "script_lines": [f"Let's talk about {topic}.","Here is what matters."],
            "full_script": f"A guide to {topic}.",
            "duration_seconds": 55,
            "on_screen_text": [topic,"Key Steps","Follow for more"],
            "thumbnail_text": f"{topic} Guide"
        }

    pr(f"  ✓ Script: {len(script.get('script_lines',[]))} lines, hook: {script.get('hook_line','')[:60]}...", "green")
    return script

# ═══════════════════════════════════════════════════════════════════════
# STEP 8 — TEXT TO SPEECH (Edge-TTS — Free)
# ═══════════════════════════════════════════════════════════════════════
def generate_voice(script_data, output_dir):
    banner("STEP 8 — Generating AI voice narration...")

    full_script = script_data.get("full_script","") or " ".join(script_data.get("script_lines",[]))
    audio_path  = output_dir / "narration.mp3"

    try:
        import edge_tts, asyncio
        async def make_audio():
            communicate = edge_tts.Communicate(full_script, voice="en-US-GuyNeural", rate="+10%")
            await communicate.save(str(audio_path))
        asyncio.run(make_audio())
        pr(f"  ✓ Voice narration saved: narration.mp3 (Edge-TTS)", "green")
        return audio_path

    except ImportError:
        pr("  ⚠ edge-tts not installed. Installing...", "yellow")
        subprocess.run([sys.executable,"-m","pip","install","edge-tts","-q"])
        try:
            import edge_tts, asyncio
            async def make_audio():
                communicate = edge_tts.Communicate(full_script, voice="en-US-GuyNeural", rate="+10%")
                await communicate.save(str(audio_path))
            asyncio.run(make_audio())
            pr("  ✓ Voice generated (Edge-TTS)", "green")
            return audio_path
        except Exception as e:
            pr(f"  ⚠ Voice failed: {e}", "yellow")

    # Fallback: save script as text
    (output_dir / "narration_script.txt").write_text(full_script)
    pr("  → Script saved as text. Install edge-tts: pip install edge-tts", "yellow")
    return None

# ═══════════════════════════════════════════════════════════════════════
# STEP 9 — ASSEMBLE VIDEO (MoviePy — Free) with background music
# ═══════════════════════════════════════════════════════════════════════
def assemble_video(script_data, article_data, audio_path, image_url, output_dir):
    banner("STEP 9 — Assembling video short...")

    if audio_path is None:
        pr("  ⚠ No audio — skipping video. Generate voice first.", "yellow")
        return None

    try:
        from moviepy.editor import (
            ColorClip, TextClip, CompositeVideoClip,
            AudioFileClip, concatenate_videoclips, CompositeAudioClip
        )
    except ImportError:
        pr("  ⚠ moviepy not installed. Installing...", "yellow")
        subprocess.run([sys.executable,"-m","pip","install","moviepy","Pillow","-q"])
        try:
            from moviepy.editor import ColorClip, TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip
        except Exception as e:
            pr(f"  ⚠ Could not install moviepy: {e}", "yellow")
            pr("  → Run: pip install moviepy Pillow", "yellow")
            return None

    try:
        video_path = output_dir / "short_video.mp4"
        lines      = script_data.get("script_lines", [])
        duration   = script_data.get("duration_seconds", 55)
        W, H       = 1080, 1920  # 9:16 vertical

        pr("  ⏳ Building video frames...", "yellow")

        # ── Background ──
        bg = ColorClip(size=(W, H), color=(14, 15, 19), duration=duration)

        # ── Voice audio ──
        voice_clip = AudioFileClip(str(audio_path))
        actual_dur = min(voice_clip.duration, duration)
        bg = bg.set_duration(actual_dur)

        # ── Caption clips ──
        clips = [bg]
        n_lines      = len(lines)
        time_per_line= actual_dur / max(n_lines, 1)

        for i, line in enumerate(lines):
            font_size = 76 if i == 0 else 54
            color     = "#4F9CF9" if i == 0 else "white"
            try:
                txt = (TextClip(
                    line, fontsize=font_size, color=color,
                    font="DejaVu-Sans-Bold", method="caption",
                    size=(W - 120, None), align="center"
                )
                .set_start(i * time_per_line)
                .set_duration(time_per_line)
                .set_position(("center", H // 2 - 100))
                .crossfadein(0.25))
                clips.append(txt)
            except Exception:
                try:
                    txt = (TextClip(
                        line, fontsize=font_size, color=color,
                        method="caption", size=(W - 120, None), align="center"
                    )
                    .set_start(i * time_per_line)
                    .set_duration(time_per_line)
                    .set_position(("center", H // 2 - 100)))
                    clips.append(txt)
                except Exception as e2:
                    pr(f"  ⚠ Skipping line {i}: {e2}", "yellow")

        # ── Watermark ──
        try:
            wm = (TextClip(
                f"@{os.getenv('AUTHOR_NAME','YourChannel')}",
                fontsize=36, color="#888888", font="DejaVu-Sans"
            ).set_duration(actual_dur).set_position(("center", H - 140)))
            clips.append(wm)
        except Exception:
            pass

        # ── Audio: mix voice + optional background music ──
        final_audio = voice_clip
        music_path  = os.getenv("BACKGROUND_MUSIC_PATH","")
        if music_path and Path(music_path).exists():
            try:
                music = (AudioFileClip(music_path)
                         .volumex(0.08)          # very quiet background
                         .set_duration(actual_dur))
                final_audio = CompositeAudioClip([voice_clip, music])
                pr("  ✓ Background music added", "green")
            except Exception as e:
                pr(f"  ⚠ Music skipped: {e}", "yellow")

        # ── Render ──
        pr("  ⏳ Rendering video (1-2 minutes)...", "yellow")
        final = CompositeVideoClip(clips).set_audio(final_audio)
        final.write_videofile(
            str(video_path), fps=30,
            codec="libx264", audio_codec="aac",
            logger=None, threads=4
        )

        pr(f"  ✓ Video ready: short_video.mp4 — upload to YouTube Shorts + Reels!", "green")
        return video_path

    except Exception as e:
        pr(f"  ⚠ Video assembly failed: {e}", "yellow")
        pr("  → Article and script are saved. Install moviepy: pip install moviepy", "yellow")
        return None

# ═══════════════════════════════════════════════════════════════════════
# STEP 10 — SAVE ALL LOCAL FILES
# ═══════════════════════════════════════════════════════════════════════
def save_outputs(topic, article, diagram, image_url, seo, social, script, output_dir):
    banner("STEP 10 — Saving all output files...")
    slug   = article.get("slug", topic.lower().replace(" ","-"))
    author = os.getenv("AUTHOR_NAME","AI Insights")

    # ── Markdown article ──
    md_content = f"""---
title: "{article.get('title','')}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
author: "{author}"
excerpt: "{article.get('excerpt','')}"
tags: {json.dumps(article.get('tags',[]))}
featured: true
cover: "{image_url}"
---

{article.get('content','')}

---
*Published by AI Insights Agent | {datetime.now().strftime('%Y-%m-%d')}*
"""
    (output_dir / "article.md").write_text(md_content, encoding="utf-8")
    pr("  ✓ article.md", "green")

    # ── Diagram HTML ──
    (output_dir / "diagram.html").write_text(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{article.get('title','')}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>body{{background:#0e0f13;display:flex;justify-content:center;align-items:center;
min-height:100vh;margin:0;}}
.mermaid{{background:#141720;padding:40px;border-radius:16px;max-width:900px;width:90%;}}</style>
</head><body><div class="mermaid">{diagram}</div>
<script>mermaid.initialize({{startOnLoad:true,theme:'dark'}});</script>
</body></html>""", encoding="utf-8")
    pr("  ✓ diagram.html (open in browser → screenshot)", "green")

    # ── Social posts ──
    thread_text = "\n".join([f"  Tweet {i+1}: {t}" for i,t in enumerate(social.get("twitter_thread",[]))])
    (output_dir / "social_posts.txt").write_text(
        f"LINKEDIN:\n{social.get('linkedin_post','')}\n\nTWITTER THREAD:\n{thread_text}\n",
        encoding="utf-8")
    pr("  ✓ social_posts.txt", "green")

    # ── Video script ──
    lines_text = "\n".join([f"  [{i+1}] {l}" for i,l in enumerate(script.get("script_lines",[]))])
    (output_dir / "video_script.txt").write_text(
        f"HOOK LINE:\n  {script.get('hook_line','')}\n\nSCRIPT LINES:\n{lines_text}\n\n"
        f"FULL SCRIPT:\n{script.get('full_script','')}\n\n"
        f"THUMBNAIL TEXT: {script.get('thumbnail_text','')}\n",
        encoding="utf-8")
    pr("  ✓ video_script.txt", "green")

    # ── SEO file ──
    (output_dir / "seo.txt").write_text(
        f"SEO TITLE       : {seo.get('seo_title','')}\n"
        f"META DESCRIPTION: {seo.get('meta_description','')}\n"
        f"FOCUS KEYWORD   : {article.get('focus_keyword','')}\n"
        f"SEO SCORE EST   : {seo.get('seo_score_estimate',75)}/100\n"
        f"KEYWORDS        : {', '.join(seo.get('schema_keywords',[]))}\n\n"
        f"NEXT ARTICLE IDEAS:\n" +
        "\n".join([f"  → {s}" for s in seo.get("internal_link_suggestions",[])]),
        encoding="utf-8")
    pr("  ✓ seo.txt", "green")

    # ── Dev.to JSON ──
    devto_data = {
        "article": {
            "title":        article.get("title",""),
            "body_markdown":article.get("content",""),
            "published":    False,
            "tags":         social.get("dev_to_tags",article.get("tags",[]))[:4],
            "description":  seo.get("meta_description",""),
            "main_image":   image_url,
        }
    }
    (output_dir / "devto_ready.json").write_text(json.dumps(devto_data, indent=2), encoding="utf-8")
    pr("  ✓ devto_ready.json", "green")

    return slug

# ═══════════════════════════════════════════════════════════════════════
# STEP 11 — PUBLISH TO YOUR WEBSITE (Next.js content/blog)
# ═══════════════════════════════════════════════════════════════════════
def publish_to_website(article, seo, image_url, slug):
    banner("STEP 11 — Publishing to your website...")

    website_path = os.getenv("WEBSITE_CONTENT_PATH","")
    if not website_path:
        pr("  ⚠ WEBSITE_CONTENT_PATH not set in .env — skipping website publish", "yellow")
        pr("  → Set it to: path/to/ai-website/content/blog", "yellow")
        return False

    target_dir = Path(website_path)
    if not target_dir.exists():
        pr(f"  ⚠ Website content folder not found: {target_dir}", "yellow")
        pr("  → Check WEBSITE_CONTENT_PATH in your .env file", "yellow")
        return False

    # Build frontmatter that matches what lib/blog.ts expects via gray-matter
    author = os.getenv("AUTHOR_NAME","AI Insights")
    content = article.get("content","")

    # Strip any existing header image from content (website renders cover separately)
    content = re.sub(r'^!\[.*?\]\(.*?\)\s*\n', '', content.strip())
    # Strip auto-generated footer
    content = re.sub(r'\n---\n\*Published by.*$','', content, flags=re.DOTALL)

    md = f"""---
title: "{article.get('title','').replace('"', "'")}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
author: "{author}"
excerpt: "{article.get('excerpt','').replace('"', "'")}"
tags: {json.dumps(article.get('tags',[]))}
featured: true
cover: "{image_url}"
---

{content.strip()}
"""

    target_file = target_dir / f"{slug}.md"
    target_file.write_text(md, encoding="utf-8")
    pr(f"  ✓ Article copied to website: content/blog/{slug}.md", "green")

    # Optional: git add + commit + push
    auto_push = os.getenv("WEBSITE_AUTO_PUSH","false").lower() == "true"
    if auto_push:
        website_root = target_dir.parent.parent  # ai-website/
        try:
            subprocess.run(["git","-C",str(website_root),"add",str(target_file)], check=True, capture_output=True)
            subprocess.run(["git","-C",str(website_root),"commit",
                            "-m",f"Add blog post: {article.get('title',slug)}"], check=True, capture_output=True)
            subprocess.run(["git","-C",str(website_root),"push"], check=True, capture_output=True)
            pr("  ✓ Git push completed — Vercel will rebuild in ~60 seconds", "green")
        except subprocess.CalledProcessError as e:
            pr(f"  ⚠ Git push failed: {e}. Push manually from GitHub Desktop or github.com", "yellow")
    else:
        pr("  → Set WEBSITE_AUTO_PUSH=true in .env to auto-push to GitHub", "yellow")
        pr("  → Or commit the file manually on github.com and Vercel rebuilds automatically", "yellow")

    return True

# ═══════════════════════════════════════════════════════════════════════
# STEP 12 — PUBLISH TO MEDIUM
# ═══════════════════════════════════════════════════════════════════════
def publish_medium(article, seo, image_url):
    banner("STEP 12 — Publishing to Medium...")

    token = os.getenv("MEDIUM_INTEGRATION_TOKEN","")
    if not token or "PASTE" in token:
        pr("  ⚠ MEDIUM_INTEGRATION_TOKEN not set — skipping", "yellow")
        pr("  → Get token at: https://medium.com/me/settings → Integration tokens", "yellow")
        return False

    import requests as req

    # Get or cache user ID
    user_id = os.getenv("MEDIUM_USER_ID","")
    if not user_id:
        try:
            r = req.get("https://api.medium.com/v1/me",
                        headers={"Authorization": f"Bearer {token}"}, timeout=15)
            if r.status_code == 200:
                user_id = r.json()["data"]["id"]
                pr(f"  ✓ Medium user ID: {user_id}", "green")
                # Hint to add to .env
                pr(f"  → Add to .env: MEDIUM_USER_ID={user_id}", "yellow")
            else:
                pr(f"  ⚠ Medium auth failed ({r.status_code}): {r.text[:200]}", "yellow")
                return False
        except Exception as e:
            pr(f"  ⚠ Medium API error: {e}", "yellow")
            return False

    # Build article content (Medium uses HTML or Markdown)
    content = article.get("content","")
    # Add header image at top
    full_content = f"![Header]({image_url})\n\n{content}"

    payload = {
        "title":         article.get("title",""),
        "contentFormat": "markdown",
        "content":       full_content,
        "tags":          article.get("tags",[])[:5],
        "publishStatus": "public",   # or "draft" if you want to review first
        "notifyFollowers": True
    }

    try:
        r = req.post(
            f"https://api.medium.com/v1/users/{user_id}/posts",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30
        )
        if r.status_code in (200, 201):
            url = r.json().get("data",{}).get("url","")
            pr(f"  ✓ Published to Medium!", "green")
            pr(f"  ✓ URL: {url}", "green")
            return url
        else:
            pr(f"  ⚠ Medium returned {r.status_code}: {r.text[:300]}", "yellow")
            return False
    except Exception as e:
        pr(f"  ⚠ Medium publish failed: {e}", "yellow")
        return False

# ═══════════════════════════════════════════════════════════════════════
# STEP 13 — PUBLISH TO HASHNODE
# ═══════════════════════════════════════════════════════════════════════
def publish_hashnode(article, social, seo, image_url):
    banner("STEP 13 — Publishing to Hashnode...")

    api_key = os.getenv("HASHNODE_API_KEY","")
    pub_id  = os.getenv("HASHNODE_PUBLICATION_ID","")
    if not api_key or not pub_id or "PASTE" in api_key:
        pr("  ⚠ HASHNODE_API_KEY or HASHNODE_PUBLICATION_ID not set — skipping", "yellow")
        pr("  → Get API key at: hashnode.com → Avatar → Account Settings → Developer", "yellow")
        return False

    import requests as req

    # Hashnode uses GraphQL API
    mutation = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) {
        post { url title }
      }
    }"""

    variables = {
        "input": {
            "title":         article.get("title",""),
            "contentMarkdown": article.get("content",""),
            "publicationId": pub_id,
            "tags":          [{"name": t, "slug": t.lower().replace(" ","-")}
                              for t in social.get("hashnode_tags", article.get("tags",[]))[:3]],
            "coverImageOptions": {"coverImageURL": image_url},
            "metaTags": {
                "title":       seo.get("seo_title",""),
                "description": seo.get("meta_description",""),
            }
        }
    }

    try:
        r = req.post(
            "https://gql.hashnode.com",
            json={"query": mutation, "variables": variables},
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=30
        )
        if r.status_code == 200 and "errors" not in r.json():
            url = r.json().get("data",{}).get("publishPost",{}).get("post",{}).get("url","")
            pr(f"  ✓ Published to Hashnode!", "green")
            pr(f"  ✓ URL: {url}", "green")
            return url
        else:
            errors = r.json().get("errors","")
            pr(f"  ⚠ Hashnode error: {errors}", "yellow")
            return False
    except Exception as e:
        pr(f"  ⚠ Hashnode publish failed: {e}", "yellow")
        return False

# ═══════════════════════════════════════════════════════════════════════
# STEP 14 — PUBLISH TO DEV.TO
# ═══════════════════════════════════════════════════════════════════════
def publish_devto(article, social, seo, image_url):
    banner("STEP 14 — Publishing to Dev.to...")

    api_key = os.getenv("DEVTO_API_KEY","")
    if not api_key or "PASTE" in api_key:
        pr("  ⚠ DEVTO_API_KEY not set — skipping", "yellow")
        pr("  → Get key at: dev.to/settings/extensions", "yellow")
        return False

    import requests as req
    payload = {
        "article": {
            "title":         article.get("title",""),
            "body_markdown": article.get("content",""),
            "published":     True,
            "tags":          social.get("dev_to_tags", article.get("tags",[]))[:4],
            "description":   seo.get("meta_description",""),
            "main_image":    image_url,
        }
    }
    try:
        r = req.post("https://dev.to/api/articles",
                     json=payload,
                     headers={"api-key": api_key},
                     timeout=30)
        if r.status_code in (200,201):
            url = f"https://dev.to{r.json().get('path','')}"
            pr(f"  ✓ Published to Dev.to! URL: {url}", "green")
            return url
        else:
            pr(f"  ⚠ Dev.to {r.status_code}: {r.text[:200]}", "yellow")
            return False
    except Exception as e:
        pr(f"  ⚠ Dev.to publish failed: {e}", "yellow")
        return False

# ═══════════════════════════════════════════════════════════════════════
# STEP 15 — UPDATE PUBLISH LOG + HTML DASHBOARD
# ═══════════════════════════════════════════════════════════════════════
def update_dashboard(topic, article, seo, image_url, video_path,
                     devto_url, medium_url, hashnode_url, website_published):
    banner("STEP 15 — Updating dashboard...")

    # ── Load existing log ──
    log = []
    if LOG_FILE.exists():
        try:
            log = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except:
            log = []

    entry = {
        "date":        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topic":       topic,
        "title":       article.get("title",""),
        "slug":        article.get("slug",""),
        "seo_score":   seo.get("seo_score_estimate",75),
        "words":       len(article.get("content","").split()),
        "has_video":   video_path is not None,
        "image_url":   image_url,
        "devto_url":   devto_url or "",
        "medium_url":  medium_url or "",
        "hashnode_url":hashnode_url or "",
        "on_website":  website_published,
    }
    log.append(entry)
    LOG_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Build HTML dashboard ──
    rows = ""
    for i, e in enumerate(reversed(log)):
        links = []
        if e.get("devto_url"):    links.append(f'<a href="{e["devto_url"]}" target="_blank">Dev.to</a>')
        if e.get("medium_url"):   links.append(f'<a href="{e["medium_url"]}" target="_blank">Medium</a>')
        if e.get("hashnode_url"): links.append(f'<a href="{e["hashnode_url"]}" target="_blank">Hashnode</a>')
        if e.get("on_website"):   links.append('<span style="color:#3cdc78">Website ✓</span>')
        links_html = " · ".join(links) if links else '<span style="color:#888">draft only</span>'

        video_badge = '<span style="background:#4f9cf9;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">📹 Video</span>' if e.get("has_video") else ""
        rows += f"""
        <tr>
          <td style="color:#888;font-size:12px">{e['date']}</td>
          <td><strong>{e['title']}</strong><br><small style="color:#888">{e['topic']}</small></td>
          <td>{e['words']:,} words</td>
          <td>{e['seo_score']}/100</td>
          <td>{video_badge}</td>
          <td style="font-size:13px">{links_html}</td>
        </tr>"""

    total_articles = len(log)
    total_videos   = sum(1 for e in log if e.get("has_video"))
    devto_count    = sum(1 for e in log if e.get("devto_url"))
    medium_count   = sum(1 for e in log if e.get("medium_url"))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Blog Agent — Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0e0f13; color: #e5e7eb; font-family: 'Inter', sans-serif; font-size: 14px; line-height: 1.6; padding: 32px; }}
h1 {{ font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; color: #fff; margin-bottom: 6px; }}
.sub {{ color: #888; margin-bottom: 32px; }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
.stat {{ background: #141720; border: 1px solid #1f2937; border-radius: 12px; padding: 20px; }}
.stat .num {{ font-family: 'Syne', sans-serif; font-size: 32px; font-weight: 800; color: #4f9cf9; }}
.stat .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; background: #141720; border-radius: 12px; overflow: hidden; }}
th {{ background: #1a1d26; padding: 12px 16px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #888; }}
td {{ padding: 14px 16px; border-top: 1px solid #1f2937; vertical-align: middle; }}
tr:hover td {{ background: rgba(79,156,249,0.05); }}
a {{ color: #4f9cf9; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
@media (max-width: 700px) {{ .stats {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<h1>📊 AI Blog Agent — Dashboard</h1>
<p class="sub">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} · {total_articles} articles published</p>

<div class="stats">
  <div class="stat"><div class="num">{total_articles}</div><div class="label">Articles Published</div></div>
  <div class="stat"><div class="num">{total_videos}</div><div class="label">Video Shorts Created</div></div>
  <div class="stat"><div class="num">{devto_count}</div><div class="label">Dev.to Posts</div></div>
  <div class="stat"><div class="num">{medium_count}</div><div class="label">Medium Posts</div></div>
</div>

<table>
  <thead>
    <tr>
      <th>Date</th>
      <th>Article</th>
      <th>Length</th>
      <th>SEO</th>
      <th>Video</th>
      <th>Published To</th>
    </tr>
  </thead>
  <tbody>
    {rows if rows else '<tr><td colspan="6" style="text-align:center;color:#888;padding:32px">No articles yet — run the agent to get started!</td></tr>'}
  </tbody>
</table>
</body>
</html>"""

    DASHBOARD_FILE.write_text(html, encoding="utf-8")
    pr(f"  ✓ Dashboard updated: {DASHBOARD_FILE} ({total_articles} total articles)", "green")
    pr(f"  → Open dashboard.html in your browser to see all published content", "cyan")

# ═══════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════
def main():
    pr("\n╔════════════════════════════════════════════════════════════╗", "cyan")
    pr("║        AI BLOG AGENT v2  —  Full Money Pipeline           ║", "cyan")
    pr("║  Article + Diagram + Video + Social + 4 Platforms + Dashboard ║", "cyan")
    pr("╚════════════════════════════════════════════════════════════╝", "cyan")

    print()
    pr("Enter your article topic:", "yellow")
    topic = input("  → ").strip()
    if not topic:
        pr("No topic entered. Exiting.", "red")
        sys.exit(1)

    pr("\nAuto-publish to Dev.to? (y/n):", "yellow")
    do_devto = input("  → ").strip().lower() == "y"

    pr("Auto-publish to Medium? (y/n):", "yellow")
    do_medium = input("  → ").strip().lower() == "y"

    pr("Auto-publish to Hashnode? (y/n):", "yellow")
    do_hashnode = input("  → ").strip().lower() == "y"

    pr("Copy to your website? (y/n):", "yellow")
    do_website = input("  → ").strip().lower() == "y"

    pr("Generate video short? (y/n) [needs moviepy + edge-tts]:", "yellow")
    do_video = input("  → ").strip().lower() == "y"

    # Create output folder
    slug     = re.sub(r'[^a-z0-9\-]','',topic.lower().replace(" ","-"))[:40]
    ts       = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir  = Path("output") / f"{ts}_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pr(f"\n  📁 Output: {out_dir}", "cyan")

    start = time.time()

    # ── Run pipeline ───────────────────────────────────────────────────
    ai       = get_ai_client()
    article  = generate_article(ai, topic)
    article  = insert_affiliate_links(article)
    diagram  = generate_diagram(ai, topic, article.get("content",""))
    img_url  = generate_image_url(topic, article.get("title",""))
    seo      = generate_seo(ai, article, topic)
    social   = generate_social_posts(ai, article, topic)
    script   = generate_video_script(ai, article, topic)

    audio_path = None
    video_path = None
    if do_video:
        audio_path = generate_voice(script, out_dir)
        if audio_path:
            video_path = assemble_video(script, article, audio_path, img_url, out_dir)

    save_outputs(topic, article, diagram, img_url, seo, social, script, out_dir)

    # ── Publish ────────────────────────────────────────────────────────
    website_ok   = False
    devto_url    = None
    medium_url   = None
    hashnode_url = None

    if do_website:
        website_ok   = publish_to_website(article, seo, img_url, article.get("slug", slug))
    if do_devto:
        devto_url    = publish_devto(article, social, seo, img_url)
    if do_medium:
        medium_url   = publish_medium(article, seo, img_url)
    if do_hashnode:
        hashnode_url = publish_hashnode(article, social, seo, img_url)

    # ── Dashboard ──────────────────────────────────────────────────────
    update_dashboard(topic, article, seo, img_url, video_path,
                     devto_url, medium_url, hashnode_url, website_ok)

    # ── Final summary ──────────────────────────────────────────────────
    elapsed = round(time.time() - start, 1)
    banner("✅  ALL DONE!")
    pr(f"\n  Topic      : {topic}", "white")
    pr(f"  Title      : {article.get('title','')}", "white")
    pr(f"  Words      : {len(article.get('content','').split())}", "white")
    pr(f"  SEO Score  : {seo.get('seo_score_estimate',75)}/100", "white")
    pr(f"  Time       : {elapsed}s", "white")
    pr(f"\n  📁 Files in : {out_dir}/", "cyan")
    pr(f"     ├── article.md          ← main article (also on website)", "white")
    pr(f"     ├── diagram.html        ← open in browser, screenshot", "white")
    pr(f"     ├── social_posts.txt    ← LinkedIn + Twitter ready to post", "white")
    pr(f"     ├── video_script.txt    ← 60-sec shorts script", "white")
    pr(f"     └── seo.txt             ← full SEO metadata", "white")
    if audio_path:
        pr(f"     ├── narration.mp3       ← AI voice audio", "white")
    if video_path:
        pr(f"     └── short_video.mp4     ← upload to YouTube Shorts + Reels!", "green")

    pr(f"\n  Published to:", "yellow")
    pr(f"  {'✓' if website_ok   else '—'} Your website (Next.js)", "green" if website_ok   else "white")
    pr(f"  {'✓' if devto_url    else '—'} Dev.to       {devto_url or ''}", "green" if devto_url    else "white")
    pr(f"  {'✓' if medium_url   else '—'} Medium       {medium_url or ''}", "green" if medium_url   else "white")
    pr(f"  {'✓' if hashnode_url else '—'} Hashnode     {hashnode_url or ''}", "green" if hashnode_url else "white")

    pr(f"\n  📊 Dashboard updated → open dashboard.html in your browser", "cyan")

    pr(f"\n  Next article suggestions:", "yellow")
    for s in seo.get("internal_link_suggestions",[])[:3]:
        pr(f"  → {s}", "cyan")

    pr("\n  Happy publishing! 🚀\n", "green")


if __name__ == "__main__":
    main()
