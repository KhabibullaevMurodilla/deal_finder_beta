"""
Anywhere Explore - Destination Article Generator
--------------------------------------------------
Turns real, recurring deals into short, curiosity-driving destination
articles - grounded in genuine appeal, not invented quotes or generic
listicle filler.

THE LOGIC (deliberately delayed, not instant):
- The FIRST time a destination shows up as a genuine deal, it's just
  recorded as "seen" - no article yet. The site shows the plain deal card.
- The NEXT time that same destination reappears as a genuine deal (a
  later run, meaning it's a real recurring opportunity, not a one-off),
  THAT's when its article actually gets written and published.
- From then on, the site can show a "Browse <Destination>" link next to
  the booking button for that destination's deals.

This means only destinations that genuinely keep showing up as real deals
earn dedicated content - a natural way to prioritize writing effort.

VOICE:
Short, unresolved on purpose - stops at a vivid, curious point rather than
wrapping up neatly, meant to create an itch to go find out more. Written
like someone who's read a lot of travel forums and trip reports and is
synthesizing what genuinely seems to make people fall for a place - NOT
inventing fake quotes, fake forum posts, or claiming specific sources.
Respectful of every place, always - no place framed as lesser or exotic
in a reductive way.

SETUP NEEDED:
- Same GEMINI_API_KEY environment variable as the concierge function
- Run this AFTER deal_finder.py, since it depends on todays_deals.json
"""

import json
import os
import re
import time
from datetime import datetime, timezone

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEALS_FILE = "todays_deals.json"
BLOG_DIR = "blog"
TRACKING_FILE = "destinations_tracking.json"
MAX_NEW_ARTICLES_PER_RUN = 3
SITE_NAME = "Anywhere"
SITE_URL = "https://anywhere-deals.com"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def extract_destination(route_label: str) -> str:
    """'Tashkent -> Dubai' -> 'Dubai'"""
    return route_label.split("->")[-1].strip()


def load_today_destinations():
    """Returns the set of destination CITY NAMES appearing in today's
    genuine, near-term deals (both tracked and special-offer sources)."""
    if not os.path.exists(DEALS_FILE):
        print(f"!! {DEALS_FILE} not found - run deal_finder.py first.")
        return set()

    with open(DEALS_FILE) as f:
        data = json.load(f)

    destinations = set()
    for d in data.get("tracked_deals", []):
        if d.get("is_deal"):
            destinations.add(extract_destination(d["route_label"]))
    for d in data.get("special_offers", []):
        destinations.add(extract_destination(d["route_label"]))
    return destinations


def load_tracking():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE) as f:
            return json.load(f)
    return {}


def save_tracking(tracking):
    with open(TRACKING_FILE, "w") as f:
        json.dump(tracking, f, indent=2)


def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    if not text:
        raise ValueError("Empty response from Gemini")
    return text


def generate_article(destination: str):
    prompt = f"""Write a SHORT piece of travel writing about {destination} for
"{SITE_NAME}", a flexible-destination flight deals site.

VOICE: like someone who has spent time reading travel forums, trip reports,
and other travelers' stories about {destination}, and is now sharing what
genuinely seems to make people fall for the place - the small admired
details, the things people mention wanting to go back for. Do NOT invent
or quote specific people, forum posts, or reviews - synthesize genuine,
well-known appeal in your own words, as an observation, not a citation.

LENGTH AND SHAPE: 100-150 words. This is deliberately NOT a complete,
wrapped-up story - stop right at a vivid, curious, specific moment or
detail, mid-thought if it feels natural, so the reader is left wanting to
know more rather than feeling satisfied. Do not summarize or conclude.

TONE: respectful and genuinely admiring - never reductive, never framing
the place or its people as exotic, backward, or a punchline. Never compare
it unfavorably to anywhere else.

Respond with ONLY valid JSON, no markdown fences, no other text, in this
exact shape:
{{"title": "a short, curiosity-driving headline about {destination} - not clickbait, just genuinely intriguing", "body_html": "the article as an HTML string using <p> tags only"}}
"""
    raw = call_gemini(prompt)
    raw = raw.replace("```json", "").replace("```", "").strip()
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1:
        raw = raw[first_brace:last_brace + 1]
    parsed = json.loads(raw)
    return parsed["title"], parsed["body_html"]


POST_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - {site_name}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical_url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical_url}">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root{{ --night:#0E1420; --amber:#FFB000; --sky:#3DB7E4; --text:#EDEFF3; --muted:#7C8798; --line:#202838;
    --display:'Archivo',sans-serif; --body:'Inter',sans-serif; --flap:'IBM Plex Mono',monospace; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--night); color:var(--text); font-family:var(--body); line-height:1.7; }}
  .wrap {{ max-width:680px; margin:0 auto; padding:0 24px; }}
  nav {{ border-bottom:1px solid var(--line); padding:20px 0; }}
  nav a {{ color:var(--sky); text-decoration:none; font-family:var(--flap); font-size:13px; margin-right:20px; }}
  article {{ padding:56px 0; }}
  .eyebrow {{ font-family:var(--flap); font-size:12px; color:var(--sky); letter-spacing:.06em; margin-bottom:14px; }}
  h1 {{ font-family:var(--display); font-weight:800; font-size:clamp(26px,4vw,38px); line-height:1.15; margin-bottom:24px; }}
  p {{ margin-bottom:18px; color:#D7DEE2; font-size:17px; }}
  .cta {{ margin-top:32px; padding:22px; border:1px solid var(--line); border-radius:10px; background:#0B111C; }}
  .cta a {{ display:inline-block; margin-top:10px; color:var(--sky); font-family:var(--flap); font-size:13px; text-decoration:none; }}
  footer {{ padding:28px 0; font-size:12px; color:var(--muted); border-top:1px solid var(--line); }}
</style>
</head>
<body>
<nav><div class="wrap"><a href="{site_url}/">&larr; back to {site_name}</a><a href="{site_url}/blog/">Explore more</a></div></nav>
<article class="wrap">
  <div class="eyebrow">EXPLORE</div>
  <h1>{title}</h1>
  {body_html}
  <div class="cta">
    <div>Curious what a flight there actually costs right now?</div>
    <a href="{site_url}/#search">Check live prices to {destination} &rarr;</a>
  </div>
</article>
<footer><div class="wrap">{site_name} - flexible-destination flight deals.</div></footer>
</body>
</html>
"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Explore - {site_name}</title>
<meta name="description" content="Short, honest reads on destinations worth a closer look - written from what genuinely seems to make people fall for a place.">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root{{ --night:#0E1420; --amber:#FFB000; --sky:#3DB7E4; --text:#EDEFF3; --muted:#7C8798; --line:#202838;
    --display:'Archivo',sans-serif; --body:'Inter',sans-serif; --flap:'IBM Plex Mono',monospace; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--night); color:var(--text); font-family:var(--body); }}
  .wrap {{ max-width:780px; margin:0 auto; padding:56px 24px; }}
  h1 {{ font-family:var(--display); font-weight:800; font-size:32px; margin-bottom:10px; }}
  .sub {{ color:var(--muted); margin-bottom:34px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
  .post {{ border:1px solid var(--line); border-radius:8px; padding:20px; background:#0B111C; }}
  .post a {{ color:var(--text); text-decoration:none; font-family:var(--display); font-weight:700; font-size:17px; }}
  .post .meta {{ font-family:var(--flap); font-size:11px; color:var(--muted); margin-top:8px; }}
  nav a {{ color:var(--sky); text-decoration:none; font-family:var(--flap); font-size:13px; }}
</style>
</head>
<body>
<div class="wrap">
  <nav style="margin-bottom:30px;"><a href="{site_url}/">&larr; back to {site_name}</a></nav>
  <h1>Explore</h1>
  <div class="sub">Short reads on places worth a closer look.</div>
  <div class="grid">
  {posts_html}
  </div>
</div>
</body>
</html>
"""


def build_post_html(destination, title, body_html, slug):
    description = f"A short read on {destination} - what makes it worth a closer look."
    return POST_TEMPLATE.format(
        title=title, site_name=SITE_NAME, site_url=SITE_URL, description=description,
        canonical_url=f"{SITE_URL}/blog/{slug}.html", body_html=body_html, destination=destination,
    )


def rebuild_index(tracking):
    published = [v for v in tracking.values() if v.get("article_generated")]
    published.sort(key=lambda p: p.get("published_at", ""), reverse=True)
    posts_html = ""
    for p in published:
        posts_html += f"""<div class="post">
      <a href="{p['slug']}.html">{p['title']}</a>
      <div class="meta">{p['destination']}</div>
    </div>\n"""
    html = INDEX_TEMPLATE.format(site_name=SITE_NAME, site_url=SITE_URL, posts_html=posts_html)
    with open(os.path.join(BLOG_DIR, "index.html"), "w") as f:
        f.write(html)


def main():
    if not GEMINI_API_KEY:
        print("!! GEMINI_API_KEY environment variable is not set.")
        return

    os.makedirs(BLOG_DIR, exist_ok=True)
    today_destinations = load_today_destinations()
    if not today_destinations:
        print("No genuine near-term deals today - nothing to track or write about.")
        return

    tracking = load_tracking()
    today_str = datetime.now(timezone.utc).date().isoformat()
    new_articles_written = 0

    for destination in sorted(today_destinations):
        entry = tracking.get(destination)

        if entry is None:
            tracking[destination] = {
                "destination": destination,
                "first_seen": today_str,
                "article_generated": False,
            }
            print(f"First sighting: {destination} (recorded, no article yet)")
            continue

        if entry.get("article_generated"):
            print(f"{destination}: already has an article, skipping")
            continue

        if entry["first_seen"] == today_str:
            continue

        if new_articles_written >= MAX_NEW_ARTICLES_PER_RUN:
            continue

        print(f"Recurring deal destination: {destination} -> writing article now")
        try:
            title, body_html = generate_article(destination)
        except Exception as e:
            print(f"  [!] Failed to generate article for {destination}: {e}")
            continue

        slug = slugify(f"{destination}-{today_str}")
        html = build_post_html(destination, title, body_html, slug)
        with open(os.path.join(BLOG_DIR, f"{slug}.html"), "w") as f:
            f.write(html)

        tracking[destination].update({
            "article_generated": True,
            "slug": slug,
            "title": title,
            "published_at": datetime.now(timezone.utc).isoformat(),
        })
        new_articles_written += 1
        time.sleep(2)

    save_tracking(tracking)
    rebuild_index(tracking)
    print(f"\nDone. Wrote {new_articles_written} new article(s) this run.")


if __name__ == "__main__":
    main()
