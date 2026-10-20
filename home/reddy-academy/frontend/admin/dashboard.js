"use strict";

(() => {
  const tbody = document.querySelector("#enquiries-body");
  if (!tbody) return;

  const pageSize = 25;
  const filters = document.querySelector("#filter-form");
  const errorBox = document.querySelector("#dashboard-error");
  const dialog = document.querySelector("#detail-dialog");
  let currentPage = 1;
  let totalItems = 0;
  let csrfToken = "";
  let toastTimer;

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const prettyDate = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
  const money = (value, status) => value === null || value === undefined
    ? `<span class="cell-subtle">${escapeHtml(status === "unavailable" ? "Not available" : "—")}</span>`
    : `₹${Number(value).toLocaleString("en-IN")}`;

  const queryParameters = () => {
    const params = new URLSearchParams();
    const values = new FormData(filters);
    for (const [key, value] of values.entries()) {
      if (String(value).trim()) params.set(key, String(value).trim());
    }
    return params;
  };

  const request = async (url, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (options.method && options.method !== "GET" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
    const response = await fetch(url, { ...options, headers, credentials: "include" });
    if (response.status === 401) {
      window.location.replace("/admin/login");
      throw new Error("Your admin session has expired.");
    }
    if (!response.ok) {
      let detail = "The request could not be completed.";
      try { detail = (await response.json()).detail || detail; } catch { /* Keep the safe fallback. */ }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return response;
  };

  const announce = (message) => {
    const toast = document.querySelector("#toast");
    toast.textContent = message;
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 3500);
  };

  const showError = (message) => {
    errorBox.textContent = message;
  };

  const loadSession = async () => {
    const response = await request("/api/admin/me");
    const session = await response.json();
    csrfToken = session.csrf_token;
    document.querySelector("#admin-email").textContent = session.email;
  };

  const loadStats = async () => {
    const response = await request("/api/admin/dashboard");
    const data = await response.json();
    document.querySelector("#stat-total").textContent = data.total_enquiries;
    document.querySelector("#stat-new").textContent = data.new_enquiries;
    document.querySelector("#stat-contacted").textContent = data.contacted_parents;
    document.querySelector("#stat-follow-up").textContent = data.follow_up_required;
    document.querySelector("#stat-converted").textContent = data.converted_enquiries;
    document.querySelector("#stat-students").textContent = data.total_students;
  };

  const renderRows = (items) => {
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No saved enquiries match these filters.</td></tr>';
      return;
    }
    tbody.innerHTML = items.map((item) => {
      const academic = item.classes.map((grade, index) => {
        const subject = item.subjects[index];
        return `<div>${escapeHtml(grade)}${subject ? `<span class="cell-subtle"> · ${escapeHtml(subject)}</span>` : ""}</div>`;
      }).join("");
      return `<tr>
        <td class="parent-cell"><strong>${escapeHtml(item.parent_name)}</strong><a href="tel:${escapeHtml(item.phone)}">${escapeHtml(item.phone)}</a><div class="cell-subtle">${escapeHtml(item.email || "")}</div></td>
        <td>${item.students_in_home}</td>
        <td>${academic || "—"}</td>
        <td>${money(item.combined_monthly_fee, item.fee_status)}</td>
        <td>${escapeHtml(prettyDate(item.submitted_at))}</td>
        <td><span class="status-pill" data-status="${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></td>
        <td><button class="details-button" type="button" data-view="${escapeHtml(item.id)}">View details</button></td>
      </tr>`;
    }).join("");
  };

  const loadEnquiries = async () => {
    showError("");
    const params = queryParameters();
    params.set("page", String(currentPage));
    params.set("page_size", String(pageSize));
    const response = await request(`/api/admin/enquiries?${params}`);
    const data = await response.json();
    totalItems = data.total;
    renderRows(data.items);
    document.querySelector("#result-count").textContent = `${data.total} ${data.total === 1 ? "enquiry" : "enquiries"}`;
    const start = data.total ? (currentPage - 1) * pageSize + 1 : 0;
    const end = Math.min(currentPage * pageSize, data.total);
    document.querySelector("#page-summary").textContent = `Showing ${start}–${end} of ${data.total}`;
    document.querySelector("#page-number").textContent = `${currentPage}`;
    document.querySelector("#previous-page").disabled = currentPage <= 1;
    document.querySelector("#next-page").disabled = currentPage * pageSize >= data.total;
    document.querySelector("#last-updated").textContent = `Updated ${new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date())}`;
  };

  const detailItem = (label, value, href) => `<div class="detail-item"><small>${escapeHtml(label)}</small>${href ? `<a href="${escapeHtml(href)}">${escapeHtml(value || "—")}</a>` : `<span>${escapeHtml(value || "—")}</span>`}</div>`;
  const optionsForStatus = (selected) => ["New", "Contacted", "Follow-up Required", "Converted", "Closed"]
    .map((status) => `<option${status === selected ? " selected" : ""}>${status}</option>`).join("");

  const renderDetail = (enquiry) => {
    document.querySelector("#detail-heading").textContent = enquiry.reference;
    const students = enquiry.students.map((student) => `
      <article class="detail-student"><h4>Student ${student.student_number}${student.student_name ? ` · ${escapeHtml(student.student_name)}` : ""}</h4>
        <div class="detail-grid">
          ${detailItem("Class or grade", student.class_or_grade)}
          ${detailItem("Education board", student.board)}
          ${detailItem("Academic stream", student.academic_stream)}
          ${detailItem("Subjects", student.subjects)}
          ${detailItem("Tuition type", student.tuition_type)}
          ${detailItem("Individual estimated monthly fee", money(student.individual_monthly_fee, student.fee_status))}
        </div>
      </article>`).join("");
    const notes = enquiry.notes.length
      ? enquiry.notes.map((note) => `<div class="note-entry"><time>${escapeHtml(prettyDate(note.created_at))}</time>${escapeHtml(note.note)}</div>`).join("")
      : '<p class="cell-subtle">No internal notes yet.</p>';

    document.querySelector("#detail-content").innerHTML = `
      <section class="detail-section"><h3>Parent &amp; submission</h3><div class="detail-grid">
        ${detailItem("Parent name", enquiry.parent_name)}
        ${detailItem("Phone", enquiry.phone, `tel:${enquiry.phone}`)}
        ${detailItem("Email", enquiry.email, enquiry.email ? `mailto:${enquiry.email}` : "")}
        ${detailItem("Preferred contact method", enquiry.preferred_contact_method)}
        ${detailItem("Enquiry reference", enquiry.reference)}
        ${detailItem("Submitted", prettyDate(enquiry.submitted_at))}
        ${detailItem("Number of students", enquiry.students_in_home)}
        ${detailItem("Status", enquiry.status)}
      </div></section>
      <section class="detail-section"><h3>Students &amp; academic requirements</h3>${students}</section>
      <section class="detail-section"><h3>Tutor preferences</h3><div class="detail-grid">
        ${detailItem("Tutor gender", enquiry.tutor_gender_preference)}
        ${detailItem("Preferred qualification", enquiry.preferred_qualification)}
        ${detailItem("Teaching language", enquiry.teaching_language)}
        ${detailItem("Preferred time", enquiry.preferred_time)}
        ${detailItem("Classes per week", enquiry.classes_per_week)}
        ${detailItem("Session duration", enquiry.session_duration)}
      </div></section>
      <section class="detail-section"><h3>Location &amp; message</h3><div class="detail-grid">
        ${detailItem("City", enquiry.city)}
        ${detailItem("Locality", enquiry.locality)}
        ${detailItem("PIN code", enquiry.pin_code)}
        ${detailItem("Address", enquiry.address)}
        ${detailItem("Parent's message", enquiry.additional_requirements)}
        ${detailItem("Consent recorded", enquiry.consent ? `Yes · ${prettyDate(enquiry.consent_timestamp)}` : "No")}
      </div></section>
      <section class="detail-section"><h3>Estimated fee</h3><div class="detail-grid">
        ${detailItem("Individual fee subtotal", money(enquiry.individual_fee_subtotal, enquiry.fee_status))}
        ${detailItem("Combined monthly fee", money(enquiry.combined_monthly_fee, enquiry.fee_status))}
        ${detailItem("Fee calculation status", enquiry.fee_status)}
      </div></section>
      <section class="detail-section"><h3>Update enquiry status</h3>
        <div class="status-editor"><label for="detail-status">Status</label><select id="detail-status">${optionsForStatus(enquiry.status)}</select><button id="save-status" class="button button-primary" type="button" data-id="${escapeHtml(enquiry.id)}">Save status</button><button id="delete-enquiry" class="button delete-button" type="button" data-id="${escapeHtml(enquiry.id)}">Delete enquiry</button></div>
      </section>
      <section class="detail-section"><h3>Private internal notes</h3><form id="note-form" class="note-form" data-id="${escapeHtml(enquiry.id)}">
        <label class="sr-only" for="internal-note">Add private internal note</label><textarea id="internal-note" maxlength="2000" required placeholder="Add a note visible only to admins"></textarea>
        <button class="button button-outline" type="submit">Add note</button>
      </form><div id="note-list" class="note-list">${notes}</div></section>`;
  };

  const openDetail = async (id) => {
    showError("");
    try {
      const response = await request(`/api/admin/enquiries/${encodeURIComponent(id)}`);
      renderDetail(await response.json());
      dialog.showModal();
    } catch (reason) {
      showError(reason instanceof Error ? reason.message : "Could not load enquiry details.");
    }
  };

  tbody.addEventListener("click", (event) => {
    const button = event.target.closest("[data-view]");
    if (button) openDetail(button.dataset.view);
  });

  document.querySelector("#detail-content").addEventListener("click", async (event) => {
    const saveButton = event.target.closest("#save-status");
    if (saveButton) {
      saveButton.disabled = true;
      try {
        const response = await request(`/api/admin/enquiries/${encodeURIComponent(saveButton.dataset.id)}/status`, {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: document.querySelector("#detail-status").value })
        });
        await response.json();
        await refreshAll();
        await openDetail(saveButton.dataset.id);
        announce("Enquiry status updated.");
      } catch (reason) {
        announce(reason instanceof Error ? reason.message : "Status update failed.");
      } finally {
        saveButton.disabled = false;
      }
    }

    const deleteButton = event.target.closest("#delete-enquiry");
    if (deleteButton) {
      if (!window.confirm("Permanently delete this enquiry and all associated students and internal notes? This cannot be undone.")) return;
      deleteButton.disabled = true;
      try {
        await request(`/api/admin/enquiries/${encodeURIComponent(deleteButton.dataset.id)}`, { method: "DELETE" });
        dialog.close();
        await refreshAll();
        announce("Enquiry deleted.");
      } catch (reason) {
        announce(reason instanceof Error ? reason.message : "Could not delete the enquiry.");
        deleteButton.disabled = false;
      }
    }
  });

  document.querySelector("#detail-content").addEventListener("submit", async (event) => {
    if (event.target.id !== "note-form") return;
    event.preventDefault();
    const textarea = event.target.querySelector("textarea");
    const submit = event.target.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const response = await request(`/api/admin/enquiries/${encodeURIComponent(event.target.dataset.id)}/notes`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: textarea.value })
      });
      const note = await response.json();
      const list = document.querySelector("#note-list");
      if (list.querySelector(".cell-subtle")) list.innerHTML = "";
      list.insertAdjacentHTML("afterbegin", `<div class="note-entry"><time>${escapeHtml(prettyDate(note.created_at))}</time>${escapeHtml(note.note)}</div>`);
      textarea.value = "";
      announce("Private note added.");
    } catch (reason) {
      announce(reason instanceof Error ? reason.message : "Could not save note.");
    } finally {
      submit.disabled = false;
    }
  });

  const refreshAll = async () => {
    await Promise.all([loadStats(), loadEnquiries()]);
  };

  filters.addEventListener("submit", async (event) => {
    event.preventDefault();
    currentPage = 1;
    try { await loadEnquiries(); } catch (reason) { showError(reason.message); }
  });
  document.querySelector("#clear-filters").addEventListener("click", async () => {
    filters.reset();
    currentPage = 1;
    try { await loadEnquiries(); } catch (reason) { showError(reason.message); }
  });
  document.querySelector("#previous-page").addEventListener("click", async () => {
    if (currentPage > 1) currentPage -= 1;
    try { await loadEnquiries(); } catch (reason) { showError(reason.message); }
  });
  document.querySelector("#next-page").addEventListener("click", async () => {
    if (currentPage * pageSize < totalItems) currentPage += 1;
    try { await loadEnquiries(); } catch (reason) { showError(reason.message); }
  });
  document.querySelector("#export-button").addEventListener("click", async () => {
    try {
      const params = queryParameters();
      const response = await request(`/api/admin/enquiries/export.csv?${params}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "reddy-academy-enquiries.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      showError(reason instanceof Error ? reason.message : "CSV export failed.");
    }
  });
  document.querySelector("#logout-button").addEventListener("click", async () => {
    try {
      await request("/api/admin/logout", { method: "POST" });
      window.location.replace("/admin/login");
    } catch (reason) {
      showError(reason instanceof Error ? reason.message : "Logout failed.");
    }
  });
  document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());

  const start = async () => {
    try {
      await loadSession();
      await refreshAll();
      window.setInterval(() => refreshAll().catch((reason) => showError(reason.message)), 60_000);
    } catch (reason) {
      if (!errorBox.textContent) showError(reason instanceof Error ? reason.message : "Could not load dashboard data.");
    }
  };
  start();
})();
