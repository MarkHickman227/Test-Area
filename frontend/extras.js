const views = ["dashboard", "analytics", "cvs"];
let currentView = "dashboard";

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

function switchView(view) {
  currentView = view;
  views.forEach((v) => {
    const el = document.getElementById(`view-${v}`);
    if (el) el.style.display = v === view ? "" : "none";
  });
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  if (view === "analytics") loadAnalytics();
  if (view === "cvs") loadCvs();
}

async function loadAnalytics() {
  const container = document.getElementById("analytics-content");
  try {
    const data = await request("/analytics");
    const counts = data.status_counts || {};
    const rows = Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .map(([status, count]) => `<tr><td>${escapeHtml(status)}</td><td>${count}</td></tr>`)
      .join("");
    const typeCounts = data.job_type_counts || {};
    const submittedByType = data.submitted_by_type || {};
    const typeRows = Object.entries(typeCounts)
      .sort(([, a], [, b]) => b - a)
      .map(([jobType, count]) => `<tr><td>${escapeHtml(jobType)}</td><td>${count}</td></tr>`)
      .join("");
    const submittedTypeRows = Object.entries(submittedByType)
      .sort(([, a], [, b]) => b - a)
      .map(([jobType, count]) => `<tr><td>${escapeHtml(jobType)}</td><td>${count}</td></tr>`)
      .join("") || `<tr><td colspan="2">No submitted applications yet.</td></tr>`;
    container.innerHTML = `
      <div class="analytics-grid">
        <div class="stat-card"><span class="stat-number">${data.total_jobs}</span><span class="stat-label">Total jobs</span></div>
        <div class="stat-card"><span class="stat-number">${data.submitted}</span><span class="stat-label">Submitted</span></div>
        <div class="stat-card"><span class="stat-number">${data.interviews}</span><span class="stat-label">Interviews</span></div>
        <div class="stat-card"><span class="stat-number">${data.offers}</span><span class="stat-label">Offers</span></div>
      </div>
      <h3>Job type mix (all jobs)</h3>
      <table class="analytics-table"><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>${typeRows}</tbody></table>
      <h3>Applied / submitted by type</h3>
      <table class="analytics-table"><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>${submittedTypeRows}</tbody></table>
      <h3>Status breakdown</h3>
      <table class="analytics-table"><thead><tr><th>Status</th><th>Count</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (error) {
    container.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

async function loadCvs() {
  const container = document.getElementById("cv-list");
  try {
    const cvs = await request("/cvs");
    if (!cvs.length) {
      container.innerHTML = "<p>No CVs uploaded yet. Add one below.</p>";
      return;
    }
    container.innerHTML = cvs.map((cv) => {
      const skillCount = (cv.parsed_profile && cv.parsed_profile.skills && cv.parsed_profile.skills.length) || 0;
      const skills = skillCount ? ` | ${skillCount} skills parsed` : " | not parsed";
      return `
      <article class="cv-item card">
        <strong>${escapeHtml(cv.label)}</strong>
        <span class="meta">${escapeHtml(cv.file_name)} | ${cv.raw_text ? cv.raw_text.length + " chars" : "empty"}${skills}</span>
        <button class="secondary" onclick="deleteCv('${cv.id}')">Delete</button>
      </article>
    `;
    }).join("");
  } catch (error) {
    container.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

async function deleteCv(id) {
  await fetch(`${apiBase}/cvs/${id}`, { method: "DELETE" });
  loadCvs();
}

document.getElementById("cv-upload").addEventListener("click", async () => {
  const label = document.getElementById("cv-label").value.trim();
  const fileName = document.getElementById("cv-filename").value.trim();
  const rawText = document.getElementById("cv-text").value.trim();
  if (!label || !fileName || !rawText) return;

  try {
    await request("/cvs", {
      method: "POST",
      body: JSON.stringify({ label, file_name: fileName, raw_text: rawText }),
    });
    document.getElementById("cv-label").value = "";
    document.getElementById("cv-filename").value = "";
    document.getElementById("cv-text").value = "";
    loadCvs();
  } catch (error) {
    alert(`Failed to upload CV: ${error.message}`);
  }
});
