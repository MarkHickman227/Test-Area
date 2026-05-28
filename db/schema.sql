create extension if not exists pgcrypto;

create table if not exists user_preferences (
  id uuid primary key default gen_random_uuid(),
  target_titles text[] not null,
  locations text[] not null,
  salary_min integer check (salary_min is null or salary_min >= 0),
  salary_max integer check (salary_max is null or salary_max >= 0),
  job_types text[] not null default '{}',
  industries text[] not null default '{}',
  seniority_level text,
  updated_at timestamptz not null default now()
);

create table if not exists cvs (
  id uuid primary key default gen_random_uuid(),
  label text not null,
  file_name text not null,
  raw_text text not null,
  parsed_profile jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  source text not null default 'indeed',
  source_url text not null unique,
  title text not null,
  company text,
  location text,
  description text,
  salary_min integer check (salary_min is null or salary_min >= 0),
  salary_max integer check (salary_max is null or salary_max >= 0),
  job_type text check (job_type in ('PERM', 'CONTRACT')),
  agency boolean not null default false,
  parsed_requirements jsonb not null default '{}'::jsonb,
  score integer check (score is null or score between 0 and 100),
  score_explanation text,
  selected_cv_id uuid references cvs(id) on delete set null,
  status text not null default 'NEW'
    check (status in ('NEW', 'DRAFT', 'READY', 'SUBMITTED', 'INTERVIEW', 'OFFER', 'REJECTED', 'IGNORED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  submitted_at timestamptz
);

create table if not exists application_artifacts (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references jobs(id) on delete cascade,
  artifact_type text not null
    check (artifact_type in ('cv_summary', 'cover_letter', 'screening_answers', 'recruiter_outreach')),
  cv_label text,
  version integer not null default 1 check (version > 0),
  content jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists recruiter_outreach (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null unique references jobs(id) on delete cascade,
  agency_name text,
  contact_name text,
  contact_email text,
  email_body text,
  linkedin_note text,
  email_sent boolean not null default false,
  linkedin_sent boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists application_status_history (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references jobs(id) on delete cascade,
  from_status text,
  to_status text not null,
  changed_at timestamptz not null default now()
);

create index if not exists jobs_status_score_idx on jobs (status, score desc);
create index if not exists jobs_type_idx on jobs (job_type);
create index if not exists artifacts_job_type_idx on application_artifacts (job_id, artifact_type, created_at desc);
