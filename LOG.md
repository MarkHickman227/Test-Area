# ApplyPilot root log

Operational record of changes. Newest first.

## 2026-09-05 — VPS pull succeeded (`cv-apply-1` is live)

Ran as `root@srv832290` from the Hostinger bash console. Backup: `backups/applypilot_20260905T182826Z.sql.gz`. Compose rebuilt; Postgres volume kept. Brief `curl: (56) Connection reset` while the new backend started, then health came up.

Live health after pull:

- `repair_version: cv-apply-1`
- `full_cv_scoring: true`
- `can_send_applications: false` (no SMTP, no Unipile)
- Current CV reparsed: roles EA/SA/Data Architect, Azure, TOGAF 9.1, 20 contract years

Pipeline from the pull script:

- Backfill: processed 80, scored 80, generated 80, applied 0, apply_blocked 80
- Apply: processed 80, applied 0, apply_blocked 80
- Analytics: 211 jobs, DRAFT 80, NEW 71, SUBMITTED 60 (July LinkedIn import), score_ge_60 80, max 100, unscored 113

Checked after pull:

- Solution Architect - Azure Cloud: **15 → 100**, status DRAFT, cover letter written from the full CV
- Enterprise Architect Director / Executive Director EA: 100 DRAFT
- Enterprise Architect - Emergent Technology: still **25 NEW** (not in the first 80)
- Enterprise Account Director: still 15 NEW (old empty-profile score, not yet rescored)

Remaining work on the VPS: run backfill two more times for the 71 NEW / 113 unscored rows. Applications still cannot send until SMTP or Unipile is in `/root/applypilot/config/.env`.

## 2026-09-05 — Windows PowerShell cannot run the VPS pull

From `PS C:\Users\MarkHickman>`, this failed:

```
curl -fsSL https://raw.githubusercontent.com/MarkHickman227/Test-Area/cursor/rescore-full-cv-53b6/scripts/vps-pull-repair.sh | bash
```

PowerShell maps `curl` to `Invoke-WebRequest`. `-fsSL` is not a valid parameter, so it errors: `A parameter cannot be found that matches parameter name 'fsSL'`. Piping to `bash` also does nothing useful on Windows. The script must run **as root on the Hostinger VPS**.

Use Hostinger browser terminal as root, or from PowerShell:

```powershell
ssh root@168.231.114.133 "curl -fsSL https://raw.githubusercontent.com/MarkHickman227/Test-Area/cursor/rescore-full-cv-53b6/scripts/vps-pull-repair.sh | bash"
```

Documented in `docs/vps-deployment.md` and the header of `scripts/vps-pull-repair.sh`.

## 2026-09-05 — Rescore Current CV and real apply path

Branch: `cursor/rescore-full-cv-53b6`  
Health marker: `cv-apply-1`  
Commits: `c5313c6`, `806c549`  
Tests: 78 passed

### Why

Live VPS (`repair_version: cv-backfill-2`) scored jobs against an empty profile (max 25, 0 at 60+). The uploaded Current CV (`CV_current.docx`, 18,120 characters) was on the box and unused. Nothing reached apply. The 60 SUBMITTED rows are a 31 July 2026 LinkedIn import, not sends.

### Scoring review (live jobs vs Current CV)

| Measure | Live VPS | New review |
| --- | --- | --- |
| Jobs | 211 | 211 |
| Score 60+ | 0 | 210 |
| Max score | 25 | 100 |
| Solution Architect - Azure Cloud | 15 (empty profile) | 100 |
| Below 60 | all scored jobs | Enterprise Account Director only (32, sales) |

Last live pipeline run: 2026-09-05 08:00 London. Discovered 8, inserted 5, processed 25, scored 0, generated 0.

### Apply attempt

Ran apply against 150 NEW jobs at 60+.

| Result | Count |
| --- | --- |
| Eligible (NEW, score 60+) | 150 |
| Sent | 0 |
| Blocked: no listing contact email | 150 |
| SMTP / Unipile in this environment | missing |
| VPS SSH | Permission denied |

Public listing URLs are mostly job-board search pages or expired ads. There is no Easy Apply API. Packs were not marked SUBMITTED.

### Code changes

- Score from the full Current CV text, not Anthropic empty-profile reviews.
- Prefer CV label `Current`, then newest row.
- Match cloud / integration / platform / data architect titles.
- Do not say the CV “has no skills” when a listing has no requirements.
- `POST /api/cvs/reparse` and `POST /api/pipeline/backfill?limit=80` rescore existing NEW jobs.
- `POST /api/pipeline/apply` sends 60+ NEW/DRAFT jobs only via SMTP or Unipile.
- Unipile client: `backend/app/services/unipile.py` (email + LinkedIn chat).
- SUBMITTED only after a real send. Otherwise DRAFT + `apply_blocked`.
- Health: `repair_version`, `full_cv_scoring`, `can_send_applications`, `unipile_configured`.
- Dashboard: Rescore from Current CV, Apply to 60+ jobs (`?v=cv7`).
- VPS pull script targets this branch and runs backfill then apply.

### Files

`AGENTS.md`, `backend/app/api/routes.py`, `backend/app/core/config.py`, `backend/app/services/apply.py`, `backend/app/services/cv_parser.py`, `backend/app/services/job_match.py`, `backend/app/services/unipile.py`, `backend/app/services/pipeline.py`, `backend/app/services/scheduler.py`, repositories (local / postgres / supabase), tests, `config/.env.example`, `docs/user-guide.md`, `docs/vps-deployment.md`, `frontend/index.html`, `frontend/extras.js`, `scripts/vps-pull-repair.sh`.

### Still blocked on the VPS

1. Repair is not installed. Live health is still `cv-backfill-2`.
2. No `SMTP_*` or `UNIPILE_*` on the VPS, so apply cannot send after pull.
3. Cloud agent cannot SSH (`root@168.231.114.133`).
4. Windows PowerShell `curl` is `Invoke-WebRequest` and rejects `-fsSL`. Pull must run as **root on the VPS** (Hostinger console / bash), not from a Windows PC.

### VPS install (Hostinger console, bash as root)

Do not paste the bash one-liner into Windows PowerShell.

```bash
curl -fsSL https://raw.githubusercontent.com/MarkHickman227/Test-Area/cursor/rescore-full-cv-53b6/scripts/vps-pull-repair.sh | bash
```

From Windows, SSH it onto the VPS instead:

```powershell
ssh root@168.231.114.133 "curl -fsSL https://raw.githubusercontent.com/MarkHickman227/Test-Area/cursor/rescore-full-cv-53b6/scripts/vps-pull-repair.sh | bash"
```

Expect `repair_version: cv-apply-1`. Do not run `docker compose down -v`.
