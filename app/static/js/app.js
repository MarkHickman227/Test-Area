const session = JSON.parse(localStorage.getItem("linkedin_session") || "null");

if (!session && window.location.pathname === "/dashboard") {
    window.location.href = "/";
}

if (session) {
    const nameEl = document.getElementById("user-name");
    const avatarEl = document.getElementById("user-avatar");
    if (nameEl) nameEl.textContent = session.profile.name;
    if (avatarEl && session.profile.picture) {
        avatarEl.src = session.profile.picture;
        avatarEl.style.display = "block";
    }
}

function toggleCompose() {
    const card = document.getElementById("compose-card");
    card.style.display = card.style.display === "none" ? "block" : "none";
}

function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    setTimeout(() => { toast.classList.remove("show"); }, 3000);
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
        month: "short", day: "numeric", year: "numeric",
        hour: "numeric", minute: "2-digit"
    });
}

function badgeClass(status) {
    if (status === "published") return "badge-published";
    if (status === "failed") return "badge-failed";
    return "badge-pending";
}

async function loadPosts() {
    const container = document.getElementById("posts-list");
    try {
        const res = await fetch("/posts/");
        const posts = await res.json();

        if (!posts.length) {
            container.innerHTML = '<div class="empty-state">No posts yet. Click "+ New Post" to get started.</div>';
            return;
        }

        container.innerHTML = posts.map(post => `
            <div class="post-item">
                <div class="post-content">${escapeHtml(post.content)}</div>
                <div class="post-meta">
                    <span class="badge ${badgeClass(post.status)}">${post.status}</span>
                    <span>${formatDate(post.scheduled_at)}</span>
                </div>
            </div>
        `).join("");
    } catch {
        container.innerHTML = '<div class="empty-state">Could not load posts. Database may be unavailable.</div>';
    }
}

async function schedulePost(e) {
    e.preventDefault();
    const content = document.getElementById("content").value;
    const scheduledAt = document.getElementById("scheduled_at").value;

    if (!session) {
        showToast("Not authenticated", "error");
        return;
    }

    try {
        const res = await fetch("/posts/schedule", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                content,
                scheduled_at: new Date(scheduledAt).toISOString(),
                access_token: session.access_token,
                author_urn: `urn:li:person:${session.profile.sub}`
            })
        });

        if (res.ok) {
            showToast("Post scheduled!");
            document.getElementById("compose-form").reset();
            document.getElementById("compose-card").style.display = "none";
            loadPosts();
        } else {
            const err = await res.json();
            showToast(err.detail || "Failed to schedule post", "error");
        }
    } catch {
        showToast("Failed to schedule post", "error");
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

if (window.location.pathname === "/dashboard") {
    loadPosts();
}
