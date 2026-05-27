"""
AI Blog Agent — Web App
Runs the full pipeline in the browser. No local installs needed.
Deploy free at: share.streamlit.io
"""

import os
import tempfile
import streamlit as st
import agent_core as core

# ─── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Blog Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Theme / custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #0e0f13; }
  [data-testid="stSidebar"] { background: #141720; border-right: 1px solid #1f2937; }
  h1, h2, h3 { font-family: 'Segoe UI', sans-serif; }
  .metric-box {
    background: #141720; border: 1px solid #1f2937;
    border-radius: 12px; padding: 16px 20px; text-align: center;
  }
  .metric-box .num { font-size: 32px; font-weight: 800; color: #4f9cf9; }
  .metric-box .lbl { font-size: 12px; color: #888; margin-top: 4px; }
  .success-url {
    background: rgba(60,220,120,0.08); border: 1px solid rgba(60,220,120,0.3);
    border-radius: 8px; padding: 10px 14px; margin: 4px 0;
    color: #3cdc78; font-size: 13px;
  }
  .step-done  { color: #3cdc78; }
  .step-run   { color: #4f9cf9; }
  .step-wait  { color: #555; }
</style>
""", unsafe_allow_html=True)


# ─── Secrets helper ───────────────────────────────────────────────────
def cfg(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)


# ─── Sidebar — configuration ──────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤖 AI Blog Agent")
    st.markdown("---")

    # Key status
    gemini_key = cfg("GEMINI_API_KEY")
    groq_key   = cfg("GROQ_API_KEY")
    devto_key  = cfg("DEVTO_API_KEY")
    medium_tok = cfg("MEDIUM_INTEGRATION_TOKEN")
    hn_key     = cfg("HASHNODE_API_KEY")
    hn_pub     = cfg("HASHNODE_PUBLICATION_ID")
    gh_token   = cfg("GITHUB_TOKEN")
    gh_repo    = cfg("GITHUB_REPO")
    gh_path    = cfg("GITHUB_BLOG_PATH", "ai-website/content/blog")
    niche      = cfg("BLOG_NICHE", "DevOps, Kubernetes, AI Automation")
    author     = cfg("AUTHOR_NAME", "AI Insights")

    ai_ok   = bool((gemini_key and len(gemini_key) > 10) or (groq_key and len(groq_key) > 10))
    ai_name = "Gemini 2.5 Flash" if (gemini_key and len(gemini_key) > 10) else "Groq Llama"

    def badge(ok, label):
        icon = "🟢" if ok else "🔴"
        return f"{icon} {label}"

    st.markdown("**API Status**")
    st.markdown(badge(ai_ok,              f"AI: {ai_name}"))
    st.markdown(badge(bool(devto_key),    "Dev.to"))
    st.markdown(badge(bool(medium_tok),   "Medium"))
    st.markdown(badge(bool(hn_key and hn_pub), "Hashnode"))
    st.markdown(badge(bool(gh_token and gh_repo), "GitHub (Website)"))

    if not ai_ok:
        st.error("⚠️ Add GEMINI_API_KEY or GROQ_API_KEY in Streamlit secrets to get started.")

    st.markdown("---")
    st.markdown(f"**Niche:** {niche}")
    st.markdown(f"**Author:** {author}")
    st.markdown("---")
    st.caption("📖 [How to add secrets →](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)")


# ─── Main header ──────────────────────────────────────────────────────
st.title("🤖 AI Blog Agent")
st.markdown("Type a topic → get a full article, video script, social posts, and publish everywhere. **One click.**")
st.markdown("---")

# ─── Tabs ─────────────────────────────────────────────────────────────
tab_gen, tab_results, tab_publish, tab_history = st.tabs([
    "🚀 Generate", "📄 Results", "📤 Publish", "📊 History"
])


# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — GENERATE
# ═══════════════════════════════════════════════════════════════════════
with tab_gen:
    col1, col2 = st.columns([2, 1])

    with col1:
        topic = st.text_input(
            "🎯 Article topic",
            placeholder="e.g. How Claude AI transforms DevOps automation in 2026",
            help="Be specific. 'Kubernetes HPA scaling' beats 'Kubernetes'."
        )
        st.caption("💡 **Best topics:** How-to guides, tool comparisons, automation playbooks, common mistakes, deep dives")

    with col2:
        st.markdown("**Options**")
        do_video   = st.toggle("🎬 Generate video short", value=False,
                                help="Creates MP4 for YouTube Shorts + Reels. Takes ~2 extra minutes.")
        do_website = st.toggle("🌐 Post to website", value=bool(gh_token),
                                help="Commits article directly to your GitHub → Vercel rebuilds in 60s.")
        do_devto   = st.toggle("📝 Publish to Dev.to",   value=bool(devto_key))
        do_medium  = st.toggle("📰 Publish to Medium",   value=bool(medium_tok))
        do_hashnode= st.toggle("🔷 Publish to Hashnode", value=bool(hn_key))

    st.markdown("")
    run_btn = st.button("🚀 Generate Everything", type="primary",
                         disabled=not ai_ok or not topic.strip(),
                         use_container_width=True)

    if not topic.strip() and run_btn:
        st.warning("Please enter a topic first.")

    # ── Pipeline ────────────────────────────────────────────────────────
    if run_btn and topic.strip() and ai_ok:
        st.markdown("---")
        progress_area = st.empty()
        status_log    = []

        def log(msg, done=False, error=False):
            icon = "✅" if done else ("❌" if error else "⏳")
            status_log.append(f"{icon} {msg}")
            progress_area.markdown("\n\n".join(status_log))

        try:
            # ── AI client ──
            log("Connecting to AI...")
            affiliate_map = {
                "ChatGPT":        cfg("AFFILIATE_CHATGPT",  "https://chat.openai.com"),
                "Claude":         cfg("AFFILIATE_CLAUDE",   "https://claude.ai"),
                "Cursor":         cfg("AFFILIATE_CURSOR",   "https://cursor.com"),
                "Midjourney":     cfg("AFFILIATE_MIDJOURNEY","https://midjourney.com"),
                "ElevenLabs":     cfg("AFFILIATE_ELEVENLABS","https://elevenlabs.io"),
                "Perplexity":     cfg("AFFILIATE_PERPLEXITY","https://perplexity.ai"),
                "Notion AI":      cfg("AFFILIATE_NOTION",   "https://notion.so"),
                "Zapier":         cfg("AFFILIATE_ZAPIER",   "https://zapier.com"),
                "n8n":            cfg("AFFILIATE_N8N",      "https://n8n.io"),
                "GitHub Copilot": cfg("AFFILIATE_COPILOT",  "https://github.com/features/copilot"),
                "Runway":         cfg("AFFILIATE_RUNWAY",   "https://runwayml.com"),
            }
            ai = core.get_ai_client(gemini_key, groq_key)
            log(f"Connected to {ai[2]}", done=True)

            # ── Article ──
            log("Writing article (30-60 seconds)...")
            article = core.generate_article(ai, topic, niche, author)
            log(f"Article written — {len(article.get('content','').split()):,} words · \"{article.get('title','')}\"", done=True)

            # ── Affiliate links ──
            log("Inserting affiliate links...")
            article, n_links = core.insert_affiliate_links(article, affiliate_map)
            log(f"Affiliate links inserted: {n_links} tools linked", done=True)

            # ── Diagram ──
            log("Generating architecture diagram...")
            diagram = core.generate_diagram(ai, topic, article.get("content",""))
            log("Diagram created", done=True)

            # ── Image ──
            log("Generating header image...")
            image_url = core.generate_image_url(topic)
            log("Header image ready (Pollinations.ai)", done=True)

            # ── SEO ──
            log("Optimising SEO...")
            seo = core.generate_seo(ai, article, topic)
            log(f"SEO done — estimated score: {seo.get('seo_score_estimate',75)}/100", done=True)

            # ── Social ──
            log("Writing social media posts...")
            social = core.generate_social_posts(ai, article, topic)
            log(f"Social posts ready — LinkedIn + {len(social.get('twitter_thread',[]))} tweets", done=True)

            # ── Video script ──
            log("Writing 60-second video script...")
            script = core.generate_video_script(ai, article, topic, niche)
            log(f"Video script ready — hook: \"{script.get('hook_line','')[:60]}...\"", done=True)

            # ── Voice + Video ──
            audio_bytes = None
            video_bytes = None

            if do_video:
                with tempfile.TemporaryDirectory() as tmp:
                    audio_path = os.path.join(tmp, "narration.mp3")
                    log("Generating AI voice narration...")
                    ok = core.generate_voice(script.get("full_script",""), audio_path)
                    if ok:
                        with open(audio_path, "rb") as f:
                            audio_bytes = f.read()
                        log("Voice narration ready (Edge-TTS)", done=True)

                        log("Assembling video (1-2 minutes)...")
                        video_path = os.path.join(tmp, "short_video.mp4")
                        ok_v = core.assemble_video(script, audio_path, video_path, author)
                        if ok_v:
                            with open(video_path, "rb") as f:
                                video_bytes = f.read()
                            log("Video assembled — ready for YouTube Shorts + Reels!", done=True)
                        else:
                            log("Video assembly failed (moviepy issue). Script + voice saved.", error=True)
                    else:
                        log("Voice generation failed. Script saved as text.", error=True)

            # ── Build file contents ──
            article_md   = core.build_article_md(article, image_url, author)
            diagram_html = core.build_diagram_html(article, diagram)
            twitter_text = "\n".join([f"Tweet {i+1}: {t}" for i,t in enumerate(social.get("twitter_thread",[]))])
            social_txt   = f"LINKEDIN:\n{social.get('linkedin_post','')}\n\nTWITTER THREAD:\n{twitter_text}\n"
            lines_txt    = "\n".join([f"[{i+1}] {l}" for i,l in enumerate(script.get("script_lines",[]))])
            script_txt   = f"HOOK: {script.get('hook_line','')}\n\nSCRIPT:\n{lines_txt}\n\nFULL:\n{script.get('full_script','')}"
            seo_txt      = (f"SEO TITLE: {seo.get('seo_title','')}\n"
                           f"META:      {seo.get('meta_description','')}\n"
                           f"SCORE:     {seo.get('seo_score_estimate',75)}/100\n"
                           f"KEYWORDS:  {', '.join(seo.get('schema_keywords',[]))}\n\n"
                           f"NEXT ARTICLES:\n" +
                           "\n".join([f"→ {s}" for s in seo.get("internal_link_suggestions",[])]))

            # ── Save to session ──
            st.session_state["result"] = {
                "topic":       topic,
                "article":     article,
                "diagram":     diagram,
                "image_url":   image_url,
                "seo":         seo,
                "social":      social,
                "script":      script,
                "audio_bytes": audio_bytes,
                "video_bytes": video_bytes,
                "article_md":  article_md,
                "diagram_html":diagram_html,
                "social_txt":  social_txt,
                "script_txt":  script_txt,
                "seo_txt":     seo_txt,
                "do_website":  do_website,
                "do_devto":    do_devto,
                "do_medium":   do_medium,
                "do_hashnode": do_hashnode,
            }

            log("🎉 **All done!** Switch to the Results tab to download files and publish.", done=True)
            st.success("✅ Generation complete! Go to the **Results** and **Publish** tabs.")
            st.balloons()

        except Exception as e:
            st.error(f"❌ Pipeline failed: {e}")
            st.exception(e)


# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — RESULTS
# ═══════════════════════════════════════════════════════════════════════
with tab_results:
    if "result" not in st.session_state:
        st.info("👆 Go to the **Generate** tab, enter a topic and click Generate. Results will appear here.")
    else:
        r       = st.session_state["result"]
        article = r["article"]
        seo     = r["seo"]
        script  = r["script"]
        social  = r["social"]
        slug    = article.get("slug", "post")

        # ── Metrics ──
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📝 Words",      f"{len(article.get('content','').split()):,}")
        c2.metric("🔍 SEO Score",  f"{seo.get('seo_score_estimate',75)}/100")
        c3.metric("⏱ Read time",   f"{article.get('read_time_minutes',8)} min")
        c4.metric("🐦 Tweets",     len(social.get('twitter_thread',[])))

        st.markdown(f"### 📰 {article.get('title','')}")
        st.caption(f"**Excerpt:** {article.get('excerpt','')}")

        # ── Cover image preview ──
        if r.get("image_url"):
            st.image(r["image_url"], caption="Header image (Pollinations.ai)", width="stretch")

        # ── Download buttons ──
        st.markdown("### 📥 Download all files")
        col_a, col_b, col_c, col_d = st.columns(4)

        col_a.download_button("📄 article.md", r["article_md"],
                               file_name=f"{slug}.md", mime="text/markdown",
                               use_container_width=True)
        col_b.download_button("🌐 diagram.html", r["diagram_html"],
                               file_name="diagram.html", mime="text/html",
                               use_container_width=True)
        col_c.download_button("📱 social_posts.txt", r["social_txt"],
                               file_name="social_posts.txt", mime="text/plain",
                               use_container_width=True)
        col_d.download_button("📋 seo.txt", r["seo_txt"],
                               file_name="seo.txt", mime="text/plain",
                               use_container_width=True)

        if r.get("audio_bytes"):
            st.markdown("**🎤 Voice narration**")
            st.audio(r["audio_bytes"], format="audio/mp3")
            st.download_button("⬇️ Download narration.mp3", r["audio_bytes"],
                                file_name="narration.mp3", mime="audio/mp3")

        if r.get("video_bytes"):
            st.markdown("**🎬 Video short (upload to YouTube Shorts + Reels)**")
            st.video(r["video_bytes"])
            st.download_button("⬇️ Download short_video.mp4", r["video_bytes"],
                                file_name="short_video.mp4", mime="video/mp4")

        # ── Content preview tabs ──
        pt1, pt2, pt3, pt4 = st.tabs(["Article", "Social Posts", "Video Script", "SEO"])

        with pt1:
            st.markdown(article.get("content",""))

        with pt2:
            st.markdown("**LinkedIn Post**")
            st.text_area("Copy and post →", social.get("linkedin_post",""), height=200, key="li")
            st.markdown("**Twitter / X Thread**")
            for i, t in enumerate(social.get("twitter_thread",[])):
                st.text_area(f"Tweet {i+1}", t, height=80, key=f"tw{i}")

        with pt3:
            st.markdown(f"**🪝 Hook line (say this first):**\n> {script.get('hook_line','')}")
            st.markdown("**Full script:**")
            for i, line in enumerate(script.get("script_lines",[])):
                st.markdown(f"`{i+1}.` {line}")
            st.markdown(f"**Thumbnail text:** `{script.get('thumbnail_text','')}`")

        with pt4:
            st.markdown(f"**SEO Title:** {seo.get('seo_title','')}")
            st.markdown(f"**Meta description:** {seo.get('meta_description','')}")
            st.markdown(f"**SEO score estimate:** {seo.get('seo_score_estimate',75)}/100")
            st.markdown("**Keywords:** " + ", ".join(seo.get("schema_keywords",[])))
            st.markdown("**Next article ideas:**")
            for s in seo.get("internal_link_suggestions",[]):
                st.markdown(f"- {s}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — PUBLISH
# ═══════════════════════════════════════════════════════════════════════
with tab_publish:
    if "result" not in st.session_state:
        st.info("👆 Generate an article first, then publish it here.")
    else:
        r       = st.session_state["result"]
        article = r["article"]
        seo     = r["seo"]
        social  = r["social"]
        img_url = r["image_url"]

        st.markdown("### 📤 Publish your article")
        st.caption("Click any button to publish. Results appear instantly.")

        col1, col2 = st.columns(2)

        # ── Website (GitHub) ──
        with col1:
            st.markdown("#### 🌐 Your Website (Next.js)")
            if gh_token and gh_repo:
                if st.button("Commit to GitHub → Vercel rebuilds", use_container_width=True):
                    with st.spinner("Committing to GitHub..."):
                        try:
                            url = core.publish_to_github(
                                article, seo, img_url,
                                gh_token, gh_repo, gh_path, author
                            )
                            st.markdown(f'<div class="success-url">✅ Live on GitHub → Vercel builds in ~60s<br>{url}</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"GitHub error: {e}")
            else:
                st.warning("Add GITHUB_TOKEN + GITHUB_REPO in Streamlit secrets to enable.")

        # ── Dev.to ──
        with col2:
            st.markdown("#### 📝 Dev.to")
            if devto_key:
                if st.button("Publish to Dev.to", use_container_width=True):
                    with st.spinner("Publishing to Dev.to..."):
                        try:
                            url = core.publish_devto(article, social, seo, img_url, devto_key)
                            st.markdown(f'<div class="success-url">✅ Published!<br><a href="{url}">{url}</a></div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Dev.to error: {e}")
            else:
                st.warning("Add DEVTO_API_KEY in Streamlit secrets to enable.")

        col3, col4 = st.columns(2)

        # ── Medium ──
        with col3:
            st.markdown("#### 📰 Medium")
            if medium_tok:
                if st.button("Publish to Medium", use_container_width=True):
                    with st.spinner("Publishing to Medium..."):
                        try:
                            user_id = cfg("MEDIUM_USER_ID", "")
                            url, uid = core.publish_medium(article, seo, img_url, medium_tok, user_id)
                            st.markdown(f'<div class="success-url">✅ Published!<br><a href="{url}">{url}</a></div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Medium error: {e}")
            else:
                st.warning("Add MEDIUM_INTEGRATION_TOKEN in Streamlit secrets to enable. Get it at medium.com/me/settings → Integration tokens.")

        # ── Hashnode ──
        with col4:
            st.markdown("#### 🔷 Hashnode")
            if hn_key and hn_pub:
                if st.button("Publish to Hashnode", use_container_width=True):
                    with st.spinner("Publishing to Hashnode..."):
                        try:
                            url = core.publish_hashnode(article, social, seo, img_url, hn_key, hn_pub)
                            st.markdown(f'<div class="success-url">✅ Published!<br><a href="{url}">{url}</a></div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Hashnode error: {e}")
            else:
                st.warning("Add HASHNODE_API_KEY + HASHNODE_PUBLICATION_ID in Streamlit secrets.")

        st.markdown("---")
        st.markdown("#### 📱 Social posts (manual — copy below)")
        st.text_area("LinkedIn", r["social_txt"].split("TWITTER")[0], height=150)
        st.text_area("Video script (for manual upload)", r["script_txt"], height=150)


# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — HISTORY
# ═══════════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("### 📊 Published Articles")
    st.info("History is stored in your Streamlit session. For a permanent log, use the CLI agent_v2.py which saves to dashboard.html on your computer.")

    if "history" not in st.session_state:
        st.session_state["history"] = []

    # Add current result to history if just generated
    if "result" in st.session_state:
        r = st.session_state["result"]
        exists = any(h.get("slug") == r["article"].get("slug") for h in st.session_state["history"])
        if not exists:
            st.session_state["history"].insert(0, {
                "date":  __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
                "title": r["article"].get("title",""),
                "slug":  r["article"].get("slug",""),
                "words": len(r["article"].get("content","").split()),
                "seo":   r["seo"].get("seo_score_estimate",75),
                "video": r.get("video_bytes") is not None,
                "topic": r.get("topic",""),
            })

    history = st.session_state["history"]
    if not history:
        st.info("No articles yet. Generate one and it will appear here.")
    else:
        c1,c2,c3 = st.columns(3)
        c1.metric("Total articles", len(history))
        c2.metric("With video", sum(1 for h in history if h.get("video")))
        c3.metric("Avg SEO score", f"{sum(h.get('seo',0) for h in history)//max(len(history),1)}/100")

        st.markdown("")
        for h in history:
            with st.expander(f"📄 {h['title']} — {h['date']}"):
                st.markdown(f"- **Topic:** {h.get('topic','')}")
                st.markdown(f"- **Words:** {h.get('words',0):,}")
                st.markdown(f"- **SEO:** {h.get('seo',0)}/100")
                st.markdown(f"- **Video:** {'✅ Yes' if h.get('video') else '—'}")
