# JobPilot AI

Your personal AI career agent. It continuously searches for internships and jobs, analyzes them against your resume and preferences, ranks the best opportunities, generates personalized application materials, and tracks your applications.

> Status: **Phase 2** — resume parsing, preferences, job search, AI match scoring, applications, a dashboard, live Internshala scraping, a Telegram notification agent with scheduled scans, analytics, and saved jobs. Phase 3 modules (interviews, skill-gap, learning roadmap) remain.

## Architecture

```
                    User
                     |
                     v
         Next.js Web Dashboard  (frontend/)
                     |
        ---------------- API Gateway ----------------
                     |
          FastAPI Backend Services  (backend/)
                     |
  +----------+----------+----------+-------------+
  |          |          |          |             |
Resume    AI Engine  Browser     Notification  Analytics
Parser      |        Agent        System       Engine
            |      (Playwright,
            v         future)
      Matching Engine
            |
            v
      PostgreSQL / SQLite
```

- **Frontend** — Next.js 16 (App Router), TypeScript, Tailwind CSS 4
- **Backend** — FastAPI, SQLAlchemy 2, Pydantic v2, APScheduler
- **Database** — PostgreSQL in production; SQLite for zero-setup local dev (one env var to switch)
- **AI** — Groq (resume parsing, match scoring, cover letters) with deterministic heuristic fallback when no API key is set
- **Automation** — Playwright (Internshala scraping) + a Telegram bot for push alerts, commands, daily summaries, and weekly reports
- **Compliance** — always keeps the user in control of submissions; never auto-applies

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows
pip install -r requirements.txt
copy .env.example .env            # set GROQ_API_KEY (optional), DATABASE_URL (optional)
python -m app.seed                # create tables + seed sample jobs
uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local      # set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm run dev                       # http://localhost:3000
```

Create an account at http://localhost:3000/register, upload a resume, set preferences, and browse ranked jobs.

## PostgreSQL (production-style local)

```bash
createdb -U postgres jobpilot
# backend/.env:
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/jobpilot
```

## Modules

| # | Module | Status |
|---|--------|--------|
| 1 | Authentication (JWT) | ✅ Phase 1 |
| 2 | Resume Intelligence Engine | ✅ Phase 1 |
| 3 | User Preference Engine | ✅ Phase 1 |
| 4 | Browser Automation Agent | ✅ Phase 2 (Playwright) |
| 5 | Job Extraction Engine | ✅ Internshala, LinkedIn, Unstop, Adzuna, Remotive (live); Naukri/Wellfound via session cookies |
| 6 | AI Matching Engine | ✅ Phase 1 |
| 7 | Recommendation Engine | ✅ Phase 1 (ranking) |
| 8 | Cover Letter Generator | ✅ Groq + heuristic fallback |
| 9 | Application Manager | ✅ Phase 1 |
| 10 | Telegram Notification Agent | ✅ Phase 2 (scheduler, alerts, commands, daily/weekly) |
| 11 | Analytics Dashboard | ✅ Phase 2 (scans, reports, skills, funnel) |
| 12 | AI Career Assistant | 🔜 Phase 3 (interview prep, skill-gap, roadmap) |

## Telegram agent setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and set `TELEGRAM_BOT_TOKEN` (and optionally `TELEGRAM_BOT_USERNAME`) in `backend/.env`, then restart the backend.
2. In the web app open **Telegram Agent**, click **Generate link code**, and send `/link <code>` to your bot.
3. Set your scan interval, minimum match score, keywords, and toggle daily/weekly reports.
4. Use `/jobs`, `/top`, `/search <keyword>`, `/saved`, `/status` inside the bot anytime.

## Compliance note

Some platforms prohibit automated scraping/auto-application in their ToS. This project uses official APIs where available, keeps the user in control of submissions, never stores platform passwords, and respects robots.txt and rate limits.

## Roadmap

- **Phase 1** — Resume parsing, preferences, job search, match scoring, dashboard
- **Phase 2 (this)** — Internshala scraping, AI cover letters, Telegram agent, analytics, saved jobs
- **Phase 3** — Interview prep, resume optimization, skill-gap analysis, learning roadmap
- **Phase 4** — Chrome extension, mobile app, recruiter dashboard, salary negotiation assistant
