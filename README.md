# Handshake Internship Auto-Applicator (UCSD)

Look, I'll be honest. I had 10+ browser tabs open, a growing list of Handshake postings I kept telling myself I'd apply to "later," and a creeping suspicion that manually submitting the same resume and cover letter over and over again was not a great use of my time.

So I built this instead.

This bot is built specifically for **UC San Diego students** on [ucsd.joinhandshake.com](https://ucsd.joinhandshake.com). It scrapes Handshake for internship postings across your keyword list — paginating through multiple pages per keyword — deduplicates everything, and applies. Groq (LLaMA 3.3 70B) only kicks in when an application actually needs it: to write a cover letter or answer a free-text question. Every outcome gets logged to a CSV so it never double-applies across runs.

Is this lazy? Yes. Is it also the most efficient thing I've built this semester? Also yes.

---

## What it actually does

1. **Scrapes** Handshake for internship postings across your keyword list, paginating through up to `MAX_PAGES` pages per keyword
2. **Deduplicates** results — the same posting can appear across multiple keywords and pages, it only gets applied to once
3. **Applies** to each new job automatically — clicks the Apply button, handles the modal, submits
4. **Generates cover letters** on the fly using Groq when an application asks for one — fresh, tailored to the specific job
5. **Auto-fills free-text questions** ("Why are you interested?", "Describe your experience") using your `CANDIDATE_PROFILE` + the job description
6. **Logs** every outcome — applied, already applied, external link, error — to `applied_jobs.csv`

Your resume is already attached from your Handshake profile — no upload needed. For external applications (the ones that redirect off Handshake), the bot flags them in the CSV for manual follow-up.

---

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
playwright install chromium
```

**2. Get a free Groq API key**

Head to [console.groq.com](https://console.groq.com), sign up, and grab a key. Free tier, no credit card. Add it to your `.env` file (copy `.env.example` to get started):
```
GROQ_API_KEY=gsk_your_key_here
```
Or export it before running:
```bash
export GROQ_API_KEY="gsk_your_key_here"
```

**3. Update the candidate profile**

Near the top of `bot.py` there's a `CANDIDATE_PROFILE` block — a plain-text summary of who you are, your skills, experience, and projects. Groq reads this when writing cover letters and question answers. The more honest and detailed it is, the better the output sounds. Replace it with your own if you're not me.

**4. Make sure your Handshake profile has a default resume set**

The bot doesn't upload a resume file — it relies on whatever's already set as your default document in your Handshake profile. Go to your profile → Documents and confirm one is set before running.

**5. Run it**
```bash
python bot.py
```

A Chrome window opens pointing to `ucsd.joinhandshake.com`. Log in with your **UCSD SSO** and complete **DUO authentication**. The bot watches for you automatically — no need to press ENTER. Once it detects you're on the dashboard, it takes over.

---

## Configuration

All the knobs are at the top of `bot.py`:

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | env var | Your Groq key — set via `.env` or `export` |
| `KEYWORDS` | (see file) | What to search for on Handshake |
| `MAX_PAGES` | `5` | Pages to scrape per keyword (25 results each) |
| `MAX_APPLICATIONS` | `25` | Safety cap — stops after this many submissions per run |
| `DELAY_BETWEEN_APPS` | `4` | Seconds between each application |
| `DRY_RUN` | `False` | Set to `True` to scrape without submitting |
| `TRACKER_FILE` | `"applied_jobs.csv"` | Where the log lives |

**On pagination:** with the defaults, the bot can scrape up to 12 keywords × 5 pages × 25 results = 1,500 postings per run before deduplication. In practice it'll be far fewer due to keyword overlap. Crank `MAX_PAGES` up if you want wider coverage, or lower it for faster runs.

**First time running?** Set `DRY_RUN = True`. It'll scrape everything and print what it finds, but won't submit anything. Good way to sanity-check your keywords before you start firing off applications.

---

## The output CSV

Every job the bot encounters gets a row in `applied_jobs.csv`:

| Column | Description |
|---|---|
| `job_id` | Handshake's internal job ID |
| `title` | Job title |
| `company` | Company name |
| `status` | `applied`, `submitted_unconfirmed`, `already_applied`, `external_link`, `error:*` |
| `applied_at` | Timestamp |

Re-run the bot anytime — it reads the CSV on startup and skips anything already logged.

---

## A note on Groq and token usage

Groq is only called when the application modal actually needs something written — a cover letter field or a free-text question. If a job has neither, no API call is made at all. This keeps usage well within the free tier across a normal run.

The `CANDIDATE_PROFILE` is what Groq draws from when writing. Generic input → generic output. The more specific and honest the profile, the more the answers sound like you and less like a ChatGPT hallucination of a computer science student.

---

## Troubleshooting

**Bot is stuck on the login check** — The bot polls every 10 seconds waiting for a logged-in Handshake tab to appear. If it's been more than a minute, make sure you fully completed DUO and can see the Handshake dashboard in the browser window. It detects login automatically — no ENTER needed.

**Bot finds 0 jobs** — Handshake occasionally updates their frontend, which can break the card selector (`data-hook^="job-result-card | "`). Open devtools on the job search page, inspect a card, and check if the data-hook format has changed. Let me know and I'll update the selector.

**"no_apply_button" in the CSV** — The Apply button selector (`button[aria-label^='Apply']`) didn't match. Handshake sometimes renders the button differently depending on your eligibility for a job (e.g. graduation year mismatch). Check the job manually to see what the button actually looks like.

**"submitted_unconfirmed" in the CSV** — The bot submitted but couldn't find a success indicator. Check your Handshake Applications tab to verify. This usually means it went through — Handshake's confirmation UI is inconsistent across postings.

**Cover letter field not detected** — The bot looks for a fieldset with "cover letter" in its legend text. If a job uses different label text, it'll be skipped. Not a dealbreaker — the application still submits, just without the cover letter attached.

---

## Limitations worth knowing

This is built and tested on `ucsd.joinhandshake.com`. If you're at a different university, update `HANDSHAKE_BASE_URL` in `bot.py` to your school's subdomain (e.g. `ucla.joinhandshake.com`) — that's the only change needed.

This isn't magic. Handshake's DOM changes, some postings have non-standard flows, and the bot will occasionally log an error on a job that it just couldn't navigate cleanly. Spot-check `applied_jobs.csv` after a run to see what went through and what needs a manual follow-up.

It removes the tedious parts. The judgment still has to be yours.

---

*Built by [Piqim](https://piqim.com) — because manually applying to 30 internships is not a personality trait I'm willing to develop.*