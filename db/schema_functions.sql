create or replace function applypilot_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function applypilot_record_status_change()
returns trigger
language plpgsql
as $$
begin
  if old.status is distinct from new.status then
    insert into application_status_history (job_id, from_status, to_status)
    values (new.id, old.status, new.status);

    if new.status = 'SUBMITTED' and old.status is distinct from 'SUBMITTED' then
      new.submitted_at = now();
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists set_jobs_updated_at on jobs;
create trigger set_jobs_updated_at
before update on jobs
for each row execute function applypilot_set_updated_at();

drop trigger if exists set_preferences_updated_at on user_preferences;
create trigger set_preferences_updated_at
before update on user_preferences
for each row execute function applypilot_set_updated_at();

drop trigger if exists set_recruiter_outreach_updated_at on recruiter_outreach;
create trigger set_recruiter_outreach_updated_at
before update on recruiter_outreach
for each row execute function applypilot_set_updated_at();

drop trigger if exists record_jobs_status_change on jobs;
create trigger record_jobs_status_change
before update on jobs
for each row execute function applypilot_record_status_change();
