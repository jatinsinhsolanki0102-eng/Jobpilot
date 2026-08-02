# JobPilot AI — Frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS 4 dashboard for JobPilot AI.

See the root `../README.md` for the full project setup.

## Local dev

```bash
npm install
copy .env.example .env.local   # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm run dev                    # http://localhost:3000
```

## Routes

- `/login`, `/register` — authentication (JWT stored in localStorage)
- `/dashboard` — stats, top matches, recent applications
- `/jobs`, `/jobs/[id]` — AI-ranked job feed + detail with apply & cover letter
- `/applications` — pipeline tracking
- `/resume` — upload + AI parsing
- `/preferences` — role/location/salary/domain filters
