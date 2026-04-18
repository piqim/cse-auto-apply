#!/usr/bin/env python3
"""
Handshake Internship Auto-Applicator v2
----------------------------------------
Scrapes Handshake for internship postings, scores each one against your
profile using Groq (LLaMA 3.3 70B), auto-fills free-text questions, attaches
your resume, and submits. Every outcome gets logged to a CSV.

Setup:
  1. pip install -r requirements.txt && playwright install chromium
  2. Get a free Groq key at https://console.groq.com
  3. Drop your resume in this folder, update RESUME_PATH below
  4. python bot.py — log in via SSO when the browser opens, then press ENTER
"""

import asyncio
import csv
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout


# ── CONFIG ────────────────────────────────────────────────────────────────────
# Everything you'd want to change is here. Don't touch anything below this.

# Free key at https://console.groq.com — or set via: export GROQ_API_KEY='gsk_...'
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_API_KEY_HERE")

RESUME_PATH = "resume.pdf"

# What to search on Handshake. Each keyword runs as its own search.
KEYWORDS = [
    "data science",
    "data engineering",
    "software engineering",
    "computer science",
    "fullstack developer",
    "developer",
    "machine learning",
    "data analyst",
    "backend engineer",
    "frontend engineer",
]

# Jobs scoring below this (out of 10) get skipped. Raise it to be picky,
# lower it if you want to cast a wider net.
MIN_RELEVANCE_SCORE = 6

MAX_APPLICATIONS   = 25     # hard stop — won't submit more than this per run
DELAY_BETWEEN_APPS = 4      # seconds between each application, don't be rude
TRACKER_FILE       = "applied_jobs.csv"
DRY_RUN            = False  # set True to scrape + score without submitting


# ── CANDIDATE PROFILE ─────────────────────────────────────────────────────────
# Plain-text summary of who you are. Groq reads this to score job fit and write
# cover letter answers. The more honest and detailed it is, the better the output.
# Replace this with your own profile if you're not me.

CANDIDATE_PROFILE = """
Name        : Mustaqim Bin Burhanuddin (goes by Piqim)
University  : UC San Diego — B.S. Mathematics-Computer Science (2024–2028)
Contact     : mbinburhanuddin@gmail.com | linkedin.com/in/piqim | piqim.com
Scholarship : Yayasan Khazanah Scholar — competitive national scholarship
              from Malaysia's sovereign wealth fund, awarded for academic
              excellence and leadership potential.
From        : Malaysia

== About ==
Mathematics-Computer Science student at UCSD with a strong interest in
software, data, and social impact. As a Yayasan Khazanah scholar, Piqim has
developed leadership, cross-functional collaboration, and communication skills
through managing real projects and teams. Eager to apply software development
and data analysis expertise to make impactful contributions.

== Technical Skills ==
Languages  : Python, Java, JavaScript/TypeScript, SQL (MySQL), R, HTML/CSS, PHP
Frameworks : React.js, Next.js, Node.js, Express.js, MERN Stack, Tailwind CSS,
             Streamlit, R Shiny, Scikit-learn, Pandas, NumPy
Data / ML  : EDA (uni/bi/multivariate), regression & predictive modeling, ANOVA,
             feature engineering, multicollinearity diagnostics, data cleaning,
             data visualization (Matplotlib, Seaborn, Plotly), web scraping
Tools      : Git/GitHub, Vercel, Render, Zapier, SDLC, Active Directory,
             Windows/macOS system imaging

== Work Experience ==
• IT Field Support Technician — UC San Diego ITS-RRSS (May 2025 – Present)
  Deployed/imaged 500+ Windows/macOS systems; resolved 500+ OS and enterprise
  software issues; reduced unresolved tickets significantly.
  Received training in Active Directory management and system administration.
  Learned to adapt technical communication to any audience — from engineers to
  professors with limited tech literacy — without being condescending.

• Data Engineering Intern — PrimeLogic AI (Dec 2025 – Jan 2026, Malaysia)
  Built end-to-end data pipelines (Python, Pandas, Scikit-learn), performed EDA,
  statistical analysis, feature engineering, and delivered ML-based client solutions.

== Projects ==
• SourceCheck (Apr 2026 – Present) | React, FastAPI, Python, Nia API, Groq/LLaMA 3
  Full-stack claim-level fact-verification tool: indexes research papers via
  semantic retrieval; analyzes each factual claim with confirmed / incorrect /
  hallucination verdicts. Built in 6 hours at his first-ever hackathon.
  Top-8 finish at the 2026 SDxUCSD Agent Hackathon.

• Malaysian Housing Price Predictor — MYHoPr2 (Jan–Feb 2026) | Python, Streamlit
  End-to-end ML pipeline on 4,000+ listings: data cleaning, uni/bi/multivariate
  EDA, correlation matrix, multicollinearity diagnostics, feature engineering,
  regression + tree-based modeling, interactive Streamlit dashboard
  (Matplotlib, Seaborn, Plotly).

• FeelingPrepper (Oct 2025 – Feb 2026) | MERN Stack, Vercel, Render
  Full-stack mobile mental health app using CBT methods (GRAPES, Cognitive
  Triangle). Secure auth, personalized activity tracking, calendar analytics.
  Deployed via Vercel + Render; targeting App Store and Play Store release.

• Calorie Burn Statistical Model (Jan 2026) | R, R Shiny
  Descriptive analytics + statistical inference on 973 gym users: distributional
  analysis, linear regression, ANOVA. Interactive R Shiny app with hypothesis
  testing, regression diagnostics, and result export.

• KERIS Scholarship Repository Website (Jan–Mar 2025) | MERN Stack
  Full-stack site with searchable mentor directory and scholarship database to
  improve scholarship access for Malaysian students.

• NOTICIAS News Website (Aug–Dec 2023) | MySQL, PHP, JavaScript, HTML/CSS
  Dynamic college journalism website with full backend CMS. Improved page load
  times by 40%; built-in Google Ad support for writer incentives.

• In The Shoes — Visual Novel Web Game (Dec 2023–Jun 2024) | React, HTML
  Core web game dev team member; built a visual novel to raise awareness about
  urban poverty.

== Volunteering & Leadership ==
• Project Lead — Engineers Without Borders @ UCSD (Jan 2026 – Present)
  Data-driven research on STEM models for K–12 students. Built ML-assisted
  web-scraping pipelines for scalable school outreach across San Diego County.

• Project Lead Developer — Triton Web Developers @ UCSD (Feb 2026 – Present)
  Main lead developer; oversees framework selection, UI/UX direction, full-stack
  architecture, and cross-club collaboration.

• Assistant Treasurer — Malaysian Student Association @ UCSD (Mar 2025 – Present)
  Financial planning, budgeting, and cost analysis for events; manages ~50-member
  Malaysian student community at UCSD.

• Co-Founder & Advisor — KERIS (Apr 2023 – Present)
  Co-founded a scholarship initiative for rural Malaysian students. Launched a
  mock interview program supporting 150+ students; contributed to a 71%
  scholarship attainment rate among participants.

• Mentor Developer — ACM @ UCSD (Oct–Dec 2025)
  Mentored students through ACM Hack School (full-stack bootcamp) covering
  JavaScript, React, Next.js, Express, Vercel, UI/UX, and API integration.

• Volunteer Instructor — KY Computing Society (Aug–Sep 2022)
  Taught HTML, CSS, JavaScript to 50+ participants; 90% course completion rate.

== Personality & Working Style ==
Piqim is, by his own proud admission, productively lazy — he would rather
spend three hours automating a task than spend one hour doing it manually.
He has a sharp instinct for finding innovative, elegant shortcuts to tedious
problems. The most literal example possible: instead of manually browsing
Handshake and applying to internships one by one, he built an automated
web-scraping bot to do it for him — the very bot currently generating this
cover letter. He considers this peak engineering efficiency.

He's also deeply people-oriented. He believes that "technical skill means
nothing if you can't meet people where they are," and that work culture and
the people around you are the real return on any role. He adapts his
communication to any audience, a skill sharpened from a year of IT support
for everyone from developers to professors who haven't touched a computer
in years.

On his first-ever hackathon: "Losing with your eyes open is how you
actually get better." He shows up, builds fast, reflects honestly, and
comes back sharper every time.
"""


# ── INTERNALS ─────────────────────────────────────────────────────────────────

# Base Handshake job search URL, pre-filtered to Internships only.
# Each keyword search appends &query=... to this.
HANDSHAKE_JOBS_URL = (
    "https://app.joinhandshake.com/ecs/jobs"
    "?page=1&per_page=25&sort_direction=desc&sort_column=default"
    "&job.job_type_names[]=Internship"
)

# Groq uses OpenAI's API format — same request shape, different URL + key.
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"

# Terminal color codes for readable output
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"
BOLD    = "\033[1m"

# Logging helpers — all print with a timestamp and a symbol for quick scanning
def log(sym, color, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}{BOLD}[{ts}] {sym}  {msg}{RESET}")

def info(msg):  log("→", CYAN,    msg)   # general progress
def ok(msg):    log("✓", GREEN,   msg)   # success
def warn(msg):  log("!", YELLOW,  msg)   # skipped / attention needed
def err(msg):   log("✗", RED,     msg)   # something broke
def ai(msg):    log("✦", MAGENTA, msg)   # LLM activity


# ── LLM ───────────────────────────────────────────────────────────────────────

def llm(system: str, user: str, max_tokens: int = 500) -> str:
    """
    Send a prompt to Groq and return the response text.

    Groq's API is OpenAI-compatible, so the request body uses the same
    messages array format: a system message sets the context/persona,
    and the user message is the actual task. We use urllib here to avoid
    pulling in an extra SDK dependency — the API is simple enough.
    """
    payload = json.dumps({
        "model":      GROQ_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }).encode()

    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        err(f"Groq API error {e.code}: {e.read().decode()[:200]}")
        return ""
    except Exception as e:
        err(f"Groq API exception: {e}")
        return ""


# ── SCORING ───────────────────────────────────────────────────────────────────

def score_job(title: str, company: str, description: str) -> tuple[int, str]:
    """
    Ask Groq to rate how well a job matches the candidate profile.
    Returns a (score, rationale) tuple — score is 1-10, rationale is one sentence.

    We tell the model to respond in raw JSON only (no markdown fences) so we
    can parse it directly. If parsing fails for whatever reason, score defaults
    to 0 so the job gets skipped rather than accidentally applied to.
    """
    system = f"""You are a career advisor evaluating job-candidate fit.
Given the candidate profile and a job posting, output ONLY a JSON object
(no markdown fences) with exactly two fields:
  "score"     : integer 1-10 (10 = perfect match)
  "rationale" : one sentence explaining the score

Candidate profile:
{CANDIDATE_PROFILE}
"""
    user = f"""Job Title   : {title}
Company     : {company}
Description :
{description[:1500]}
"""
    raw = llm(system, user, max_tokens=120)
    try:
        # Strip markdown fences in case the model adds them anyway
        clean = raw.replace("```json", "").replace("```", "").strip()
        obj   = json.loads(clean)
        return int(obj.get("score", 0)), obj.get("rationale", "")
    except Exception:
        return 0, f"Could not parse score (raw: {raw[:80]})"


# ── ANSWER GENERATION ─────────────────────────────────────────────────────────

def generate_answer(question: str, title: str, company: str,
                    description: str) -> str:
    """
    Generate a tailored response to a free-text application question.

    We pass in the specific question text, the job details, and the full
    candidate profile so the model has enough context to write something
    that actually sounds relevant — not a boilerplate answer.
    The system prompt instructs it to write as Piqim, keep it to 2-4 sentences,
    and work in the bot story where it fits naturally.
    """
    system = f"""You write short application answers on behalf of a job applicant.
Write in first person as Mustaqim (Piqim). Be genuine, specific, and concise
(2-4 sentences max). Avoid hollow openers like "I am passionate about...".
Where it fits naturally, mention that Piqim built an automated Handshake
application bot rather than applying manually — framing it as evidence of
his problem-solving instinct and drive to find innovative, efficient solutions.
Confident but not arrogant tone. No emojis. No bullet points.

Candidate profile:
{CANDIDATE_PROFILE}
"""
    user = f"""Job Title   : {title}
Company     : {company}
Description : {description[:800]}

Question:
\"\"\"{question}\"\"\"
"""
    return llm(system, user, max_tokens=250)


# ── TRACKER ───────────────────────────────────────────────────────────────────

class Tracker:
    """
    Keeps track of every job we've seen across runs using a CSV file.
    On init, it loads all previously recorded job IDs into memory so
    already_applied() is just a set lookup — no file reads mid-run.
    Every new outcome gets appended to the CSV immediately.
    """

    def __init__(self, path: str):
        self.path    = Path(path)
        self.applied: set[str] = set()
        self._load()

    def _load(self):
        # Read existing job IDs from the CSV into a set for fast lookups
        if self.path.exists():
            with open(self.path, newline="") as f:
                for row in csv.DictReader(f):
                    self.applied.add(row["job_id"])

    def already_applied(self, job_id: str) -> bool:
        return job_id in self.applied

    def record(self, job_id: str, title: str, company: str,
               status: str, score: int = 0):
        """Append a new row to the CSV and add the ID to the in-memory set."""
        self.applied.add(job_id)
        exists = self.path.exists()
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "job_id", "title", "company", "score", "status", "applied_at"
            ])
            if not exists:
                writer.writeheader()
            writer.writerow({
                "job_id":     job_id,
                "title":      title,
                "company":    company,
                "score":      score,
                "status":     status,
                "applied_at": datetime.now().isoformat(),
            })


# ── SCRAPER ───────────────────────────────────────────────────────────────────

async def search_jobs(page: Page, keyword: str) -> list[dict]:
    """
    Search Handshake for a keyword and return a list of job dicts.

    Handshake renders job cards as <a> tags with hrefs like /jobs/12345678.
    We grab all matching anchors, pull the numeric ID from the href, and
    extract the title and company from the card's inner text.
    Deduplication happens here within a single keyword search — cross-keyword
    deduplication happens in run().
    """
    search_url = (
        f"{HANDSHAKE_JOBS_URL}"
        f"&query={keyword.replace(' ', '+')}"
    )
    info(f"Searching: \"{keyword}\"")
    await page.goto(search_url, wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(2000)

    jobs: list[dict] = []
    seen_ids: set[str] = set()
    cards = await page.query_selector_all("a[href*='/jobs/']")

    for card in cards:
        href  = await card.get_attribute("href") or ""

        # Pull the job ID — it's the last numeric segment in the href path
        parts  = [p for p in href.split("/") if p.isdigit()]
        if not parts:
            continue
        job_id = parts[-1]
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        # Card text is usually "Job Title\nCompany Name\n..." — first two lines
        text    = (await card.inner_text()).strip().split("\n")
        title   = text[0].strip() if text else "Unknown Title"
        company = text[1].strip() if len(text) > 1 else "Unknown Company"

        jobs.append({
            "id":          job_id,
            "title":       title,
            "company":     company,
            "url":         f"https://app.joinhandshake.com{href}",
            "score":       0,
            "description": "",
        })

    ok(f"Found {len(jobs)} internship(s) for \"{keyword}\"")
    return jobs


async def get_job_description(page: Page, url: str) -> str:
    """
    Navigate to a job page and return the description text.

    Handshake doesn't use a consistent class name for the description container,
    so we try a few selectors in order of specificity and take the first one
    that returns meaningful content (>80 chars). Falls back to empty string
    if nothing works — the job will still get scored, just with less context.
    """
    try:
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(1000)
        for sel in [
            "[data-hook='job-description']",
            ".job-description",
            "[class*='description']",
            "article",
            "main",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) > 80:
                    return text[:2000]   # cap at 2000 chars — enough for scoring
        return ""
    except Exception:
        return ""


# ── APPLICATOR ────────────────────────────────────────────────────────────────

# Substrings we check for in a textarea's label to decide if it's a qualitative
# question worth generating an answer for (vs. something like a phone number field)
QUESTION_SIGNALS = [
    "why", "interest", "motivat", "tell us", "describe",
    "experience", "yourself", "passion", "contribut", "goal",
    "relevant", "qualif", "background", "about you",
]


async def fill_text_fields(page: Page, title: str, company: str,
                            description: str) -> int:
    """
    Find empty textareas on the current page and fill them with AI-generated answers.
    Returns the number of fields filled.

    For each visible, empty textarea, we walk up the DOM (up to 6 levels) looking
    for a nearby label, paragraph, or heading that contains the question text.
    If the question text matches any of the QUESTION_SIGNALS, we generate an answer
    and fill the field. We skip fields that are already filled or look like they're
    asking for something structured (phone, date, etc.).
    """
    filled    = 0
    textareas = await page.query_selector_all("textarea")

    for ta in textareas:
        if not await ta.is_visible():
            continue
        if (await ta.input_value()).strip():
            continue   # already has content, leave it alone

        # Walk up the DOM from the textarea to find the question label.
        # Handshake wraps inputs in divs so the label isn't always a direct sibling.
        question_text: str = ""
        try:
            question_text = await page.evaluate(
                """el => {
                    let node = el;
                    for (let i = 0; i < 6; i++) {
                        node = node.parentElement;
                        if (!node) break;
                        const lbl = node.querySelector('label, p, span, h3, h4, legend');
                        if (lbl && lbl.innerText && lbl.innerText.trim().length > 8)
                            return lbl.innerText.trim();
                    }
                    return '';
                }""",
                ta,
            )
        except Exception:
            pass

        # Only fill if this looks like a "tell us about yourself" type question
        if not any(sig in question_text.lower() for sig in QUESTION_SIGNALS):
            continue

        ai(f"  Generating answer for: \"{question_text[:70]}\"")
        answer = generate_answer(question_text, title, company, description)
        if answer:
            await ta.click()
            await ta.fill(answer)
            ok(f"  Field filled ({len(answer)} chars)")
            filled += 1

    return filled


async def apply_to_job(page: Page, job: dict, resume_path: str) -> str:
    """
    Attempt to apply to a single job. Returns a status string.

    Handshake's apply flow is multi-step — usually 2-4 pages in a modal.
    We loop up to 6 times, handling resume uploads and free-text fields on each
    step before clicking Next/Continue/Submit. The loop exits when we hit a
    Submit button or can't find a next button to click.

    Possible return values:
      applied               — confirmed success
      submitted_unconfirmed — submitted but couldn't find a confirmation element
      already_applied       — Handshake showed "Applied" before we even clicked
      no_apply_button       — couldn't find an Apply button on the page
      external              — job links to an external site, can't auto-apply
      dry_run               — DRY_RUN is True, skipped submission
      timeout               — page took too long
      error                 — something unexpected broke
    """
    try:
        # Navigate to the job page if we're not already there
        if job["id"] not in page.url:
            await page.goto(job["url"], wait_until="networkidle", timeout=30_000)
            await page.wait_for_timeout(1500)

        if await page.query_selector("text=Applied"):
            return "already_applied"

        apply_btn = (
            await page.query_selector("button:has-text('Apply')")
            or await page.query_selector("a:has-text('Apply')")
        )
        if not apply_btn:
            return "no_apply_button"

        btn_text = (await apply_btn.inner_text()).strip().lower()
        if "external" in btn_text or "website" in btn_text:
            return "external"

        if DRY_RUN:
            return "dry_run"

        await apply_btn.click()
        await page.wait_for_timeout(2000)

        # Step through the multi-page application modal
        for step in range(6):

            # Attach resume if a file upload input is present on this step
            file_input = await page.query_selector("input[type='file']")
            if file_input and Path(resume_path).exists():
                await file_input.set_input_files(resume_path)
                await page.wait_for_timeout(1000)
                ok(f"  Resume attached (step {step + 1})")

            # Fill any open-ended text fields on this step
            filled = await fill_text_fields(
                page, job["title"], job["company"], job["description"]
            )
            if filled:
                ai(f"  Groq answered {filled} question(s)")

            # Find the button to advance — could be Next, Continue, or Submit
            next_btn = (
                await page.query_selector("button:has-text('Next')")
                or await page.query_selector("button:has-text('Continue')")
                or await page.query_selector("button:has-text('Submit')")
                or await page.query_selector("button:has-text('Apply')")
            )
            if not next_btn:
                break   # no button found, assume we're done

            btn_label = (await next_btn.inner_text()).strip().lower()
            await next_btn.click()
            await page.wait_for_timeout(2000)

            if "submit" in btn_label or "apply" in btn_label:
                break   # that was the final step

        # Check for a success indicator — Handshake isn't consistent about this
        success = (
            await page.query_selector("text=Application submitted")
            or await page.query_selector("text=Successfully applied")
            or await page.query_selector("text=Applied")
            or await page.query_selector("[class*='success']")
        )
        return "applied" if success else "submitted_unconfirmed"

    except PlaywrightTimeout:
        return "timeout"
    except Exception as ex:
        err(f"  Exception on {job['url']}: {ex}")
        return "error"


# ── MAIN ──────────────────────────────────────────────────────────────────────

async def run():
    """
    Entry point. Runs the full pipeline:
      1. Validate config
      2. Open browser, wait for manual SSO login
      3. Scrape all keywords, deduplicate results
      4. Fetch each job's description and score it against the profile
      5. Sort by score, apply to everything above MIN_RELEVANCE_SCORE
      6. Print summary, close browser
    """

    if GROQ_API_KEY == "YOUR_API_KEY_HERE":
        err("Set your GROQ_API_KEY before running.")
        err("  Get a free key at: https://console.groq.com")
        err("  Then: export GROQ_API_KEY='gsk_...'")
        sys.exit(1)

    resume = Path(RESUME_PATH)
    if not resume.exists():
        err(f"Resume not found at '{RESUME_PATH}'. Update RESUME_PATH in bot.py.")
        sys.exit(1)

    tracker = Tracker(TRACKER_FILE)

    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗
║       Handshake Internship Auto-Applicator  v2               ║
║  + Groq-powered cover letters & job relevance scoring        ║
╚══════════════════════════════════════════════════════════════╝{RESET}
  Resume       : {resume.resolve()}
  Keywords     : {len(KEYWORDS)} terms
  Min score    : {MIN_RELEVANCE_SCORE}/10
  Max apps     : {MAX_APPLICATIONS}
  Dry run      : {DRY_RUN}
  Tracker      : {TRACKER_FILE}
""")

    async with async_playwright() as pw:
        # Run headed (visible browser) — needed for SSO and to debug if things break
        browser = await pw.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context()
        page    = await context.new_page()

        # SSO login is manual — every university's flow is different and most
        # use MFA, so there's no clean way to automate this part
        await page.goto("https://app.joinhandshake.com/login")
        print(f"{YELLOW}{BOLD}  ➤  A browser window has opened.")
        print(f"  ➤  Log in with your university SSO.")
        print(f"  ➤  Once you see your Handshake dashboard, return here.")
        input(f"\n  Press ENTER when you're logged in...{RESET}\n")

        if "login" in page.url or "sign_in" in page.url:
            err("Still on the login page — please try again.")
            await browser.close()
            return

        ok("Logged in!\n")

        # Scrape each keyword and collect unique jobs.
        # The same posting can show up across multiple keyword searches,
        # so we deduplicate by job ID before doing anything else.
        seen_ids: set[str] = set()
        all_jobs: list[dict] = []

        for keyword in KEYWORDS:
            jobs = await search_jobs(page, keyword)
            for job in jobs:
                if job["id"] not in seen_ids:
                    seen_ids.add(job["id"])
                    all_jobs.append(job)

        info(f"Total unique internships found: {len(all_jobs)}")
        info("Fetching descriptions and scoring against your profile...\n")

        # Score every job we haven't applied to before.
        # Jobs below MIN_RELEVANCE_SCORE get logged as "low_score" and skipped.
        scored_jobs: list[dict] = []

        for job in all_jobs:
            if tracker.already_applied(job["id"]):
                warn(f"Already applied — skip: {job['title']} @ {job['company']}")
                continue

            description        = await get_job_description(page, job["url"])
            job["description"] = description
            score, rationale   = score_job(job["title"], job["company"], description)
            job["score"]       = score
            job["rationale"]   = rationale

            color = GREEN if score >= MIN_RELEVANCE_SCORE else YELLOW
            print(f"{color}{BOLD}  [{score:2}/10]{RESET}  {job['title']} @ {job['company']}")

            if score < MIN_RELEVANCE_SCORE:
                warn(f"         Below threshold — {rationale}")
                tracker.record(job["id"], job["title"], job["company"], "low_score", score)
            else:
                ai(f"         {rationale}")
                scored_jobs.append(job)

        # Apply to best matches first
        scored_jobs.sort(key=lambda j: j["score"], reverse=True)

        print(f"\n{CYAN}{BOLD}  {len(scored_jobs)} job(s) cleared the bar "
              f"(≥{MIN_RELEVANCE_SCORE}/10). Starting applications...{RESET}\n")

        applied_count  = 0
        skipped_count  = 0
        external_count = 0
        error_count    = 0

        for job in scored_jobs:
            if applied_count >= MAX_APPLICATIONS:
                warn(f"Hit the MAX_APPLICATIONS limit ({MAX_APPLICATIONS}). Stopping.")
                break

            label = f"[{job['score']}/10] {job['title']} @ {job['company']}"
            info(f"Applying → {label}")

            status = await apply_to_job(page, job, RESUME_PATH)

            if status == "applied":
                ok(f"Applied ✓  {label}")
                tracker.record(job["id"], job["title"], job["company"], "applied", job["score"])
                applied_count += 1

            elif status in ("submitted_unconfirmed", "dry_run"):
                ok(f"Submitted  {label}")
                tracker.record(job["id"], job["title"], job["company"], status, job["score"])
                applied_count += 1

            elif status == "already_applied":
                warn(f"Already applied: {label}")
                skipped_count += 1

            elif status == "external":
                warn(f"External link — apply manually: {label}")
                tracker.record(job["id"], job["title"], job["company"], "external_link", job["score"])
                external_count += 1

            else:
                err(f"Error ({status}): {label}")
                tracker.record(job["id"], job["title"], job["company"], f"error:{status}", job["score"])
                error_count += 1

            await asyncio.sleep(DELAY_BETWEEN_APPS)

        print(f"""
{GREEN}{BOLD}══════════════════════ RUN COMPLETE ══════════════════════{RESET}
  ✓  Applied               : {applied_count}
  →  Skipped (already done): {skipped_count}
  ↗  External (manual)     : {external_count}
  ✗  Errors                : {error_count}
  ✦  Model used            : Groq / {GROQ_MODEL}
  📄 Full log              : {TRACKER_FILE}
{GREEN}{BOLD}══════════════════════════════════════════════════════════{RESET}
""")
        input("Press ENTER to close the browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())