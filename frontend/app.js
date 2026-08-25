const apiBase = "/api";
let selectedJob = null;
let activeTab = "cover_letter";
let notice = "";
let allJobs = [];
let activeStatus = "";
let activeType = "";

const fields = {
  health: document.querySelector("#health"),
  jobs: document.querySelector("#jobs"),
  detail: document.querySelector("#detail"),
  refresh: document.querySelector("#refresh"),
  filterLabel: document.querySelector("#jobs-filter-label"),
};

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function loadHealth() {
  try {
    const health = await request("/health");
    const dataStoreReady =
      health.supabase_configured ||
      health.database_configured ||
      health.data_store === "local";
    fields.health.textContent = `API ready | Data store ${dataStoreReady ? "on" : "off"}`;
  } catch (error) {
    fields.health.textContent = "API unavailable";
    fields.health.classList.add("error");
  }
}

function updateMetricTiles(jobs) {
  const submitted = jobs.filter((job) => job.status === "SUBMITTED");
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value);
  };
  set("count-total", jobs.length);
  set("count-applied", submitted.length);
  set("count-perm", submitted.filter((job) => job.job_type === "PERM").length);
  set("count-contract", submitted.filter((job) => job.job_type === "CONTRACT").length);
  set("count-new", jobs.filter((job) => job.status === "NEW").length);
  set("count-interview", jobs.filter((job) => job.status === "INTERVIEW").length);
  set("count-offer", jobs.filter((job) => job.status === "OFFER").length);
  set("count-rejected", jobs.filter((job) => job.status === "REJECTED").length);
}

function filterLabel() {
  const parts = [];
  if (activeStatus) parts.push(activeStatus);
  if (activeType) parts.push(activeType);
  return parts.length ? parts.join(" · ") : "All";
}

function filteredJobs() {
  return allJobs.filter((job) => {
    if (activeStatus && job.status !== activeStatus) return false;
    if (activeType && job.job_type !== activeType) return false;
    return true;
  });
}

function renderJobsList() {
  const jobs = filteredJobs();
  if (fields.filterLabel) fields.filterLabel.textContent = filterLabel();
  fields.jobs.innerHTML = jobs.length
    ? jobs.map(renderJobItem).join("")
    : "<p>No jobs match this filter.</p>";
  document.querySelectorAll(".job-item").forEach((node) => {
    node.addEventListener("click", () => loadJob(node.dataset.id));
  });
}

async function loadJobs() {
  fields.jobs.textContent = "Loading jobs...";
  try {
    allJobs = await request("/jobs");
    updateMetricTiles(allJobs);
    renderJobsList();
  } catch (error) {
    fields.jobs.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

function renderJobItem(job) {
  const score = job.score ?? 0;
  const scoreClass = score >= 80 ? "high" : score >= 60 ? "medium" : "low";
  return `
    <article class="job-item" data-id="${job.id}">
      <strong>${escapeHtml(job.title)}</strong>
      <p class="meta">${escapeHtml([job.company, job.location].filter(Boolean).join(" | "))}</p>
      <span class="score ${scoreClass}">${score}</span>
      <span class="meta">${job.job_type || "UNKNOWN"} | ${job.status}${job.agency ? " | Agency" : ""}</span>
    </article>`;
}

async function loadJob(id) {
  selectedJob = await request(`/jobs/${id}`);
  renderDetail();
}

function renderDetail() {
  if (!selectedJob) return;
  const tabValue = tabContent(selectedJob, activeTab);
  fields.detail.innerHTML = `
    <h2>${escapeHtml(selectedJob.title)}</h2>
    <p class="meta">${escapeHtml([selectedJob.company, selectedJob.location, selectedJob.job_type].filter(Boolean).join(" | "))}${selectedJob.source_url ? ` | <a href="${escapeHtml(selectedJob.source_url)}" target="_blank" rel="noopener">Open original</a>` : ""}</p>
    <p><strong>Status:</strong> <span class="status-pill">${selectedJob.status}</span></p>
    ${notice ? `<p class="notice">${escapeHtml(notice)}</p>` : ""}
    <div class="actions">
      ${statusButton("READY", "Mark as Ready")}
      ${statusButton("SUBMITTED", "Mark as Submitted")}
      ${statusButton("INTERVIEW", "Interview")}
      ${statusButton("OFFER", "Offer")}
      ${statusButton("IGNORED", "Ignore")}
    </div>
    <div class="split">
      <section class="panel">
        <h3>Job details</h3>
        <p><strong>Fit:</strong> ${escapeHtml(selectedJob.score_explanation || "Not scored yet.")}</p>
        <h4>Requirements</h4>
        <pre>${escapeHtml(JSON.stringify(selectedJob.parsed_requirements || {}, null, 2))}</pre>
        <h4>Description</h4>
        <p>${escapeHtml(selectedJob.description || "No description stored.")}</p>
      </section>
      <section class="panel">
        <h3>Your application</h3>
        <div class="tabs">
          ${tabButton("cv_summary", "CV / Profile")}
          ${tabButton("cover_letter", "Cover letter")}
          ${tabButton("screening_answers", "Screening Q&A")}
        </div>
        <textarea id="artifact-editor">${escapeHtml(tabValue)}</textarea>
        <div class="actions">
          <button id="save-artifact" type="button">Save edits</button>
          <button id="regenerate" type="button" class="secondary">Regenerate</button>
        </div>
        ${renderRecruiterPanel(selectedJob)}
      </section>
    </div>`;

  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.tab;
      renderDetail();
    });
  });
  document.querySelectorAll("[data-status]").forEach((button) => {
    button.addEventListener("click", () => updateStatus(button.dataset.status));
  });
  document.querySelector("#save-artifact").addEventListener("click", saveArtifact);
  document.querySelector("#regenerate").addEventListener("click", regenerateArtifact);
}

function tabButton(tab, label) {
  return `<button type="button" class="${activeTab === tab ? "" : "secondary"}" data-tab="${tab}">${label}</button>`;
}

function statusButton(status, label) {
  return `<button type="button" class="secondary" data-status="${status}">${label}</button>`;
}

function tabContent(job, tab) {
  if (tab === "cv_summary") return job.tailored_summary || "";
  if (tab === "screening_answers") {
    return (job.screening_answers || [])
      .map((item) => `${item.question}\n${item.answer}`)
      .join("\n\n");
  }
  return job.cover_letter || "";
}

function renderRecruiterPanel(job) {
  if (!job.agency && !job.recruiter_outreach) return "";
  const outreach = job.recruiter_outreach || {};
  return `
    <section class="panel">
      <h3>Recruiter outreach</h3>
      <p><strong>Agency:</strong> ${escapeHtml(outreach.agency_name || "Unknown")}</p>
      <pre>${escapeHtml(outreach.email_body || "No recruiter email drafted yet.")}</pre>
      <pre>${escapeHtml(outreach.linkedin_note || "")}</pre>
    </section>`;
}

async function updateStatus(status) {
  notice = "Updating status...";
  renderDetail();
  selectedJob = await request(`/jobs/${selectedJob.id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  notice = `Status updated to ${status}.`;
  await loadJobs();
  renderDetail();
}

async function saveArtifact() {
  notice = "Saving edits...";
  renderDetail();
  selectedJob = await request(`/jobs/${selectedJob.id}/artifacts`, {
    method: "PATCH",
    body: JSON.stringify({
      artifact: activeTab,
      content: document.querySelector("#artifact-editor").value,
    }),
  });
  notice = "Edits saved.";
  await loadJobs();
  renderDetail();
}

async function regenerateArtifact() {
  notice = "Regenerating artifact...";
  renderDetail();
  selectedJob = await request(`/jobs/${selectedJob.id}/regenerate`, {
    method: "POST",
    body: JSON.stringify({ artifact: activeTab }),
  });
  notice = "Artifact regenerated.";
  await loadJobs();
  renderDetail();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

document.querySelectorAll(".metric-tile").forEach((tile) => {
  tile.addEventListener("click", () => {
    activeStatus = tile.dataset.filterStatus || "";
    activeType = tile.dataset.filterType || "";
    document.querySelectorAll(".metric-tile").forEach((node) => {
      node.classList.toggle("active", node === tile);
    });
    renderJobsList();
  });
});

if (fields.refresh) fields.refresh.addEventListener("click", loadJobs);

document.addEventListener("keydown", (event) => {
  if (!selectedJob || !event.ctrlKey) return;
  if (event.key === "s") {
    event.preventDefault();
    saveArtifact();
  }
  if (event.key === "r") {
    event.preventDefault();
    regenerateArtifact();
  }
  if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
    event.preventDefault();
    const tabs = ["cv_summary", "cover_letter", "screening_answers"];
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const next = (tabs.indexOf(activeTab) + direction + tabs.length) % tabs.length;
    activeTab = tabs[next];
    renderDetail();
  }
});

loadHealth();
loadJobs();
