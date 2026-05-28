"""
agent_core.py — All pipeline logic, no CLI / UI code.
Used by both agent_v2.py (CLI) and streamlit_app.py (web).
"""

import os, json, re
from datetime import datetime


def clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*',     '', raw)
    raw = re.sub(r'\s*```$',     '', raw)
    return raw.strip()


def safe_parse_article_json(raw: str, fallback_topic: str = "") -> dict:
    """
    Parse AI-returned article JSON with 4 fallback strategies.
    Handles: unescaped newlines/quotes in content field, truncated output,
    markdown code fences, and other common LLM JSON quirks.
    """
    # ── Strategy 1: direct parse ──────────────────────────────────────
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # ── Strategy 2: find outermost {} block ───────────────────────────
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    # ── Strategy 3: re-escape the content field then reparse ──────────
    # The "content" field is almost always what breaks JSON — it's long
    # markdown with newlines, backtick fences, and double-quotes.
    try:
        cs = re.search(r'"content"\s*:\s*"', raw)
        if cs:
            after = raw[cs.end():]
            # content ends where "excerpt" or "}" begins at same level
            end_m = re.search(r'",?\s*"excerpt"\s*:', after)
            if end_m:
                content_raw = after[:end_m.start()]
                # escape bare newlines / carriage returns inside the string
                content_safe = content_raw.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')
                rebuilt = raw[:cs.end()] + content_safe + after[end_m.start():]
                return json.loads(rebuilt)
    except Exception:
        pass

    # ── Strategy 4: field-by-field regex extraction ───────────────────
    def _str(field: str) -> str:
        m = re.search(rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        if m:
            return m.group(1).replace('\\n', '\n').replace('\\"', '"')
        return ""

    def _int(field: str, default: int) -> int:
        m = re.search(rf'"{field}"\s*:\s*(\d+)', raw)
        return int(m.group(1)) if m else default

    def _list(field: str) -> list:
        m = re.search(rf'"{field}"\s*:\s*\[(.*?)\]', raw, re.DOTALL)
        return re.findall(r'"([^"]+)"', m.group(1)) if m else []

    # content: grab everything between "content": " and the next field
    content = ""
    m = re.search(r'"content"\s*:\s*"([\s\S]+?)"(?:\s*,\s*"|\s*\})', raw)
    if m:
        content = m.group(1).replace('\\n', '\n').replace('\\"', '"')
    else:
        m = re.search(r'"content"\s*:\s*"([\s\S]+)', raw)
        if m:
            content = m.group(1)[:10000]

    slug = _str("slug") or re.sub(r'[^a-z0-9\-]', '', fallback_topic.lower().replace(" ", "-"))[:50]

    return {
        "title":             _str("title")            or fallback_topic,
        "meta_description":  _str("meta_description"),
        "focus_keyword":     _str("focus_keyword")    or fallback_topic,
        "slug":              slug,
        "tags":              _list("tags"),
        "read_time_minutes": _int("read_time_minutes", 8),
        "content":           content or raw,
        "excerpt":           _str("excerpt"),
    }


# ─── AI client ────────────────────────────────────────────────────────

def get_ai_client(gemini_key: str, groq_key: str, gemini_model: str = "gemini-2.5-flash", groq_model: str = "llama-3.3-70b-versatile"):
    """
    Returns 4-tuple: (kind, primary_client, model, groq_fallback_or_None)
    groq_fallback is (groq_client, groq_model) used automatically on 429/quota errors.
    """
    # ── Always set up Groq fallback if key available ───────────────────
    groq_fallback = None
    if groq_key and len(groq_key) > 10:
        try:
            from groq import Groq
            groq_fallback = (Groq(api_key=groq_key), groq_model)
        except Exception:
            pass

    # ── Try Gemini (new SDK) ───────────────────────────────────────────
    if gemini_key and len(gemini_key) > 10:
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            client.models.generate_content(model=gemini_model, contents="Say OK")
            return ("gemini", client, gemini_model, groq_fallback)
        except ImportError:
            try:
                import google.generativeai as genai  # type: ignore
                import warnings; warnings.filterwarnings("ignore")
                genai.configure(api_key=gemini_key)
                mdl = genai.GenerativeModel(gemini_model)
                mdl.generate_content("Say OK", generation_config={"max_output_tokens": 5})
                return ("gemini_old", mdl, gemini_model, groq_fallback)
            except Exception:
                pass
        except Exception:
            pass  # quota or other error on smoke test — fall through

    # ── Use Groq directly ─────────────────────────────────────────────
    if groq_fallback:
        groq_client, gmodel = groq_fallback
        return ("groq", groq_client, gmodel, None)

    raise RuntimeError("No valid API keys. Add GEMINI_API_KEY or GROQ_API_KEY in Streamlit secrets.")


_QUOTA_SIGNALS = ("429", "quota", "ResourceExhausted", "RESOURCE_EXHAUSTED",
                  "rate_limit", "rate limit", "RateLimitError")


def ai_generate(client_tuple, prompt: str, max_tokens: int = 8000) -> str:
    kind     = client_tuple[0]
    client   = client_tuple[1]
    model    = client_tuple[2]
    fallback = client_tuple[3] if len(client_tuple) > 3 else None

    def _groq_generate():
        if not fallback:
            raise RuntimeError("Gemini quota exceeded and no Groq fallback key configured.")
        groq_client, groq_model = fallback
        resp = groq_client.chat.completions.create(
            model=groq_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content

    def _is_quota_error(e):
        msg = str(e)
        return any(s in msg for s in _QUOTA_SIGNALS)

    if kind == "gemini":
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return resp.text
        except Exception as e:
            if _is_quota_error(e):
                return _groq_generate()
            raise
    elif kind == "gemini_old":
        try:
            resp = client.generate_content(prompt)
            return resp.text
        except Exception as e:
            if _is_quota_error(e):
                return _groq_generate()
            raise
    else:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content


# ─── Step 1: Article ─────────────────────────────────────────────────

def generate_article(ai, topic: str, niche: str, author: str) -> dict:
    prompt = f"""You are a senior {niche} engineer writing a detailed technical tutorial.

TOPIC: {topic}

Rules:
1. Start with a strong hook — a real problem engineers face
2. Proper Markdown: one H1, multiple H2 / H3
3. At least 2 working code blocks with comments
4. Include "Common Mistakes to Avoid" section
5. Include "Key Takeaways" at the end
6. Length: 1800–2500 words
7. Tone: conversational but technically precise
8. NO "In today's world" or "In this article we will"
9. Naturally mention relevant AI tools (ChatGPT, Claude, Cursor, GitHub Copilot, etc.)

Return ONLY valid JSON, no markdown fences:
{{
  "title": "SEO-optimized title (55-60 chars)",
  "meta_description": "Compelling meta (150-155 chars)",
  "focus_keyword": "primary keyword phrase",
  "slug": "url-friendly-slug",
  "tags": ["tag1","tag2","tag3","tag4","tag5"],
  "read_time_minutes": 8,
  "content": "FULL ARTICLE IN MARKDOWN",
  "excerpt": "2-3 sentence teaser"
}}"""

    raw = clean_json(ai_generate(ai, prompt))
    return safe_parse_article_json(raw, fallback_topic=topic)


# ─── Step 2: Affiliate links ─────────────────────────────────────────

def insert_affiliate_links(article_data: dict, affiliate_map: dict) -> dict:
    content = article_data.get("content", "")
    inserted = 0
    for tool_name, url in affiliate_map.items():
        if not url or not tool_name:
            continue
        pattern = r'(?<!\[)(?<!\()' + re.escape(tool_name) + r'(?!\])'
        if re.search(pattern, content):
            replacement = f"[{tool_name}]({url})"
            content, n = re.subn(pattern, replacement, content, count=1)
            if n > 0:
                inserted += 1
    article_data["content"] = content
    return article_data, inserted


# ─── Step 3: Diagram ─────────────────────────────────────────────────

def generate_diagram(ai, topic: str, article_content: str) -> str:
    prompt = f"""Based on this article about "{topic}", create ONE Mermaid.js diagram.

Choose: flowchart TD, sequenceDiagram, or graph LR — whichever fits best.
Rules: max 12 nodes, short labels (3-5 words), valid Mermaid syntax.

Return ONLY raw Mermaid code, no fences.

Article excerpt: {article_content[:600]}"""

    raw = clean_json(ai_generate(ai, prompt, max_tokens=500))
    return raw.strip()


# ─── Step 4: Image URL ───────────────────────────────────────────────

def generate_image_url(topic: str) -> str:
    from urllib.parse import quote
    # Strip special chars that break URL validation on Dev.to / Hashnode
    clean_topic = re.sub(r'[^\w\s,]', '', topic)[:80]
    prompt = (
        f"professional tech blog header, {clean_topic}, "
        "dark background glowing circuits blue cyan accent modern minimal 16:9 no text"
    )
    encoded = quote(prompt, safe='')
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&nologo=true"


# ─── Step 5: SEO ─────────────────────────────────────────────────────

def generate_seo(ai, article_data: dict, topic: str) -> dict:
    prompt = f"""Generate SEO metadata for this article.

Title: {article_data.get('title','')}
Focus keyword: {article_data.get('focus_keyword', topic)}
Tags: {article_data.get('tags',[])}

Return ONLY valid JSON:
{{
  "seo_title": "optimised title (max 60 chars)",
  "meta_description": "description (max 155 chars)",
  "og_title": "OG title",
  "schema_keywords": ["kw1","kw2","kw3","kw4","kw5"],
  "internal_link_suggestions": ["next article idea 1","idea 2","idea 3"],
  "seo_score_estimate": 84
}}"""

    raw = clean_json(ai_generate(ai, prompt, max_tokens=600))
    try:
        return json.loads(raw)
    except:
        return {
            "seo_title": article_data.get("title", ""),
            "meta_description": article_data.get("meta_description", ""),
            "og_title": article_data.get("title", ""),
            "schema_keywords": article_data.get("tags", []),
            "internal_link_suggestions": [],
            "seo_score_estimate": 75
        }


# ─── Step 6: Social posts ────────────────────────────────────────────

def generate_social_posts(ai, article_data: dict, topic: str) -> dict:
    prompt = f"""Write social media posts for this article.

Title: {article_data.get('title','')}
Excerpt: {article_data.get('excerpt','')}
Tags: {article_data.get('tags',[])}

Return ONLY valid JSON:
{{
  "linkedin_post": "Professional 150-200 word post, hook, question, hashtags",
  "twitter_thread": ["Tweet1 (280 chars)","Tweet2","Tweet3","Tweet4","Tweet5 CTA"],
  "dev_to_tags": ["tag1","tag2","tag3","tag4"],
  "hashnode_tags": ["tag1","tag2","tag3"]
}}"""

    raw = clean_json(ai_generate(ai, prompt, max_tokens=1200))
    try:
        return json.loads(raw)
    except:
        return {"linkedin_post": "", "twitter_thread": [], "dev_to_tags": [], "hashnode_tags": []}


# ─── Step 7: Video script ────────────────────────────────────────────

def generate_video_script(ai, article_data: dict, topic: str, niche: str) -> dict:
    prompt = f"""Write a 60-second YouTube/Instagram Shorts script.

Topic: {topic}
Title: {article_data.get('title','')}
Key insight: {article_data.get('excerpt','')}

STRUCTURE (must follow exactly):
- 0-3s:   ONE shocking/counter-intuitive statement
- 3-15s:  Explain the PROBLEM clearly
- 15-45s: THE ANSWER in 3 clear steps
- 45-55s: ONE quick win they get immediately
- 55-60s: "Full guide in bio. Follow for daily {niche} tips."

Style: Short sentences (max 10 words). No filler words.

Return ONLY valid JSON:
{{
  "hook_line": "single most powerful opening line",
  "script_lines": ["Line 1 (0-3s)","Line 2","...","Last line (CTA)"],
  "full_script": "full script as one paragraph",
  "duration_seconds": 58,
  "on_screen_text": ["Overlay 1","Overlay 2","Overlay 3"],
  "thumbnail_text": "Bold thumbnail text (max 6 words)"
}}"""

    raw = clean_json(ai_generate(ai, prompt, max_tokens=1000))
    try:
        return json.loads(raw)
    except:
        return {
            "hook_line": f"Most engineers don't know this about {topic}",
            "script_lines": [f"Let's talk about {topic}.", "Here's what matters."],
            "full_script": f"A guide to {topic}.",
            "duration_seconds": 55,
            "on_screen_text": [topic, "Key Steps", "Follow for more"],
            "thumbnail_text": f"{topic} Guide"
        }


# ─── Step 8: Voice (Edge-TTS) ────────────────────────────────────────

def generate_voice(full_script: str, output_path: str) -> bool:
    """Generate MP3 narration. Returns True on success."""
    try:
        import edge_tts, asyncio

        async def _make():
            c = edge_tts.Communicate(full_script, voice="en-US-GuyNeural", rate="+10%")
            await c.save(output_path)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                loop.run_until_complete(_make())
            else:
                asyncio.run(_make())
        except RuntimeError:
            asyncio.run(_make())

        return True
    except Exception:
        return False


# ─── Step 9: Assemble video ──────────────────────────────────────────

def assemble_video(script_data: dict, audio_path: str, video_output_path: str,
                   author_name: str = "AI Insights", music_path: str = "") -> bool:
    """Assemble a 9:16 vertical video. Returns True on success."""
    try:
        from moviepy.editor import (
            ColorClip, TextClip, CompositeVideoClip,
            AudioFileClip, CompositeAudioClip
        )
    except ImportError:
        return False

    try:
        lines    = script_data.get("script_lines", [])
        duration = script_data.get("duration_seconds", 55)
        W, H     = 1080, 1920

        bg         = ColorClip(size=(W, H), color=(14, 15, 19), duration=duration)
        voice      = AudioFileClip(audio_path)
        actual_dur = min(voice.duration, duration)
        bg         = bg.set_duration(actual_dur)

        clips         = [bg]
        time_per_line = actual_dur / max(len(lines), 1)

        for i, line in enumerate(lines):
            fs    = 76 if i == 0 else 54
            color = "#4F9CF9" if i == 0 else "white"
            try:
                txt = (TextClip(line, fontsize=fs, color=color,
                                font="DejaVu-Sans-Bold", method="caption",
                                size=(W - 120, None), align="center")
                       .set_start(i * time_per_line).set_duration(time_per_line)
                       .set_position(("center", H // 2 - 100)).crossfadein(0.25))
                clips.append(txt)
            except Exception:
                pass

        try:
            wm = (TextClip(f"@{author_name}", fontsize=36, color="#888888")
                  .set_duration(actual_dur).set_position(("center", H - 140)))
            clips.append(wm)
        except Exception:
            pass

        audio = voice
        if music_path and os.path.exists(music_path):
            try:
                music = AudioFileClip(music_path).volumex(0.08).set_duration(actual_dur)
                audio = CompositeAudioClip([voice, music])
            except Exception:
                pass

        CompositeVideoClip(clips).set_audio(audio).write_videofile(
            video_output_path, fps=30, codec="libx264",
            audio_codec="aac", logger=None, threads=4
        )
        return True
    except Exception:
        return False


# ─── Publishing ───────────────────────────────────────────────────────

def _sanitize_devto_tags(tags: list) -> list:
    """Dev.to tags: lowercase, alphanumeric + hyphens only, max 20 chars, max 4 tags."""
    clean = []
    for t in tags:
        t = str(t).lower().strip()
        t = re.sub(r'[^a-z0-9\-]', '', t.replace(' ', ''))
        t = t[:20]
        if t and t not in clean:
            clean.append(t)
        if len(clean) == 4:
            break
    return clean


def publish_devto(article: dict, social: dict, seo: dict, image_url: str, api_key: str) -> str:
    import requests
    raw_tags  = social.get("dev_to_tags", article.get("tags", []))
    safe_tags = _sanitize_devto_tags(raw_tags)
    title     = article.get("title", "")[:128]
    desc      = seo.get("meta_description", "")[:160]

    # Only include main_image if URL looks safe (no unencoded spaces/special chars)
    safe_image = image_url if image_url and image_url.startswith("http") and " " not in image_url else None

    article_body = {"article": {
        "title":         title,
        "body_markdown": article.get("content", ""),
        "published":     True,
        "tags":          safe_tags,
        "description":   desc,
    }}
    if safe_image:
        article_body["article"]["main_image"] = safe_image

    r = requests.post("https://dev.to/api/articles",
                      json=article_body, headers={"api-key": api_key}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Dev.to {r.status_code}: {r.text[:300]}")
    return f"https://dev.to{r.json().get('path','')}"


def publish_medium(article: dict, seo: dict, image_url: str, token: str, user_id: str = "") -> tuple:
    """Returns (url, user_id). Fetches user_id if not provided."""
    import requests
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if not user_id:
        r = requests.get("https://api.medium.com/v1/me", headers=headers, timeout=15)
        r.raise_for_status()
        user_id = r.json()["data"]["id"]

    payload = {
        "title":         article.get("title", ""),
        "contentFormat": "markdown",
        "content":       f"![Header]({image_url})\n\n{article.get('content','')}",
        "tags":          article.get("tags", [])[:5],
        "publishStatus": "public",
        "notifyFollowers": True
    }
    r = requests.post(f"https://api.medium.com/v1/users/{user_id}/posts",
                      json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json().get("data", {}).get("url", ""), user_id


def publish_hashnode(article: dict, social: dict, seo: dict, image_url: str,
                     api_key: str, pub_id: str) -> str:
    import requests
    mutation = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) {
        post { url id title }
      }
    }"""

    raw_tags = social.get("hashnode_tags", article.get("tags", []))[:5]
    hn_tags  = [{"name": str(t)[:50], "slug": re.sub(r'[^a-z0-9\-]', '',
                  str(t).lower().replace(" ", "-"))[:50]}
                for t in raw_tags if t]

    variables = {"input": {
        "title":           article.get("title", "")[:250],
        "contentMarkdown": article.get("content", ""),
        "publicationId":   pub_id,
        "tags":            hn_tags,
        # coverImageOptions and metaTags omitted — some Hashnode accounts
        # reject these fields silently; add back once basic publish works
    }}

    # Validate API key first with a lightweight query
    test_q = {"query": "{ __typename }"}
    for auth_fmt in [api_key, f"Bearer {api_key}"]:
        tr = requests.post("https://gql.hashnode.com",
                           json=test_q,
                           headers={"Authorization": auth_fmt,
                                    "Content-Type": "application/json"},
                           timeout=15, allow_redirects=False)
        if tr.ok and tr.text.strip().startswith("{"):
            working_auth = auth_fmt
            break
    else:
        raise RuntimeError(
            "Hashnode API key rejected — the key is invalid or expired.\n"
            "Fix: Go to hashnode.com → your profile → Account Settings → "
            "Developer → delete old token → Generate new token → "
            "update HASHNODE_API_KEY in Streamlit secrets."
        )

    headers = {"Authorization": working_auth, "Content-Type": "application/json"}
    r = requests.post("https://gql.hashnode.com",
                      json={"query": mutation, "variables": variables},
                      headers=headers, timeout=30, allow_redirects=False)

    if not r.ok:
        raise RuntimeError(
            f"Hashnode HTTP {r.status_code} | "
            f"body({len(r.content)}B): {r.text[:300] or '(empty)'}"
        )

    try:
        data = r.json()
    except Exception:
        raise RuntimeError(
            f"Hashnode returned non-JSON (HTTP {r.status_code}) | "
            f"{len(r.content)} bytes | raw: {repr(r.content[:120])}"
        )

    if "errors" in data:
        msgs = "; ".join(e.get("message", str(e)) for e in data["errors"])
        raise RuntimeError(f"Hashnode GraphQL error: {msgs}")

    return data.get("data", {}).get("publishPost", {}).get("post", {}).get("url", "")


def publish_to_github(article: dict, seo: dict, image_url: str,
                      github_token: str, repo: str, blog_path: str,
                      author_name: str = "AI Insights") -> str:
    """
    Commits the article markdown directly to GitHub via REST API.
    No git needed locally. Returns the raw GitHub URL of the file.
    """
    import requests, base64

    slug    = article.get("slug", "post")
    content = article.get("content", "")
    content = re.sub(r'^!\[.*?\]\(.*?\)\s*\n', '', content.strip())
    content = re.sub(r'\n---\n\*Published.*$', '', content, flags=re.DOTALL)

    md = f"""---
title: "{article.get('title','').replace('"', "'")}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
author: "{author_name}"
excerpt: "{article.get('excerpt','').replace('"', "'")}"
tags: {json.dumps(article.get('tags', []))}
featured: true
cover: "{image_url}"
---

{content.strip()}
"""

    file_path = f"{blog_path.rstrip('/')}/{slug}.md"
    url       = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers   = {
        "Authorization": f"token {github_token}",
        "Accept":        "application/vnd.github.v3+json"
    }

    # Check if file already exists (need SHA to update)
    existing = requests.get(url, headers=headers)
    body = {
        "message": f"Add blog post: {article.get('title', slug)}",
        "content":  base64.b64encode(md.encode("utf-8")).decode(),
        "branch":   "main"
    }
    if existing.status_code == 200:
        body["sha"] = existing.json().get("sha", "")

    r = requests.put(url, json=body, headers=headers, timeout=30)
    r.raise_for_status()
    return f"https://github.com/{repo}/blob/main/{file_path}"


# ─── Helpers ─────────────────────────────────────────────────────────

def build_article_md(article: dict, image_url: str, author_name: str) -> str:
    return f"""---
title: "{article.get('title','').replace('"', "'")}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
author: "{author_name}"
excerpt: "{article.get('excerpt','').replace('"', "'")}"
tags: {json.dumps(article.get('tags', []))}
featured: true
cover: "{image_url}"
---

{article.get('content','').strip()}
"""


def build_diagram_html(article: dict, diagram_code: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{article.get('title','')}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>body{{background:#0e0f13;display:flex;justify-content:center;
align-items:center;min-height:100vh;margin:0;}}
.mermaid{{background:#141720;padding:40px;border-radius:16px;
max-width:900px;width:90%;}}</style>
</head><body>
<div class="mermaid">{diagram_code}</div>
<script>mermaid.initialize({{startOnLoad:true,theme:'dark'}});</script>
</body></html>"""
