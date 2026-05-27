"""
╔══════════════════════════════════════════════════════════════════╗
║          AI BLOG AGENT — Full Pipeline                          ║
║  Input : Topic                                                  ║
║  Output: Article + Diagram + Image + SEO + Video Script + Voice ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python agent.py
    Then type your topic when prompted.
"""

import os, sys, json, re, time, textwrap, subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── colour helpers ─────────────────────────────────────────────────
def pr(msg, color="white"):
    colors = {"green":"\033[92m","yellow":"\033[93m","cyan":"\033[96m",
               "red":"\033[91m","bold":"\033[1m","white":"\033[0m","reset":"\033[0m"}
    print(f"{colors.get(color,'')}{msg}{colors['reset']}")

def banner(text):
    pr(f"\n{'─'*60}", "cyan")
    pr(f"  {text}", "bold")
    pr(f"{'─'*60}", "cyan")

# ── AI client setup ────────────────────────────────────────────────
def get_ai_client():
    """Try Gemini first, fall back to Groq."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    groq_key   = os.getenv("GROQ_API_KEY", "")

    if gemini_key and gemini_key != "your_new_gemini_key":
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
            pr("✓ Using Gemini 2.5 Flash (primary)", "green")
            return ("gemini", model)
        except Exception as e:
            pr(f"⚠ Gemini failed: {e} — trying Groq", "yellow")

    if groq_key and groq_key != "your_new_groq_key":
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            pr("✓ Using Groq Llama (fallback)", "green")
            return ("groq", client)
        except Exception as e:
            pr(f"✗ Groq also failed: {e}", "red")

    pr("✗ No working AI key found. Check your .env file.", "red")
    sys.exit(1)

def ai_generate(client_tuple, prompt, max_tokens=8000):
    """Generate text using whichever AI client is active."""
    kind, client = client_tuple
    if kind == "gemini":
        resp = client.generate_content(prompt)
        return resp.text
    else:
        resp = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content

# ═══════════════════════════════════════════════════════════════════
# STEP 1 — GENERATE FULL ARTICLE
# ═══════════════════════════════════════════════════════════════════
def generate_article(ai, topic):
    banner("STEP 1 — Writing the article...")
    niche  = os.getenv("BLOG_NICHE", "DevOps, Kubernetes, AI Automation")
    author = os.getenv("AUTHOR_NAME", "Author")

    prompt = f"""You are a senior {niche} engineer writing a detailed technical tutorial blog post.

TOPIC: {topic}

Write a comprehensive, original article following these rules:
1. Start with a strong hook — a real problem engineers face
2. Use proper Markdown headings: one H1, multiple H2 and H3
3. Include at minimum 2 working code blocks with comments
4. Include a "Common Mistakes to Avoid" section
5. Include a "Key Takeaways" section at the end
6. Length: 1800–2500 words
7. Tone: conversational but technically precise
8. DO NOT use generic phrases like "In today's world" or "In this article we will"
9. Write from real engineering experience

Return ONLY valid JSON, no markdown fences, no preamble:
{{
  "title": "SEO-optimized title (55-60 chars)",
  "meta_description": "Compelling meta description (150-155 chars)",
  "focus_keyword": "primary keyword phrase",
  "slug": "url-friendly-slug",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "read_time_minutes": 8,
  "content": "FULL ARTICLE IN MARKDOWN HERE",
  "excerpt": "2-3 sentence teaser for social sharing"
}}"""

    pr("  ⏳ Generating article (30–60 seconds)...", "yellow")
    raw = ai_generate(ai, prompt)

    # strip any accidental fences
    raw = re.sub(r'^```json\s*', '', raw.strip())
    raw = re.sub(r'^```\s*',     '', raw.strip())
    raw = re.sub(r'\s*```$',     '', raw.strip())

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # try to extract JSON block
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            pr("⚠ Could not parse JSON — saving raw output", "yellow")
            data = {"title": topic, "content": raw, "tags": [], "slug": topic.lower().replace(" ","-"),
                    "meta_description": "", "focus_keyword": topic, "read_time_minutes": 8, "excerpt": ""}

    pr(f"  ✓ Article written: {len(data.get('content','').split())} words", "green")
    pr(f"  ✓ Title: {data.get('title','')}", "green")
    return data

# ═══════════════════════════════════════════════════════════════════
# STEP 2 — GENERATE MERMAID DIAGRAM
# ═══════════════════════════════════════════════════════════════════
def generate_diagram(ai, topic, article_content):
    banner("STEP 2 — Creating flow diagram...")

    prompt = f"""Based on this technical article about "{topic}", create ONE Mermaid.js diagram.

Choose the most appropriate diagram type:
- flowchart TD  (for processes / pipelines)
- sequenceDiagram  (for system interactions)
- graph LR  (for architecture)

Rules:
- Maximum 12 nodes
- Node labels must be short (3-5 words max)
- Use meaningful connection labels
- Must be valid Mermaid syntax

Return ONLY the raw Mermaid code, no explanation, no fences:

Article summary: {article_content[:800]}"""

    pr("  ⏳ Generating diagram...", "yellow")
    diagram_code = ai_generate(ai, prompt, max_tokens=500)

    # clean up
    diagram_code = re.sub(r'^```mermaid\s*', '', diagram_code.strip())
    diagram_code = re.sub(r'^```\s*',         '', diagram_code.strip())
    diagram_code = re.sub(r'\s*```$',         '', diagram_code.strip())

    pr("  ✓ Diagram code generated", "green")
    return diagram_code.strip()

# ═══════════════════════════════════════════════════════════════════
# STEP 3 — GENERATE HEADER IMAGE URL (Pollinations.ai — FREE)
# ═══════════════════════════════════════════════════════════════════
def generate_image_url(topic, title):
    banner("STEP 3 — Creating header image URL...")
    # Pollinations.ai is 100% free, no API key, just a URL
    image_prompt = (
        f"professional tech blog header image, {topic}, "
        "dark background, glowing circuit patterns, blue and cyan accent colors, "
        "modern minimalist style, 16:9 aspect ratio, no text"
    )
    encoded = image_prompt.replace(" ", "%20").replace(",", "%2C")
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&nologo=true"
    pr(f"  ✓ Image URL generated (Pollinations.ai — free)", "green")
    return url

# ═══════════════════════════════════════════════════════════════════
# STEP 4 — GENERATE SEO METADATA
# ═══════════════════════════════════════════════════════════════════
def generate_seo(ai, article_data, topic):
    banner("STEP 4 — SEO optimization...")

    prompt = f"""Given this blog article data, generate optimized SEO metadata.

Title: {article_data.get('title','')}
Focus keyword: {article_data.get('focus_keyword', topic)}
Tags: {article_data.get('tags', [])}

Return ONLY valid JSON:
{{
  "seo_title": "title optimized for search (max 60 chars)",
  "meta_description": "compelling description (max 155 chars)",
  "og_title": "Open Graph title for social sharing",
  "twitter_title": "Twitter card title",
  "schema_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "internal_link_suggestions": ["related topic 1", "related topic 2", "related topic 3"],
  "seo_score_estimate": 82
}}"""

    pr("  ⏳ Optimizing SEO...", "yellow")
    raw = ai_generate(ai, prompt, max_tokens=600)
    raw = re.sub(r'^```json\s*','',raw.strip())
    raw = re.sub(r'^```\s*','',raw.strip())
    raw = re.sub(r'\s*```$','',raw.strip())

    try:
        seo = json.loads(raw)
    except:
        seo = {
            "seo_title": article_data.get("title",""),
            "meta_description": article_data.get("meta_description",""),
            "og_title": article_data.get("title",""),
            "twitter_title": article_data.get("title",""),
            "schema_keywords": article_data.get("tags",[]),
            "internal_link_suggestions": [],
            "seo_score_estimate": 75
        }

    pr(f"  ✓ SEO score estimate: {seo.get('seo_score_estimate',75)}/100", "green")
    return seo

# ═══════════════════════════════════════════════════════════════════
# STEP 5 — GENERATE SOCIAL MEDIA POSTS
# ═══════════════════════════════════════════════════════════════════
def generate_social_posts(ai, article_data, topic):
    banner("STEP 5 — Writing social media posts...")

    prompt = f"""Write social media posts for this blog article.

Article title: {article_data.get('title','')}
Topic: {topic}
Excerpt: {article_data.get('excerpt','')}
Tags: {article_data.get('tags',[])}

Return ONLY valid JSON:
{{
  "linkedin_post": "Professional LinkedIn post, 150-200 words, starts with a hook, ends with a question to drive comments. Use line breaks for readability. Add relevant hashtags at end.",
  "twitter_thread": [
    "Tweet 1: Strong hook that makes people click (max 280 chars)",
    "Tweet 2: The core insight (max 280 chars)",
    "Tweet 3: Key point with code snippet hint (max 280 chars)",
    "Tweet 4: Another key takeaway (max 280 chars)",
    "Tweet 5: Call to action + link placeholder (max 280 chars)"
  ],
  "dev_to_tags": ["tag1", "tag2", "tag3", "tag4"],
  "hashnode_tags": ["tag1", "tag2", "tag3"]
}}"""

    pr("  ⏳ Writing social posts...", "yellow")
    raw = ai_generate(ai, prompt, max_tokens=1200)
    raw = re.sub(r'^```json\s*','',raw.strip())
    raw = re.sub(r'^```\s*','',raw.strip())
    raw = re.sub(r'\s*```$','',raw.strip())

    try:
        social = json.loads(raw)
    except:
        social = {"linkedin_post": "", "twitter_thread": [], "dev_to_tags": [], "hashnode_tags": []}

    pr("  ✓ LinkedIn post written", "green")
    pr(f"  ✓ Twitter thread: {len(social.get('twitter_thread',[]))} tweets", "green")
    return social

# ═══════════════════════════════════════════════════════════════════
# STEP 6 — GENERATE VIDEO SCRIPT (Hook Formula)
# ═══════════════════════════════════════════════════════════════════
def generate_video_script(ai, article_data, topic):
    banner("STEP 6 — Writing video short script...")

    prompt = f"""Write a 60-second YouTube/Instagram Shorts script for this technical article.

Topic: {topic}
Title: {article_data.get('title','')}
Key insight: {article_data.get('excerpt','')}

CRITICAL RULES — this script must NOT be skipped:
- Second 0-3: ONE shocking/surprising statement. Make it controversial or counter-intuitive.
  Example: "Most DevOps engineers are doing Kubernetes wrong — and it's costing them hours every week."
- Second 3-15: Explain the PROBLEM clearly. Make the viewer feel pain.
- Second 15-45: Give THE ANSWER in 3 clear steps. Be specific, not vague.
- Second 45-55: Show ONE quick win / result they get immediately.
- Second 55-60: Call to action — "Full guide in bio. Follow for daily {os.getenv('BLOG_NICHE','DevOps AI')} tips."

Style rules:
- Short sentences. Max 10 words per sentence.
- Conversational. Like talking to a colleague.
- NO filler words: "basically", "actually", "so", "um"
- Each line = one spoken sentence (for caption display)

Return ONLY valid JSON:
{{
  "hook_line": "The single most powerful opening line",
  "script_lines": [
    "Line 1 (0-3s hook)",
    "Line 2",
    "Line 3",
    "...",
    "Last line (CTA)"
  ],
  "full_script": "Full script as one readable paragraph",
  "duration_seconds": 58,
  "on_screen_text": ["Text overlay 1", "Text overlay 2", "Text overlay 3"],
  "thumbnail_text": "Bold text for video thumbnail (max 6 words)"
}}"""

    pr("  ⏳ Writing video script...", "yellow")
    raw = ai_generate(ai, prompt, max_tokens=1000)
    raw = re.sub(r'^```json\s*','',raw.strip())
    raw = re.sub(r'^```\s*','',raw.strip())
    raw = re.sub(r'\s*```$','',raw.strip())

    try:
        script = json.loads(raw)
    except:
        script = {
            "hook_line": f"Most engineers don't know this about {topic}",
            "script_lines": [f"Let's talk about {topic}.", "Here is what you need to know."],
            "full_script": f"A guide to {topic}.",
            "duration_seconds": 55,
            "on_screen_text": [topic, "Key Steps", "Follow for more"],
            "thumbnail_text": f"{topic} Guide"
        }

    pr(f"  ✓ Script written: {len(script.get('script_lines',[]))} lines", "green")
    pr(f"  ✓ Hook: {script.get('hook_line','')[:70]}...", "green")
    return script

# ═══════════════════════════════════════════════════════════════════
# STEP 7 — TEXT TO SPEECH (Edge-TTS — Free, no API key)
# ═══════════════════════════════════════════════════════════════════
def generate_voice(script_data, output_dir):
    banner("STEP 7 — Generating AI voice narration...")

    full_script = script_data.get("full_script", "")
    if not full_script:
        full_script = " ".join(script_data.get("script_lines", []))

    audio_path = output_dir / "narration.mp3"

    # Try edge-tts (Microsoft free voices)
    try:
        import edge_tts
        import asyncio

        async def make_audio():
            # en-US-GuyNeural — clear, professional male voice
            communicate = edge_tts.Communicate(full_script, voice="en-US-GuyNeural", rate="+10%")
            await communicate.save(str(audio_path))

        asyncio.run(make_audio())
        pr(f"  ✓ Voice generated: {audio_path.name} (Edge-TTS)", "green")
        return audio_path

    except ImportError:
        pr("  ⚠ edge-tts not installed. Installing now...", "yellow")
        subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts", "-q"])
        try:
            import edge_tts, asyncio
            async def make_audio():
                communicate = edge_tts.Communicate(full_script, voice="en-US-GuyNeural", rate="+10%")
                await communicate.save(str(audio_path))
            asyncio.run(make_audio())
            pr(f"  ✓ Voice generated (Edge-TTS)", "green")
            return audio_path
        except Exception as e:
            pr(f"  ⚠ Voice generation failed: {e}", "yellow")
            pr("  → Saving script as text. Install edge-tts manually: pip install edge-tts", "yellow")
            # Save script as fallback
            script_txt = output_dir / "narration_script.txt"
            script_txt.write_text(full_script)
            return None

    except Exception as e:
        pr(f"  ⚠ Voice generation failed: {e}", "yellow")
        script_txt = output_dir / "narration_script.txt"
        script_txt.write_text(full_script)
        pr("  → Script saved as text file for manual recording", "yellow")
        return None

# ═══════════════════════════════════════════════════════════════════
# STEP 8 — ASSEMBLE VIDEO (MoviePy — Free)
# ═══════════════════════════════════════════════════════════════════
def assemble_video(script_data, article_data, audio_path, image_url, output_dir):
    banner("STEP 8 — Assembling video short...")

    if audio_path is None:
        pr("  ⚠ No audio file — skipping video assembly", "yellow")
        pr("  → Generate audio first, then re-run with existing output folder", "yellow")
        return None

    try:
        from moviepy.editor import (
            ColorClip, TextClip, CompositeVideoClip,
            AudioFileClip, concatenate_videoclips
        )
        import requests as req
        from PIL import Image
        import numpy as np
        import io
    except ImportError:
        pr("  ⚠ moviepy or Pillow not installed. Installing...", "yellow")
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "moviepy", "Pillow", "requests", "-q"])
        try:
            from moviepy.editor import ColorClip, TextClip, CompositeVideoClip, AudioFileClip
            import requests as req
            from PIL import Image
            import numpy as np
            import io
        except Exception as e:
            pr(f"  ⚠ Could not install moviepy: {e}", "yellow")
            pr("  → Run: pip install moviepy Pillow", "yellow")
            return None

    try:
        video_path = output_dir / "short_video.mp4"
        lines      = script_data.get("script_lines", [])
        duration   = script_data.get("duration_seconds", 55)
        W, H       = 1080, 1920   # 9:16 vertical for Shorts/Reels

        pr("  ⏳ Building video frames...", "yellow")

        # ── Background: dark gradient ──
        bg = ColorClip(size=(W, H), color=(14, 15, 19), duration=duration)

        # ── Load audio ──
        audio_clip = AudioFileClip(str(audio_path))
        actual_dur = min(audio_clip.duration, duration)
        bg = bg.set_duration(actual_dur)

        # ── Caption clips — word by word appearance ──
        clips = [bg]
        n_lines = len(lines)
        time_per_line = actual_dur / max(n_lines, 1)

        for i, line in enumerate(lines):
            start_t = i * time_per_line
            line_dur = time_per_line

            # First line = hook — BIG text
            font_size = 72 if i == 0 else 52
            color     = "white" if i != 0 else "#4F9CF9"

            try:
                txt_clip = (TextClip(
                    line,
                    fontsize=font_size,
                    color=color,
                    font="DejaVu-Sans-Bold",
                    method="caption",
                    size=(W - 120, None),
                    align="center"
                )
                .set_start(start_t)
                .set_duration(line_dur)
                .set_position(("center", H // 2 - 100))
                .crossfadein(0.3))
                clips.append(txt_clip)
            except Exception:
                # fallback font
                try:
                    txt_clip = (TextClip(
                        line,
                        fontsize=font_size,
                        color=color,
                        method="caption",
                        size=(W - 120, None),
                        align="center"
                    )
                    .set_start(start_t)
                    .set_duration(line_dur)
                    .set_position(("center", H // 2 - 100))
                    .crossfadein(0.3))
                    clips.append(txt_clip)
                except Exception as e2:
                    pr(f"  ⚠ Skipping caption line {i}: {e2}", "yellow")

        # ── Watermark / channel name ──
        try:
            wm = (TextClip(
                f"@{os.getenv('AUTHOR_NAME','YourChannel')}",
                fontsize=36, color="#aaaaaa", font="DejaVu-Sans"
            )
            .set_duration(actual_dur)
            .set_position(("center", H - 140)))
            clips.append(wm)
        except Exception:
            pass

        # ── Compose and write ──
        pr("  ⏳ Rendering video (this takes 1-2 minutes)...", "yellow")
        final = CompositeVideoClip(clips).set_audio(audio_clip)
        final.write_videofile(
            str(video_path),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            logger=None,
            threads=4
        )

        pr(f"  ✓ Video created: {video_path.name}", "green")
        pr(f"  ✓ Ready to upload to YouTube Shorts and Instagram Reels!", "green")
        return video_path

    except Exception as e:
        pr(f"  ⚠ Video assembly failed: {e}", "yellow")
        pr("  → Article and script are ready. Install moviepy to enable video: pip install moviepy", "yellow")
        return None

# ═══════════════════════════════════════════════════════════════════
# STEP 9 — SAVE ALL OUTPUTS
# ═══════════════════════════════════════════════════════════════════
def save_outputs(topic, article, diagram, image_url, seo, social, script, output_dir):
    banner("STEP 9 — Saving all outputs...")
    slug = article.get("slug", topic.lower().replace(" ", "-"))

    # ── 1. Markdown article file ──────────────────────────────────
    md_path = output_dir / "article.md"
    md_content = f"""---
title: "{article.get('title','')}"
meta_description: "{seo.get('meta_description','')}"
focus_keyword: "{article.get('focus_keyword','')}"
slug: "{slug}"
tags: {article.get('tags',[])}
read_time: {article.get('read_time_minutes', 8)} min
image: "{image_url}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
---

![Header Image]({image_url})

{article.get('content','')}

---
*Generated by AI Blog Agent | {datetime.now().strftime('%Y-%m-%d')}*
"""
    md_path.write_text(md_content, encoding="utf-8")
    pr(f"  ✓ Article saved: article.md", "green")

    # ── 2. Mermaid diagram HTML (renders in browser) ──────────────
    diagram_path = output_dir / "diagram.html"
    diagram_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Diagram — {article.get('title','')}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>
body {{ background:#0e0f13; display:flex; justify-content:center; align-items:center;
       min-height:100vh; margin:0; font-family:sans-serif; }}
.mermaid {{ background:#141720; padding:40px; border-radius:16px; max-width:900px; width:90%; }}
h2 {{ color:#4f9cf9; text-align:center; margin-bottom:24px; font-size:18px; }}
</style>
</head>
<body>
<div>
<h2>{article.get('title','')}</h2>
<div class="mermaid">
{diagram}
</div>
</div>
<script>mermaid.initialize({{startOnLoad:true, theme:'dark'}});</script>
</body>
</html>"""
    diagram_path.write_text(diagram_html, encoding="utf-8")
    pr(f"  ✓ Diagram saved: diagram.html (open in browser to view)", "green")

    # ── 3. Social media posts ─────────────────────────────────────
    social_path = output_dir / "social_posts.txt"
    twitter_thread = "\n".join([f"  Tweet {i+1}: {t}" for i,t in enumerate(social.get("twitter_thread",[]))])
    social_content = f"""═══════════════════════════════════════════════
SOCIAL POSTS — {article.get('title','')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
═══════════════════════════════════════════════

── LINKEDIN POST ───────────────────────────────
{social.get('linkedin_post','')}

── TWITTER/X THREAD ────────────────────────────
{twitter_thread}

── DEV.TO TAGS ─────────────────────────────────
{', '.join(social.get('dev_to_tags',[]))}

── HASHNODE TAGS ───────────────────────────────
{', '.join(social.get('hashnode_tags',[]))}
"""
    social_path.write_text(social_content, encoding="utf-8")
    pr(f"  ✓ Social posts saved: social_posts.txt", "green")

    # ── 4. Video script ───────────────────────────────────────────
    script_path = output_dir / "video_script.txt"
    lines_text  = "\n".join([f"  [{i+1}] {l}" for i,l in enumerate(script.get("script_lines",[]))])
    script_content = f"""═══════════════════════════════════════════════
VIDEO SHORT SCRIPT — {article.get('title','')}
Duration: ~{script.get('duration_seconds',55)} seconds
═══════════════════════════════════════════════

HOOK LINE (say this FIRST — 0-3 seconds):
  {script.get('hook_line','')}

FULL SCRIPT LINES:
{lines_text}

FULL SCRIPT (for TTS / reading):
{script.get('full_script','')}

ON-SCREEN TEXT OVERLAYS:
{chr(10).join(['  • ' + t for t in script.get('on_screen_text',[])])}

THUMBNAIL TEXT:
  {script.get('thumbnail_text','')}
"""
    script_path.write_text(script_content, encoding="utf-8")
    pr(f"  ✓ Video script saved: video_script.txt", "green")

    # ── 5. SEO summary ────────────────────────────────────────────
    seo_path = output_dir / "seo.txt"
    seo_content = f"""═══════════════════════════════════════════════
SEO DATA — {article.get('title','')}
═══════════════════════════════════════════════

SEO Title:        {seo.get('seo_title','')}
Meta Description: {seo.get('meta_description','')}
OG Title:         {seo.get('og_title','')}
Focus Keyword:    {article.get('focus_keyword','')}
SEO Score Est:    {seo.get('seo_score_estimate',75)}/100

Keywords: {', '.join(seo.get('schema_keywords',[]))}

Suggested internal links (write these articles next!):
{chr(10).join(['  → ' + s for s in seo.get('internal_link_suggestions',[])])}

Header Image URL:
{image_url}
"""
    seo_path.write_text(seo_content, encoding="utf-8")
    pr(f"  ✓ SEO data saved: seo.txt", "green")

    # ── 6. Dev.to ready JSON ──────────────────────────────────────
    devto_path = output_dir / "devto_ready.json"
    devto_data = {
        "article": {
            "title":         article.get("title",""),
            "body_markdown": article.get("content",""),
            "published":     False,   # set True to auto-publish
            "tags":          social.get("dev_to_tags", article.get("tags",[]))[:4],
            "description":   seo.get("meta_description",""),
            "canonical_url": ""       # add your site URL here later
        }
    }
    devto_path.write_text(json.dumps(devto_data, indent=2), encoding="utf-8")
    pr(f"  ✓ Dev.to payload saved: devto_ready.json", "green")

    return {
        "article_md":   md_path,
        "diagram_html": diagram_path,
        "social_txt":   social_path,
        "video_script": script_path,
        "seo_txt":      seo_path,
        "devto_json":   devto_path,
    }

# ═══════════════════════════════════════════════════════════════════
# STEP 10 — PUBLISH TO DEV.TO
# ═══════════════════════════════════════════════════════════════════
def publish_devto(article, social, seo, image_url):
    banner("STEP 10 — Publishing to Dev.to...")
    api_key = os.getenv("DEVTO_API_KEY","")
    if not api_key or api_key == "your_new_devto_key":
        pr("  ⚠ No Dev.to API key in .env — skipping auto-publish", "yellow")
        pr("  → Article saved in devto_ready.json — copy-paste manually", "yellow")
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
        r = req.post(
            "https://dev.to/api/articles",
            json=payload,
            headers={"api-key": api_key},
            timeout=30
        )
        if r.status_code in (200, 201):
            data = r.json()
            pr(f"  ✓ Published to Dev.to!", "green")
            pr(f"  ✓ URL: https://dev.to{data.get('path','')}", "green")
            return True
        else:
            pr(f"  ⚠ Dev.to returned {r.status_code}: {r.text[:200]}", "yellow")
            return False
    except Exception as e:
        pr(f"  ⚠ Dev.to publish failed: {e}", "yellow")
        return False

# ═══════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════
def main():
    pr("\n╔══════════════════════════════════════════════════════╗", "cyan")
    pr("║         AI BLOG AGENT  —  by Your Team              ║", "cyan")
    pr("║   Blog + Diagram + Image + Social + Video + Voice   ║", "cyan")
    pr("╚══════════════════════════════════════════════════════╝", "cyan")

    # get topic
    print()
    pr("Enter your article topic:", "yellow")
    topic = input("  → ").strip()
    if not topic:
        pr("No topic entered. Exiting.", "red")
        sys.exit(1)

    # ask about publishing
    pr("\nAuto-publish to Dev.to? (y/n):", "yellow")
    do_publish = input("  → ").strip().lower() == "y"

    # ask about video
    pr("Generate video short? (y/n) [needs moviepy + edge-tts]:", "yellow")
    do_video = input("  → ").strip().lower() == "y"

    # create output folder
    slug = topic.lower().replace(" ","-").replace("/","-")[:40]
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path("output") / f"{ts}_{slug}"
    output_dir.mkdir(parents=True, exist_ok=True)
    pr(f"\n  📁 Output folder: {output_dir}", "cyan")

    start = time.time()

    # ── run pipeline ──────────────────────────────────────────────
    ai      = get_ai_client()
    article = generate_article(ai, topic)
    diagram = generate_diagram(ai, topic, article.get("content",""))
    img_url = generate_image_url(topic, article.get("title",""))
    seo     = generate_seo(ai, article, topic)
    social  = generate_social_posts(ai, article, topic)
    script  = generate_video_script(ai, article, topic)

    audio_path = None
    video_path = None
    if do_video:
        audio_path = generate_voice(script, output_dir)
        if audio_path:
            video_path = assemble_video(script, article, audio_path, img_url, output_dir)

    files = save_outputs(topic, article, diagram, img_url, seo, social, script, output_dir)

    if do_publish:
        publish_devto(article, social, seo, img_url)

    # ── final summary ─────────────────────────────────────────────
    elapsed = round(time.time() - start, 1)
    banner("✅  ALL DONE!")
    pr(f"\n  Topic    : {topic}", "white")
    pr(f"  Title    : {article.get('title','')}", "white")
    pr(f"  Words    : {len(article.get('content','').split())}", "white")
    pr(f"  SEO Score: {seo.get('seo_score_estimate',75)}/100", "white")
    pr(f"  Time     : {elapsed}s", "white")
    pr(f"\n  📁 All files in: {output_dir}/", "cyan")
    pr(f"     ├── article.md          ← copy to Medium / Hashnode", "white")
    pr(f"     ├── diagram.html        ← open in browser, screenshot it", "white")
    pr(f"     ├── social_posts.txt    ← LinkedIn + Twitter ready", "white")
    pr(f"     ├── video_script.txt    ← YouTube short script", "white")
    pr(f"     ├── seo.txt             ← all SEO metadata", "white")
    pr(f"     └── devto_ready.json    ← auto-published or copy-paste", "white")

    if audio_path:
        pr(f"     ├── narration.mp3       ← AI voice audio", "white")
    if video_path:
        pr(f"     └── short_video.mp4     ← upload to YouTube Shorts + Reels!", "green")

    pr(f"\n  Next article suggestion:", "yellow")
    suggestions = seo.get("internal_link_suggestions", [])
    for s in suggestions[:3]:
        pr(f"  → {s}", "cyan")

    pr("\n  Happy publishing! 🚀\n", "green")

if __name__ == "__main__":
    main()
