# Handshake Internship Auto-Applicator

Look, I'll be honest. I had 10+ browser tabs open, a growing list of Handshake postings I kept telling myself I'd apply to "later," and a creeping suspicion that manually submitting the same resume and cover letter over and over again was not a great use of my time.

So I built this instead.

This bot scrapes Handshake for internship postings that match your keywords, scores each one against your profile using an LLM, auto-fills free-text application questions with tailored responses, attaches your resume, and submits — all while you do something better with your time. Every application gets logged to a CSV so it never double-applies across runs.

Is this lazy? Yes. Is it also the most efficient thing I've built this quarter? Also yes.

---

## What it actually does

1. **Scrapes** Handshake for internship postings across your keyword list
2. **Deduplicates** results so the same job doesn't appear twice across different searches
3. **Scores** each job 1–10 against your resume using Groq (LLaMA 3.3 70B) — skips anything below your threshold
4. **Auto-fills** free-text application questions ("Why are you interested?", "Describe your experience") with context-aware answers generated from your profile
5. **Attaches** your resume at every file upload step
6. **Logs** every outcome — applied, skipped, external link, error — to `applied_jobs.csv`

For external applications (the ones that redirect you off Handshake), it can't auto-submit, but it flags them in the CSV so you know which ones still need your attention.

---

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
playwright install chromium
```

**2. Get a free Groq API key**

Head to [console.groq.com](https://console.groq.com), sign up, and grab a key. Free tier. No credit card. Generous limits. Then either paste it into `bot.py`:
```python
GROQ_API_KEY = "gsk_your_key_here"
```
Or export it before running (cleaner option):
```bash
export GROQ_API_KEY="gsk_your_key_here"
```

**3. Add your resume**

Drop your resume PDF into this folder and update the path in `bot.py`:
```python
RESUME_PATH = "your_resume.pdf"
```

**4. Update the candidate profile**

Near the top of `bot.py` there's a `CANDIDATE_PROFILE` block — a plain-text summary of who you are, your experience, projects, and how you work. The LLM uses this to score jobs and write your answers. The more accurate it is, the better the output. Replace it with yours.

**5. Run it**
```bash
python bot.py
```

A Chrome window opens. Log in with your university SSO — the bot can't do this part since every school's SSO is different. Once you're on your Handshake dashboard, come back to the terminal and press `ENTER`. It handles everything from there.

---

## Configuration

All the knobs are at the top of `bot.py`:

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | `"YOUR_API_KEY_HERE"` | Your Groq key |
| `RESUME_PATH` | `"resume.pdf"` | Path to your resume |
| `KEYWORDS` | (see file) | What to search for on Handshake |
| `MIN_RELEVANCE_SCORE` | `6` | Skip jobs scoring below this (out of 10) |
| `MAX_APPLICATIONS` | `25` | Safety cap — stops after this many submissions per run |
| `DELAY_BETWEEN_APPS` | `4` | Seconds between each application |
| `DRY_RUN` | `False` | Set to `True` to scrape and score without submitting |
| `TRACKER_FILE` | `"applied_jobs.csv"` | Where the log lives |

**First time running?** Set `DRY_RUN = True`. It'll go through the full scrape and scoring pipeline, print everything it would apply to, and stop before submitting anything. Good way to check that your profile and keywords are pulling the right jobs before you start firing off applications.

---

## The output CSV

Every job the bot encounters — applied, skipped, scored too low, external link, errored — gets a row in `applied_jobs.csv`:

| Column | Description |
|---|---|
| `job_id` | Handshake's internal job ID |
| `title` | Job title |
| `company` | Company name |
| `score` | Relevance score out of 10 |
| `status` | `applied`, `submitted_unconfirmed`, `low_score`, `external_link`, `already_applied`, `error:*` |
| `applied_at` | Timestamp |

Re-run the bot anytime — it reads the CSV first and skips anything already in there.

---

## A note on the cover letters

The bot detects textareas in the application flow that look like qualitative questions and auto-fills them using your `CANDIDATE_PROFILE` + the job description. It's not copy-pasting a template — it generates a fresh 2–4 sentence response per question, per job.

It works best when your `CANDIDATE_PROFILE` is detailed and honest. Generic input → generic output. The more context you give it about your actual experience and how you think, the more the answers will actually sound like you.

---

## Troubleshooting

**"Resume not found"** — Double-check that `RESUME_PATH` matches your filename exactly, including the extension.

**Bot freezes or can't find the Apply button** — Handshake updates their frontend occasionally, which can break the CSS selectors. Open `bot.py`, find `apply_to_job()`, and update the selectors to match what you see in your browser's dev tools.

**Submitted but status is `submitted_unconfirmed`** — The bot couldn't detect a success message after submitting. Check your Handshake "Applications" tab to verify it went through. This usually means it did — Handshake's confirmation UI just varies by posting.

**Groq rate limit hit** — The free tier has a daily token limit. If you're running large batches, spread them across multiple sessions or bump `DELAY_BETWEEN_APPS`.

---

## Limitations worth knowing

This isn't magic. Handshake's DOM changes, some postings have non-standard application flows, and the LLM occasionally produces cover letter answers you'd want to edit before a real recruiter reads them. I'd recommend spot-checking the `applied_jobs.csv` after each run and reviewing a few of the auto-generated answers before you scale up to a large batch.

It's a tool that removes the tedious parts. The judgment still has to be yours.

---

*Built by [Piqim](https://piqim.com) — because manually applying to 30 internships is not a personality trait I'm willing to develop.*