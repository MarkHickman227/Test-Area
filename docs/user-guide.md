# ApplyPilot User Guide

Version 1.0 | Avalon Creative Ltd | 28/05/2026

ApplyPilot is an AI job application agent that runs on your own server. It finds jobs, scores them against your CV, and generates tailored cover letters, CV summaries, screening answers, and recruiter notes for your review.

ApplyPilot does not submit applications automatically. You stay in control of every submission.

## What ApplyPilot does

| Stage | What happens | Your involvement |
| --- | --- | --- |
| Discover | Searches on your schedule using your titles, locations, salary, and perm/contract preference. | None |
| Enrich | Reads each job description and extracts skills, requirements, seniority, and keywords. | None |
| Score | Gives each job a 0-100 suitability score vs your CV, with strengths and gaps. | None |
| Generate | Writes a tailored cover letter, CV summary, and screening answers. | None |
| Recruiter | Detects agency roles and drafts a personalised recruiter outreach email. | None |
| Review | Surfaces everything in your dashboard for editing and approval. | You review, edit, and submit |

## Setup

### What you need

| Requirement | What it is | Where to get it |
| --- | --- | --- |
| AWS account | Production host for ApplyPilot (ECS Fargate). | `docs/aws-deployment.md` |
| Anthropic API key | Powers AI scoring and writing. | `console.anthropic.com` |
| Supabase account | Hosts your database. | `supabase.com` |
| Unipile account | Optional LinkedIn message sending. | `unipile.com` |
| Docker installed | Runs application containers. | `docs.docker.com/get-docker` |

You can run ApplyPilot on **AWS** (ECS Fargate) plus API usage if you process a moderate number of jobs per day. See `docs/aws-deployment.md`.

### Installation

1. Set up Supabase: create a project, open SQL Editor, run `db/schema.sql`, then run `db/schema_functions.sql`. Copy your Project URL and `service_role` key from Settings > API.
2. Configure your environment: copy `config/.env.example` to `config/.env` and fill in `SUPABASE_URL`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, and optional Telegram settings. For database access, use either `SUPABASE_SERVICE_KEY` or `DATABASE_URL` from the Supabase connection pooler.
3. Deploy with Docker: run `docker compose up --build -d`.
4. Verify the app: open your server IP address or domain and confirm that the dashboard loads.
5. Complete onboarding: register your account, upload CVs, and complete preferences.

### Preferences

| Preference | What to enter | Example |
| --- | --- | --- |
| Target job titles | Exact titles, ideally 2-5. | Enterprise Architect, Solutions Architect |
| Locations | Cities or regions you are willing to work in. | London, Manchester, Remote |
| Salary minimum | Your floor. Jobs below this can be penalised or dropped. | 80000 |
| Salary maximum | Optional ceiling. | 150000 |
| Job types | Permanent, contract, or both. | Both |
| Industries | Preferred sectors, optional. | Financial Services, Legal |
| Seniority level | Target level used for scoring. | Senior / Director |

Upload multiple CV variants with clear labels, such as `EA Focus` or `CTO Track`. ApplyPilot can select the best variant for each job based on keyword overlap.

## Daily use

### Dashboard

Jobs are sorted by suitability score, highest first.

| Column | What it shows |
| --- | --- |
| Score | 0-100 suitability rating. Green is 80+, amber is 60-79, red is below 60. |
| Type | `PERM` or `CONTRACT`. |
| Agency? | Agency-listed roles include recruiter outreach drafts. |
| Status | Pipeline state: `NEW`, `DRAFT`, `READY`, `SUBMITTED`, `INTERVIEW`, `OFFER`, `REJECTED`. |
| Actions | Open, update status, regenerate, or ignore. |

Filter by status, job type, or score range to focus on applications needing attention.

### Application builder

The left panel shows the job description, parsed requirements, and fit explanation. The right panel contains the CV/profile summary, cover letter, and screening Q&A tabs.

Always read the generated content before submitting. The AI tailors the draft to the job, but personal edits usually improve the application.

| Action | When to use it | What it does |
| --- | --- | --- |
| Mark as Ready | You reviewed and approved the application. | Sets status to `READY`. |
| Mark as Submitted | You manually applied. | Sets status to `SUBMITTED` and records the date. |
| Regenerate | You want a different angle. | Calls the AI again and saves a new version. |
| Ignore | The job is irrelevant. | Removes it from the active dashboard view. |

### Recruiter outreach

For agency roles, the recruiter panel shows parsed agency details, a personalised email draft, and an optional LinkedIn connection note.

ApplyPilot does not send emails. Copy the drafted email into your own email client, send it, and then mark it sent so the pipeline stays accurate.

### Analytics

Use pipeline statuses to track total applications, submitted applications, interviews, offers, weekly activity, and response rate.

When a recruiter responds, update the job to `INTERVIEW`, `OFFER`, or `REJECTED` so analytics stay accurate.

## Troubleshooting

| Problem | Likely cause | Fix |
| --- | --- | --- |
| No new jobs appearing | Scheduler not running or preferences too narrow. | Check `docker logs applypilot-backend`; broaden titles or locations. |
| All jobs score low | CV parsing issue or skills mismatch. | Check parsed CV profile and re-upload if needed. |
| Cover letter feels generic | Thin job description. | Edit manually or ignore the role. |
| Agency email is empty | No contact details in the job description. | Search the agency name and contact directly. |
| Docker will not start | Port conflict or missing environment variable. | Run `docker compose logs` and check `config/.env`. |
| Database connection error | Supabase credentials wrong or project paused. | Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`. |

## Quick reference

| Status | Meaning | Next action |
| --- | --- | --- |
| `NEW` | Scored and queued. | Wait for generation. |
| `DRAFT` | Artifacts generated. | Review in Application Builder. |
| `READY` | Reviewed and approved. | Apply manually, then mark submitted. |
| `SUBMITTED` | Applied manually. | Wait for response. |
| `INTERVIEW` | Interview booked. | Prepare and update after outcome. |
| `OFFER` | Offer received. | Close your pipeline. |
| `REJECTED` | Application unsuccessful. | No action needed. |

| Score | Meaning | Recommended action |
| --- | --- | --- |
| 80-100 | Strong match. | Prioritise. |
| 60-79 | Good match with some gaps. | Review gaps and apply if acceptable. |
| 40-59 | Partial match. | Apply only with extra context. |
| Below 40 | Weak match. | Usually ignore. |

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl + S | Save edits to current artifact. |
| Ctrl + R | Regenerate current tab. |
| Ctrl + Right | Next tab. |
| Ctrl + Left | Previous tab. |

ApplyPilot v1.0 | Avalon Creative Ltd | avaloncreativeltd.com | mark.hickman@avaloncreativeltd.com
