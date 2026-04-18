#!/usr/bin/env python3
"""
Handshake Internship Auto-Applicator v2
----------------------------------------
Scrapes Handshake for internship postings, applies to each one, and uses
Groq (LLaMA 3.3 70B) only when needed — to write cover letters and answer
free-text questions during the application. Every outcome gets logged to a CSV.

Setup:
  1. pip install -r requirements.txt && playwright install chromium
  2. Get a free Groq key at https://console.groq.com
  3. python bot.py — log in via SSO when the browser opens, then press ENTER
"""

import asyncio
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout


# ── CONFIG ────────────────────────────────────────────────────────────────────
# Everything you'd want to change is here. Don't touch anything below this.

# Load variables from .env (if present) before reading config values.
load_dotenv()

# Free key at https://console.groq.com — or set via: export GROQ_API_KEY='gsk_...'
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_API_KEY_HERE")

# What to search on Handshake. Each keyword runs as its own search.
KEYWORDS = [
    "data science",
    #"data engineering",
    #"software engineering",
    #"computer science",
    #"fullstack developer",
    #"developer",
    #"machine learning",
    #"data analyst",
    #"backend engineer",
    #"frontend engineer",
    #"AI engineer",
    #"artificial intelligence",
]

# Jobs scoring below this (out of 10) get skipped. Raise it to be picky,
# lower it if you want to cast a wider net.
MAX_APPLICATIONS   = 25     # hard stop — won't submit more than this per run
MAX_PAGES          = 5      # pages to scrape per keyword (25 results each = up to 125 per keyword)
DELAY_BETWEEN_APPS = 4      # seconds between each application, don't be rude
TRACKER_FILE       = "applied_jobs.csv"
DRY_RUN            = False  # set True to scrape without submitting


# ── CANDIDATE PROFILE ─────────────────────────────────────────────────────────
# Groq uses this to write cover letters and answer free-text questions.
# The more accurate it is, the better the output. Replace with your own if needed.

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
HANDSHAKE_BASE_URL = "https://ucsd.joinhandshake.com"

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

    Groq's free tier caps at 12,000 tokens/minute. On a 429 rate limit error,
    we wait and retry up to 3 times with increasing delays before giving up.
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
            # Cloudflare blocks requests with no User-Agent (treats them as bots)
            "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )

    # Retry up to 3 times on rate limit — waits grow: 15s, 30s, 60s
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 429:
                wait = 15 * (2 ** attempt)   # 15s, 30s, 60s
                warn(f"Groq rate limit hit — waiting {wait}s before retry ({attempt + 1}/3)")
                time.sleep(wait)
            else:
                err(f"Groq API error {e.code}: {body[:200]}")
                return ""
        except Exception as e:
            err(f"Groq API exception: {e}")
            return ""

    err("Groq rate limit — all retries exhausted, skipping this call")
    return ""


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

    def record(self, job_id: str, title: str, company: str, status: str):
        """Append a new row to the CSV and add the ID to the in-memory set."""
        self.applied.add(job_id)
        exists = self.path.exists()
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "job_id", "title", "company", "status", "applied_at"
            ])
            if not exists:
                writer.writeheader()
            writer.writerow({
                "job_id":     job_id,
                "title":      title,
                "company":    company,
                "status":     status,
                "applied_at": datetime.now().isoformat(),
            })


# ── SCRAPER ───────────────────────────────────────────────────────────────────

async def search_jobs(page: Page, keyword: str) -> list[dict]:
    """
    Search Handshake for a keyword across multiple pages and return all job dicts.

    From the HTML we know:
    - Job cards are elements with data-hook="job-result-card | {id}"
    - The job ID is after the pipe in that attribute
    - Title comes from the <a> tag's aria-label: "View {title}" → strip "View "
    - Company comes from the <img alt="{company}"> inside the card

    Pagination: loops up to MAX_PAGES. Stops early if a page returns fewer
    cards than per_page (meaning we've hit the last page of results).
    """
    per_page  = 25
    jobs: list[dict] = []
    seen_ids: set[str] = set()

    for page_num in range(1, MAX_PAGES + 1):
        search_url = (
            f"{HANDSHAKE_BASE_URL}/job-search"
            f"?jobType=3&per_page={per_page}&page={page_num}"
            f"&query={keyword.replace(' ', '+')}"
        )

        if page_num == 1:
            info(f"Searching: \"{keyword}\"")
        else:
            info(f"  Page {page_num}: \"{keyword}\"")

        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

        try:
            await page.wait_for_selector(
                "[data-hook^='job-result-card | ']", timeout=10_000
            )
        except PlaywrightTimeout:
            if page_num == 1:
                warn(f"No job cards loaded for \"{keyword}\" — skipping")
            break   # no cards on this page, we've gone past the last page

        await page.wait_for_timeout(500)

        cards        = await page.query_selector_all("[data-hook^='job-result-card | ']")
        cards_found  = 0

        for card in cards:
            hook   = await card.get_attribute("data-hook") or ""
            job_id = hook.split("|")[-1].strip()
            if not job_id.isdigit() or job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            cards_found += 1

            # Title: <a aria-label="View AI Engineering Intern"> → strip "View "
            title   = "Unknown Title"
            link_el = await card.query_selector("a[aria-label^='View ']")
            if link_el:
                aria  = await link_el.get_attribute("aria-label") or ""
                title = aria.removeprefix("View ").strip()

            # Company: <img alt="CaterAI"> inside the card
            company = "Unknown Company"
            img_el  = await card.query_selector("img[alt]")
            if img_el:
                company = (await img_el.get_attribute("alt") or "").strip()

            jobs.append({
                "id":          job_id,
                "title":       title,
                "company":     company,
                "url":         f"{HANDSHAKE_BASE_URL}/job-search/{job_id}",
                "description": "",
            })

        # Fewer results than a full page means this was the last page
        if cards_found < per_page:
            break

    ok(f"Found {len(jobs)} internship(s) for \"{keyword}\" ({page_num} page(s))")
    return jobs


async def get_job_description(page: Page, url: str) -> str:
    """
    Navigate to a job page and return the description text.

    The job detail panel is in data-hook="right-content".
    Falls back to broader selectors if that's empty.
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(1500)
        for sel in [
            "[data-hook='right-content']",
            "[data-hook='job-description']",
            "[class*='description']",
            "article",
            "main",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) > 80:
                    return text[:2000]
        return ""
    except Exception:
        return ""


# ── COVER LETTER ─────────────────────────────────────────────────────────────

def generate_cover_letter(title: str, company: str, description: str) -> str:
    """
    Generate a full cover letter for jobs that ask for one as a file upload.

    Unlike generate_answer() which writes 2-4 sentences for a specific question,
    this writes a proper 3-paragraph cover letter: intro, body (relevant
    experience), and close. Still keeps it tight — recruiters don't read essays.
    """
    system = f"""You write cover letters on behalf of a job applicant.
Write in first person as Mustaqim (Piqim). Three short paragraphs:
  1. Why this role and company specifically — be concrete, not generic
  2. Two or three most relevant experiences/projects from the profile
  3. Brief close — what you'd bring and enthusiasm to discuss further
No "Dear Hiring Manager" header needed. No hollow phrases like
"I am passionate about". Where natural, mention that Piqim built an
automated Handshake application bot — evidence of how he approaches problems.
Confident, specific, human. Keep it under 250 words total.

Candidate profile:
{CANDIDATE_PROFILE}
"""
    user = f"""Job Title   : {title}
Company     : {company}
Description : {description[:800]}
"""
    return llm(system, user, max_tokens=400)


def save_cover_letter(title: str, company: str, content: str) -> str:
    """
    Save cover letter text to a temp .txt file and return the file path.
    Handshake accepts plain text files for document uploads.
    """
    import tempfile
    safe_company = "".join(c for c in company if c.isalnum() or c in " _-")[:30]
    filename = f"cover_letter_{safe_company}.txt".replace(" ", "_")
    path = Path(tempfile.gettempdir()) / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


# ── APPLICATOR ────────────────────────────────────────────────────────────────

# Substrings we check for in a textarea's label to decide if it's a qualitative
# question worth generating an answer for (vs. something like a phone number field)
QUESTION_SIGNALS = [
    "why", "interest", "motivat", "tell us", "describe",
    "experience", "yourself", "passion", "contribut", "goal",
    "relevant", "qualif", "background", "about you",
]

# Labels that indicate a file upload or URL field the bot cannot fill automatically.
# Matched case-insensitively against the label text nearest to the field.
MANUAL_UPLOAD_SIGNALS = [
    "transcript", "resume", "cv", "portfolio", "writing sample",
    "work sample", "reference", "letter of recommendation",
]
MANUAL_URL_SIGNALS = [
    "github", "gitlab", "portfolio", "personal site", "website",
    "linkedin", "behance", "dribbble",
]


async def detect_manual_fields(page: Page) -> list[str]:
    """
    Scan the open apply modal for fields the bot cannot fill automatically.
    Returns a human-readable list of field descriptions so the user knows
    exactly what to fill in before pressing ENTER.

    Detects:
      - File upload inputs whose label suggests a transcript, resume, portfolio, etc.
        (cover letter uploads are handled automatically and are excluded here)
      - Text/URL inputs whose label matches GitHub, portfolio, personal site, etc.
      - Any visible required field that is still empty after the bot's auto-fill pass
    """
    modal = "[data-hook='apply-modal-content']"
    needed: list[str] = []

    # ── File uploads (non-cover-letter) ──────────────────────────────────────
    file_inputs = await page.query_selector_all(f"{modal} input[type='file']")
    for fi in file_inputs:
        if not await fi.is_visible():
            continue
        label_text: str = await page.evaluate(
            """el => {
                let node = el;
                for (let i = 0; i < 6; i++) {
                    node = node.parentElement;
                    if (!node) break;
                    const lbl = node.querySelector('label, legend, p, span, h3, h4');
                    if (lbl && lbl.innerText && lbl.innerText.trim().length > 2)
                        return lbl.innerText.trim().toLowerCase();
                }
                return '';
            }""",
            fi,
        )
        # Skip if the file input lives inside a cover-letter fieldset (handled
        # automatically by the cover-letter generation logic above).
        # We check both the direct label text AND whether any ancestor fieldset
        # has a "cover letter" legend — the "Upload new" button inside the
        # cover-letter fieldset would otherwise be flagged as a manual upload.
        in_cover_letter_fieldset: bool = await page.evaluate(
            """el => {
                let node = el;
                while (node) {
                    if (node.tagName === 'FIELDSET') {
                        const legend = node.querySelector('legend');
                        if (legend && legend.innerText.toLowerCase().includes('cover letter'))
                            return true;
                        break;
                    }
                    node = node.parentElement;
                }
                return false;
            }""",
            fi,
        )
        if in_cover_letter_fieldset or "cover letter" in label_text:
            continue  # handled automatically

        for sig in MANUAL_UPLOAD_SIGNALS:
            if sig in label_text:
                needed.append(f"\U0001f4ce File upload \u2014 \"{label_text[:60]}\"")
                break
        else:
            needed.append(
                f"\U0001f4ce File upload \u2014 \"{label_text[:60]}\"" if label_text
                else "\U0001f4ce File upload (unlabeled)"
            )

    # ── URL / text inputs that need manual data ───────────────────────────────
    text_inputs = await page.query_selector_all(
        f"{modal} input[type='text'], {modal} input[type='url'], {modal} input:not([type])"
    )
    for ti in text_inputs:
        if not await ti.is_visible():
            continue
        if (await ti.input_value()).strip():
            continue
        label_text: str = await page.evaluate(
            """el => {
                if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').toLowerCase();
                if (el.getAttribute('placeholder')) return el.getAttribute('placeholder').toLowerCase();
                let node = el;
                for (let i = 0; i < 6; i++) {
                    node = node.parentElement;
                    if (!node) break;
                    const lbl = node.querySelector('label, legend, p, span, h3, h4');
                    if (lbl && lbl.innerText && lbl.innerText.trim().length > 2)
                        return lbl.innerText.trim().toLowerCase();
                }
                return '';
            }""",
            ti,
        )
        for sig in MANUAL_URL_SIGNALS:
            if sig in label_text:
                needed.append(f"\U0001f517 URL / text field \u2014 \"{label_text[:60]}\"")
                break

    # ── Required fields still empty ───────────────────────────────────────────
    required_inputs = await page.query_selector_all(
        f"{modal} input[required], {modal} textarea[required], "
        f"{modal} input[aria-required='true'], {modal} textarea[aria-required='true']"
    )
    for ri in required_inputs:
        if not await ri.is_visible():
            continue
        if (await ri.input_value()).strip():
            continue
        label_text: str = await page.evaluate(
            """el => {
                if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
                if (el.getAttribute('placeholder')) return el.getAttribute('placeholder');
                let node = el;
                for (let i = 0; i < 6; i++) {
                    node = node.parentElement;
                    if (!node) break;
                    const lbl = node.querySelector('label, legend, p, span, h3, h4');
                    if (lbl && lbl.innerText && lbl.innerText.trim().length > 2)
                        return lbl.innerText.trim();
                }
                return '(unlabeled required field)';
            }""",
            ri,
        )
        entry = f"\u26a0\ufe0f  Required field \u2014 \"{label_text[:60]}\""
        if entry not in needed:
            needed.append(entry)

    return needed


async def wait_for_enter_or_submit(page: Page) -> str:
    """
    Pause the bot and wait for one of two things:

      1. User presses ENTER in the terminal after manually filling fields.
         The bot then clicks Submit itself.

      2. User clicks Submit/Apply in the browser themselves.
         The bot detects the modal closing and skips its own Submit click.

    Returns "bot_submits" or "user_submitted".
    """
    loop = asyncio.get_event_loop()

    # Task A: wait for ENTER in the terminal (non-blocking via thread executor)
    enter_future = loop.run_in_executor(None, sys.stdin.readline)
    enter_task   = asyncio.ensure_future(asyncio.wrap_future(enter_future))

    # Task B: poll the browser every 500 ms waiting for the modal to close.
    # IMPORTANT: only check for success AFTER the modal is gone.
    # The "Cancel application" button lives INSIDE the modal header and is
    # always present while the modal is open — checking it before the modal
    # closes would fire "user_submitted" instantly, before the user does anything.
    async def watch_browser():
        for _ in range(600):   # up to 5 minutes
            modal_present = await page.query_selector("[data-hook='apply-modal-content']")
            if not modal_present:
                # Modal closed — check the main page for a success/applied state
                right = "[data-hook='right-content']"
                success = (
                    await page.query_selector(f"{right} button:text('Withdraw application')")
                    or await page.query_selector(f"{right} [role='alert'] h2")
                    or await page.query_selector("text=Application submitted")
                    or await page.query_selector("text=Successfully applied")
                )
                return "user_submitted" if success else "bot_submits"
            await asyncio.sleep(0.5)
        return "timeout"

    browser_task = asyncio.ensure_future(watch_browser())

    done, pending = await asyncio.wait(
        [enter_task, browser_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()

    winner = done.pop()
    result = winner.result() if not winner.cancelled() else None
    return "user_submitted" if result == "user_submitted" else "bot_submits"


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


async def _is_external_job(page: Page, right: str) -> bool:
    """
    Scan the right-content panel for signals that this job requires external
    application. Runs immediately after domcontentloaded — no waiting needed.

    Handshake external postings show buttons like "Apply on employer's website"
    or "Apply on company website" instead of the standard Handshake apply modal.
    These never match the normal Apply button selectors, so without this check
    they'd time out waiting for a button and return no_apply_button.
    """
    EXTERNAL_TEXT_SIGNALS = [
        "apply on employer", "apply on company", "apply externally",
        "apply on their website", "apply on the employer",
        "apply on company website", "apply on employer's website",
        "visit company website", "external application", "apply at",
        "apply on their site",
    ]
    try:
        for selector in [f"{right} button", f"{right} a"]:
            elements = await page.query_selector_all(selector)
            for el in elements:
                if not await el.is_visible():
                    continue
                txt  = (await el.inner_text()).strip().lower()
                aria = (await el.get_attribute("aria-label") or "").lower()
                for signal in EXTERNAL_TEXT_SIGNALS:
                    if signal in txt or signal in aria:
                        return True
    except Exception:
        pass
    return False


async def apply_to_job(page: Page, job: dict) -> str:
    """
    Attempt to apply to a single job. Returns a status string.

    Possible return values:
      applied               — confirmed success
      submitted_unconfirmed — submitted but couldn't find a confirmation element
      already_applied       — Handshake showed an applied state before clicking
      no_apply_button       — couldn't find an Apply button on the page
      external              — job links to an external site, can't auto-apply
      dry_run               — DRY_RUN is True, skipped submission
      timeout               — page took too long
      error                 — something unexpected broke
    """
    try:
        # Always navigate fresh with the pagination params — this ensures the
        # right-content detail panel renders fully. Do NOT skip based on
        # page.url: a prior get_job_description call used a URL without params
        # that may leave the right panel in an unrendered state.
        job_url = f"{HANDSHAKE_BASE_URL}/job-search/{job['id']}?page=1&per_page=25"
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)

        # ── Fast external detection (runs immediately after domcontentloaded) ──
        # External postings show "Apply on company website"-style buttons that
        # never match the standard Apply selectors. Without this early check the
        # bot would wait the full 12 s for a Handshake apply button that will
        # never appear, then log a misleading no_apply_button error.
        # We give the right panel 2 s to paint its buttons, then scan.
        right = "[data-hook='right-content']"
        try:
            await page.wait_for_selector(right, timeout=2_000)
        except PlaywrightTimeout:
            pass
        if await _is_external_job(page, right):
            return "external"

        # ── Wait for the right panel to fully render ──────────────────────────
        # Wait for the Apply button OR the already-applied indicator — whichever
        # appears first means the right panel is ready.
        try:
            await page.wait_for_selector(
                "[data-hook='right-content'] button[aria-label='Apply'],"
                "[data-hook='right-content'] button[aria-label^='Apply to'],"
                "[data-hook='right-content'] button[aria-label='Cancel application'],"
                "[data-hook='right-content'] [data-hook='applied-indicator']",
                timeout=12_000,
            )
        except PlaywrightTimeout:
            # Right panel still didn't render — give it one last chance.
            # Run the external check one more time before giving up — some slow
            # pages only paint the external button after the full timeout.
            await page.wait_for_timeout(3000)
            if await _is_external_job(page, right):
                return "external"

        # ── Fetch description now that we are on the right page ───────────────
        # Fetching here (rather than in a separate navigation before this call)
        # avoids the double-navigation bug where get_job_description would land
        # on a slightly different URL and leave apply_to_job with a stale page.
        desc = ""
        for sel in ["[data-hook='right-content']", "[data-hook='job-description']",
                    "[class*='description']", "article", "main"]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) > 80:
                    desc = text[:2000]
                    break
        job["description"] = desc

        # ── Check if already applied ──────────────────────────────────────────
        # BUG FIX: scope ALL selectors to [data-hook='right-content'].
        #
        # Handshake renders a split-pane: the LEFT panel is a scrolling list of
        # job cards. Any card in that list for a job you previously applied to
        # shows a "Cancel application" button. The old unscoped selector matched
        # those left-panel cards and returned "already_applied" for every single
        # job — even ones that were never applied to.
        already = (
            # "Withdraw application" button shown when already applied (from HTML)
            await page.query_selector(f"{right} button:text('Withdraw application')")
            # Role-alert banner: "Applied on ..." shown at the top of the right panel
            or await page.query_selector(f"{right} [role='alert'] h2")
            # Apply button is disabled (aria-disabled="true") when already applied
            or await page.query_selector(f"{right} button[aria-disabled='true'][aria-label='Apply']")
            # Legacy / fallback selectors
            or await page.query_selector(f"{right} button[aria-label='Cancel application']")
            or await page.query_selector(f"{right} [aria-label='Applied']")
            or await page.query_selector(f"{right} [data-hook='applied-indicator']")
        )
        if already:
            return "already_applied"

        # ── Locate the Apply button ───────────────────────────────────────────
        # Prefer the button inside the right-content panel. There are two Apply
        # buttons on the page (panel header + floating sticky bar), so we use
        # .first to avoid a strict-mode violation.
        #
        # Priority order:
        #   1. Exact aria-label="Apply" inside right-content
        #   2. Starts-with aria-label="Apply to …" inside right-content
        #   3. Any visible button whose inner text is exactly "Apply"
        apply_btn = None

        for selector in [
            "[data-hook='right-content'] button[aria-label='Apply']",
            "[data-hook='right-content'] button[aria-label^='Apply to']",
            "button[aria-label='Apply']",
            "button[aria-label^='Apply to']",
        ]:
            els = await page.query_selector_all(selector)
            for el in els:
                if await el.is_visible():
                    apply_btn = el
                    break
            if apply_btn:
                break

        # Last resort: find any visible button whose text content is "Apply"
        if not apply_btn:
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                text = (await btn.inner_text()).strip()
                if text == "Apply" and await btn.is_visible():
                    apply_btn = btn
                    break

        if not apply_btn:
            # One last pass: some external postings render their "Apply on
            # employer's website" button slowly. Check before giving up.
            if await _is_external_job(page, right):
                return "external"
            return "no_apply_button"

        # ── Check for external-link indicators ───────────────────────────────
        btn_aria = (await apply_btn.get_attribute("aria-label") or "").lower()
        btn_text = (await apply_btn.inner_text()).strip().lower()
        if "external" in btn_aria or "website" in btn_aria:
            return "external"

        # Some jobs show an "Apply on company website" button as the main CTA
        if "website" in btn_text or "company site" in btn_text:
            return "external"

        if DRY_RUN:
            return "dry_run"

        # ── Click Apply and wait for the modal ────────────────────────────────
        await apply_btn.click()

        try:
            await page.wait_for_selector(
                "[data-hook='apply-modal-content']", timeout=8_000
            )
        except PlaywrightTimeout:
            # Modal never appeared — Handshake may have opened an external link
            # or the click didn't register properly
            return "no_modal"

        await page.wait_for_timeout(1000)   # let modal fully paint

        # ── Cover letter (optional) ───────────────────────────────────────────
        cover_letter_input = await page.evaluate("""
            () => {
                const fieldsets = document.querySelectorAll(
                    '[data-hook="apply-modal-content"] fieldset'
                );
                for (const fs of fieldsets) {
                    const legend = fs.querySelector('legend');
                    if (legend && legend.innerText.toLowerCase().includes('cover letter')) {
                        const input = fs.querySelector('input[type="file"]');
                        return input ? true : false;
                    }
                }
                return false;
            }
        """)

        if cover_letter_input:
            ai(f"  Cover letter required — generating...")
            cl_text = generate_cover_letter(
                job["title"], job["company"], job["description"]
            )
            if cl_text:
                cl_path = save_cover_letter(job["title"], job["company"], cl_text)
                cl_file_input = await page.evaluate("""
                    () => {
                        const fieldsets = document.querySelectorAll(
                            '[data-hook="apply-modal-content"] fieldset'
                        );
                        for (const fs of fieldsets) {
                            const legend = fs.querySelector('legend');
                            if (legend && legend.innerText.toLowerCase().includes('cover letter')) {
                                const input = fs.querySelector('input[type="file"]');
                                if (input) {
                                    input.style.display = 'block';
                                    input.style.opacity = '1';
                                    return true;
                                }
                            }
                        }
                        return false;
                    }
                """)
                if cl_file_input:
                    file_input = await page.query_selector(
                        "[data-hook='apply-modal-content'] fieldset input[type='file']"
                    )
                    if file_input:
                        await file_input.set_input_files(cl_path)

                        # ── Phase 1: wait for filename to appear ──────────────
                        # Handshake renders the filename (or "replace") in the
                        # fieldset once it has received the file bytes.
                        CL_FIELDSET_JS = """
                            () => {
                                const fieldsets = document.querySelectorAll(
                                    '[data-hook="apply-modal-content"] fieldset'
                                );
                                for (const fs of fieldsets) {
                                    const legend = fs.querySelector('legend');
                                    if (legend && legend.innerText.toLowerCase().includes('cover letter'))
                                        return fs;
                                }
                                return null;
                            }
                        """
                        try:
                            await page.wait_for_function(
                                """() => {
                                    const fieldsets = document.querySelectorAll(
                                        '[data-hook="apply-modal-content"] fieldset'
                                    );
                                    for (const fs of fieldsets) {
                                        const legend = fs.querySelector('legend');
                                        if (legend && legend.innerText.toLowerCase().includes('cover letter')) {
                                            const text = fs.innerText.toLowerCase();
                                            return text.includes('.txt') || text.includes('.pdf')
                                                   || text.includes('replace') || text.includes('uploaded');
                                        }
                                    }
                                    return false;
                                }""",
                                timeout=8_000,
                            )
                        except PlaywrightTimeout:
                            await page.wait_for_timeout(3_000)

                        # ── Phase 2: wait for "converting" to finish ──────────
                        # After the filename appears, Handshake converts the file
                        # server-side and shows a "Converting..." spinner. The
                        # Submit button stays disabled until this clears. We poll
                        # until the word "converting" is gone from the fieldset.
                        ai(f"  Waiting for cover letter conversion...")
                        try:
                            await page.wait_for_function(
                                """() => {
                                    const fieldsets = document.querySelectorAll(
                                        '[data-hook="apply-modal-content"] fieldset'
                                    );
                                    for (const fs of fieldsets) {
                                        const legend = fs.querySelector('legend');
                                        if (legend && legend.innerText.toLowerCase().includes('cover letter')) {
                                            const text = fs.innerText.toLowerCase();
                                            // Still converting — keep waiting
                                            if (text.includes('converting')) return false;
                                            // No filename yet either — keep waiting
                                            if (!text.includes('.txt') && !text.includes('.pdf')
                                                && !text.includes('replace') && !text.includes('uploaded'))
                                                return false;
                                            return true;
                                        }
                                    }
                                    // Fieldset gone — assume done
                                    return true;
                                }""",
                                timeout=30_000,   # conversion can be slow on bad connections
                            )
                        except PlaywrightTimeout:
                            warn(f"  Cover letter conversion timed out — submitting anyway")
                        ok(f"  Cover letter ready")

        # ── Free-text questions ───────────────────────────────────────────────
        filled = await fill_text_fields(
            page, job["title"], job["company"], job["description"]
        )
        if filled:
            ai(f"  Groq answered {filled} question(s)")

        # ── Detect fields needing manual input ────────────────────────────────
        # Scan the modal for anything the bot cannot fill: transcript uploads,
        # GitHub/portfolio URLs, other file uploads, or unfilled required fields.
        manual_fields = await detect_manual_fields(page)

        user_submitted = False
        if manual_fields:
            print()
            warn(f"  ⏸  Manual input needed for: {job['title']} @ {job['company']}")
            for field in manual_fields:
                warn(f"      {field}")
            warn(f"  Fill the highlighted fields in the browser, then either:")
            warn(f"    • Press ENTER here to let the bot click Submit, OR")
            print()

            outcome = await wait_for_enter_or_submit(page)
            if outcome == "user_submitted":
                ok(f"  Detected browser submission — continuing.")
                user_submitted = True
            else:
                ok(f"  ENTER received — bot will click Submit now.")

        # ── Submit (only if the user hasn't already clicked it themselves) ────
        if not user_submitted:
            submit_btn = None
            for selector in [
                "[data-hook='apply-modal-content'] button:has-text('Submit Application')",
                "[data-hook='apply-modal-content'] button:has-text('Submit')",
                "[data-hook='apply-modal-content'] button:has-text('Apply')",
            ]:
                submit_btn = await page.query_selector(selector)
                if submit_btn and await submit_btn.is_visible():
                    break

            if not submit_btn:
                return "no_submit_button"

            await submit_btn.click()
            await page.wait_for_timeout(2500)   # give Handshake time to process

        # ── Confirm success ───────────────────────────────────────────────────
        success = (
            await page.query_selector("button[aria-label='Cancel application']")
            or await page.query_selector("text=Application submitted")
            or await page.query_selector("text=Successfully applied")
        )
        return "applied" if success else "submitted_unconfirmed"

    except PlaywrightTimeout:
        # Before declaring a timeout, check whether the page actually shows an
        # already-applied state. Some jobs (e.g. external or slow-loading ones)
        # time out on the wait_for_selector but the page is fully loaded and
        # already shows "Applied" or a disabled Apply button.
        try:
            right = "[data-hook='right-content']"
            already = (
                await page.query_selector(f"{right} button:text('Withdraw application')")
                or await page.query_selector(f"{right} [role='alert'] h2")
                or await page.query_selector(f"{right} button[aria-disabled='true'][aria-label='Apply']")
                or await page.query_selector(f"{right} button[aria-label='Cancel application']")
            )
            if already:
                return "already_applied"
        except Exception:
            pass
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
      4. Apply to each new job — Groq fires only when the modal needs a cover letter or question answered
      5. Print summary, close browser
    """

    if GROQ_API_KEY == "YOUR_API_KEY_HERE":
        err("Set your GROQ_API_KEY before running.")
        err("  Get a free key at: https://console.groq.com")
        err("  Then: export GROQ_API_KEY='gsk_...'")
        sys.exit(1)

    tracker = Tracker(TRACKER_FILE)

    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗
║       Handshake Internship Auto-Applicator  v2               ║
║  + Groq-powered cover letters & job relevance scoring        ║
╚══════════════════════════════════════════════════════════════╝{RESET}
  Keywords     : {len(KEYWORDS)} terms (up to {MAX_PAGES} pages each)
  Max apps     : {MAX_APPLICATIONS}
  Dry run      : {DRY_RUN}
  Tracker      : {TRACKER_FILE}
""")

    async with async_playwright() as pw:
        # Run headed (visible browser) — needed for SSO and to debug if things break
        browser = await pw.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context()
        page    = await context.new_page()

        # SSO login is manual — UCSD routes through DUO which can take a while.
        # Instead of relying on the user pressing ENTER at the right moment,
        # we just poll every 10 seconds until a tab lands on the dashboard.
        await page.goto(f"{HANDSHAKE_BASE_URL}/login")
        print(f"{YELLOW}{BOLD}  ➤  A browser window has opened.")
        print(f"  ➤  Log in with your UCSD SSO and complete DUO authentication.")
        print(f"  ➤  The bot will detect when you're on the dashboard automatically.{RESET}\n")

        # Wait up to 5 minutes total. 10 second intervals keeps it responsive
        # without hammering context.pages in a tight loop.
        page = None
        for attempt in range(30):
            page = next(
                (p for p in context.pages
                 if "joinhandshake.com" in p.url and "login" not in p.url),
                None
            )
            if page:
                break
            info(f"Not logged in yet — checking again in 10 seconds... ({attempt + 1}/30)")
            await asyncio.sleep(10)

        if not page:
            err("Timed out after 5 minutes. Run the bot again and complete login faster.")
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

        # Filter out already-applied jobs before starting
        pending = [j for j in all_jobs if not tracker.already_applied(j["id"])]
        skipped_count = len(all_jobs) - len(pending)
        if skipped_count:
            info(f"Skipping {skipped_count} already-applied job(s)")

        info(f"{len(pending)} new internship(s) to apply to. Starting...\n")

        applied_count  = 0
        external_count = 0
        no_button_count = 0
        error_count    = 0

        for job in pending:
            if applied_count >= MAX_APPLICATIONS:
                warn(f"Hit the MAX_APPLICATIONS limit ({MAX_APPLICATIONS}). Stopping.")
                break

            # Description is now fetched inside apply_to_job after navigating,
            # so we don't do a separate navigation here that leaves the page in
            # a half-ready state before apply_to_job runs.
            label = f"{job['title']} @ {job['company']}"
            info(f"Applying → {label}")

            status = await apply_to_job(page, job)

            if status == "applied":
                ok(f"Applied ✓  {label}")
                tracker.record(job["id"], job["title"], job["company"], "applied")
                applied_count += 1

            elif status in ("submitted_unconfirmed", "dry_run"):
                ok(f"Submitted  {label}")
                tracker.record(job["id"], job["title"], job["company"], status)
                applied_count += 1

            elif status == "already_applied":
                warn(f"Already applied: {label}")
                tracker.record(job["id"], job["title"], job["company"], "already_applied")
                skipped_count += 1

            elif status == "external":
                warn(f"External link — apply manually: {label}")
                tracker.record(job["id"], job["title"], job["company"], "external_link")
                external_count += 1

            elif status == "no_modal":
                # Clicking Apply opened an external tab instead of a modal
                warn(f"External (opened outside Handshake): {label}")
                tracker.record(job["id"], job["title"], job["company"], "external_link")
                external_count += 1

            elif status == "no_apply_button":
                # Likely an external posting whose button text wasn't detected,
                # or a Handshake UI variant we don't handle yet.
                warn(f"No apply button (check manually): {label}")
                tracker.record(job["id"], job["title"], job["company"], "no_apply_button")
                no_button_count += 1

            else:
                err(f"Error ({status}): {label}")
                tracker.record(job["id"], job["title"], job["company"], f"error:{status}")
                error_count += 1

            await asyncio.sleep(DELAY_BETWEEN_APPS)

        print(f"""
{GREEN}{BOLD}══════════════════════ RUN COMPLETE ══════════════════════{RESET}
  ✓  Applied               : {applied_count}
  →  Skipped (already done): {skipped_count}
  ↗  External (manual)     : {external_count}
  ⊘  No apply button       : {no_button_count}
  ✗  Errors                : {error_count}
  ✦  Model used            : Groq / {GROQ_MODEL}
  📄 Full log              : {TRACKER_FILE}
{GREEN}{BOLD}══════════════════════════════════════════════════════════{RESET}
""")
        input("Press ENTER to close the browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())