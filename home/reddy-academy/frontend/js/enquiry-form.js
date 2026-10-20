"use strict";

(() => {
  const form = document.querySelector("#enquiry-form");
  if (!form) return;

  const maxStudents = 10;
  const classOptions = [
    ["nursery", "Nursery"], ["lkg", "LKG"], ["ukg", "UKG"],
    ...Array.from({ length: 12 }, (_, index) => [`class-${index + 1}`, `Class ${index + 1}`]),
    ["intermediate-1", "Intermediate 1st Year"],
    ["intermediate-2", "Intermediate 2nd Year"],
    ["other", "Other or equivalent academic level"]
  ];
  const boardOptions = [
    ["", "Select a board"], ["cbse", "CBSE"], ["icse", "ICSE"],
    ["state-board", "State Board"], ["ib", "IB"], ["igcse", "IGCSE"], ["other", "Other"]
  ];
  const steps = [...form.querySelectorAll(".form-step")];
  const studentList = document.querySelector("#students-list");
  const progressFill = document.querySelector("#progress-fill");
  const stepLabel = document.querySelector("#step-label");
  const stepName = document.querySelector("#step-name");
  const studentCountRadios = [...form.querySelectorAll('input[name="studentCount"]')];
  const errorMessages = {
    1: form.querySelector('[data-step="1"] .form-error'),
    2: form.querySelector('[data-step="2"] .form-error'),
    3: form.querySelector('[data-step="3"] .form-error'),
    4: form.querySelector('[data-step="4"] .form-error')
  };
  const stepNames = ["Parent details", "Student details", "Preferences & location", "Review"];
  let currentStep = 1;
  let nextStudentId = 3;
  let lastSubmissionPayload = "";
  let submissionIdempotencyKey = "";

  // ── Fee estimation state ──
  let feeEstimateData = null;
  let feeEstimateError = null;
  let feeEstimatePending = false;
  let feeDebounceTimer = null;

  const escapeHtml = (value) => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const fmt = (n) => n != null ? `₹${Number(n).toLocaleString("en-IN")}` : "—";

  // ── Student card template ──
  const studentTemplate = (number, id, removable) => {
    const classOptionsHtml = classOptions.map(([value, label]) =>
      `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`
    ).join("");
    const boardOptionsHtml = boardOptions.map(([value, label]) =>
      `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`
    ).join("");
    return `
      <article class="student-card" data-student-id="${id}" aria-labelledby="student-title-${id}">
        <div class="student-card-header">
          <h4 id="student-title-${id}">Student ${number} details</h4>
          ${removable ? `<button type="button" class="remove-student" data-remove-student="${id}" aria-label="Remove Student ${number}">Remove student</button>` : ""}
        </div>
        <div class="field-grid">
          <label class="field full-width">Student name <span class="optional">OPTIONAL</span>
            <input name="studentName" maxlength="120" placeholder="Student's name">
          </label>
          <label class="field">Class or grade <span class="required">*</span>
            <select name="grade" required><option value="">Select a class</option>${classOptionsHtml}</select>
          </label>
          <label class="field">Education board <span class="required">*</span>
            <select name="board" required>${boardOptionsHtml}</select>
          </label>
          <label class="field full-width custom-board-field" hidden>Custom board name <span class="required">*</span>
            <input name="customBoard" maxlength="100" placeholder="Enter the board or curriculum name">
          </label>
          <label class="field full-width stream-field" hidden>Academic stream <span class="optional">OPTIONAL</span>
            <select name="stream"><option value="">Select a stream</option><option>Science</option><option>Commerce</option><option>Humanities</option><option>Other</option></select>
          </label>
          <label class="field full-width">Subjects of interest <span class="optional">OPTIONAL</span>
            <textarea name="subjects" rows="2" maxlength="300" placeholder="Share the subjects your child needs support with"></textarea>
          </label>
          <p class="subject-note full-width">Subject choices are confirmed by REDDY ACADEMY after enquiry.</p>
          <label class="field full-width">Tuition type <span class="optional">OPTIONAL</span>
            <select name="tuitionType"><option value="">Select if known</option><option>One-to-one</option><option>Small group</option><option>To be discussed</option></select>
          </label>
        </div>
      </article>`;
  };

  const currentStudentCards = () => [...studentList.querySelectorAll(".student-card")];

  const updateEmailRequirement = () => {
    const emailRequired = form.querySelector('[name="contactMethod"]:checked')?.value === "Email";
    const emailInput = form.elements.namedItem("email");
    const requirementLabel = document.querySelector("#email-requirement");
    emailInput.required = emailRequired;
    requirementLabel.textContent = emailRequired ? "REQUIRED" : "OPTIONAL";
    requirementLabel.className = emailRequired ? "required" : "optional";
  };

  const renumberStudents = () => {
    currentStudentCards().forEach((card, index) => {
      const number = index + 1;
      const heading = card.querySelector("h4");
      const removeButton = card.querySelector(".remove-student");
      heading.textContent = `Student ${number} details`;
      heading.id = `student-title-${card.dataset.studentId}`;
      card.setAttribute("aria-labelledby", heading.id);
      if (removeButton) {
        removeButton.setAttribute("aria-label", `Remove Student ${number}`);
        removeButton.hidden = currentStudentCards().length <= 1;
      }
    });
  };

  const toggleStudentDetails = (card) => {
    const board = card.querySelector('[name="board"]');
    const customField = card.querySelector(".custom-board-field");
    const customInput = card.querySelector('[name="customBoard"]');
    const isCustom = board.value === "other";
    customField.hidden = !isCustom;
    customInput.required = isCustom;
    if (!isCustom) customInput.value = "";

    const grade = card.querySelector('[name="grade"]').value;
    const streamField = card.querySelector(".stream-field");
    const stream = card.querySelector('[name="stream"]');
    const needsStream = ["class-11", "class-12", "intermediate-1", "intermediate-2"].includes(grade);
    streamField.hidden = !needsStream;
    if (!needsStream) stream.value = "";
  };

  const addStudent = (allowOverTwo) => {
    const cards = currentStudentCards();
    if (cards.length >= maxStudents) {
      setError(2, `A maximum of ${maxStudents} students can be included.`);
      return;
    }
    if (!allowOverTwo && cards.length >= 2) return;
    const id = nextStudentId++;
    studentList.insertAdjacentHTML("beforeend", studentTemplate(cards.length + 1, id, true));
    syncStudentCount();
    renumberStudents();
    const newCard = studentList.querySelector(`[data-student-id="${id}"]`);
    newCard.querySelector('[name="grade"]').focus();
  };

  const syncStudentCount = () => {
    const count = currentStudentCards().length;
    studentCountRadios.forEach((radio) => {
      radio.checked = Number(radio.value) === count && count <= 2;
    });
  };

  const setError = (step, message) => {
    if (errorMessages[step]) errorMessages[step].textContent = message;
  };

  const clearErrors = () => {
    Object.values(errorMessages).forEach((el) => { if (el) el.textContent = ""; });
  };

  // ─────────────────────────────────────────────
  // LIVE FEE WIDGET  (always-visible in aside)
  // ─────────────────────────────────────────────
  const liveWidget       = document.querySelector("#live-fee-widget");
  const lwfSpinner       = document.querySelector("#lfw-spinner");
  const lwfBody          = document.querySelector("#lfw-body");

  const updateLiveWidget = () => {
    if (!liveWidget) return;

    if (feeEstimatePending) {
      liveWidget.hidden = false;
      lwfSpinner.hidden = false;
      lwfBody.innerHTML = `<p class="lfw-calculating">Calculating…</p>`;
      return;
    }
    lwfSpinner.hidden = true;

    if (feeEstimateError || !feeEstimateData) {
      if (!feeEstimateData && !feeEstimateError) {
        // Nothing selected yet — hide widget
        liveWidget.hidden = true;
      } else {
        liveWidget.hidden = false;
        lwfBody.innerHTML = `<p class="lfw-error">${escapeHtml(feeEstimateError || "Estimate unavailable")}</p>`;
      }
      return;
    }

    liveWidget.hidden = false;
    const data = feeEstimateData;
    let html = "";

    data.students.forEach((s, i) => {
      const label = data.students.length > 1 ? `Student ${i + 1} — ${escapeHtml(s.grade)}` : escapeHtml(s.grade);
      if (s.status === "unavailable") {
        html += `<div class="lfw-row">
          <span class="lfw-label">${label}</span>
          <span class="lfw-value lfw-na">Contact us</span>
        </div>`;
      } else {
        html += `<div class="lfw-row">
          <span class="lfw-label">${label}</span>
          <span class="lfw-value">${fmt(s.estimated_fee)}<small>/mo</small>${s.capped ? ' <span class="lfw-capped" title="Capped at maximum">↑</span>' : ""}</span>
        </div>`;
      }
    });

    if (data.students.length > 1 && data.combined_monthly_fee != null) {
      html += `<div class="lfw-row lfw-total">
        <span class="lfw-label"><strong>Total</strong></span>
        <span class="lfw-value"><strong>${fmt(data.combined_monthly_fee)}<small>/mo</small></strong></span>
      </div>`;
    }

    lwfBody.innerHTML = html;
  };

  // ─────────────────────────────────────────────
  // STEP-4 FEE PANEL (inside review step)
  // ─────────────────────────────────────────────
  const feePanel   = () => document.querySelector("#fee-estimate-panel");
  const feeLoading = () => document.querySelector("#fee-estimate-loading");
  const feeResult  = () => document.querySelector("#fee-estimate-result");
  const feeErrEl   = () => document.querySelector("#fee-estimate-error");

  const renderFeePanel = () => {
    const panel = feePanel();
    if (!panel) return;
    const loading = feeLoading();
    const result  = feeResult();
    const errEl   = feeErrEl();

    if (feeEstimatePending) {
      panel.hidden = false;
      loading.hidden = false;
      result.hidden = true;
      errEl.hidden = true;
      return;
    }
    loading.hidden = true;

    if (feeEstimateError) {
      panel.hidden = false;
      errEl.hidden = false;
      errEl.textContent = feeEstimateError;
      result.hidden = true;
      return;
    }

    if (!feeEstimateData) {
      panel.hidden = true;
      return;
    }

    panel.hidden = false;
    errEl.hidden = true;
    const data = feeEstimateData;

    let html = `<div class="fee-breakdown">`;
    data.students.forEach((s, i) => {
      const label = data.students.length > 1 ? `Student ${i + 1} — ${escapeHtml(s.grade)}` : escapeHtml(s.grade);
      if (s.status === "unavailable") {
        html += `<div class="fee-row fee-unavailable">
          <span class="fee-label">${label}</span>
          <span class="fee-value fee-na">Unavailable</span>
        </div>
        <p class="fee-note">${escapeHtml(s.unavailable_reason || "Submit enquiry — REDDY ACADEMY will confirm the fee.")}</p>`;
      } else {
        html += `<div class="fee-row">
          <span class="fee-label">${label}</span>
          <span class="fee-value">${fmt(s.estimated_fee)}<small>/month</small>${s.capped ? '<span class="fee-capped"> (max)</span>' : ""}</span>
        </div>`;
      }
    });
    if (data.students.length > 1 && data.combined_monthly_fee != null) {
      html += `<div class="fee-row fee-total">
        <span class="fee-label"><strong>Combined total</strong></span>
        <span class="fee-value"><strong>${fmt(data.combined_monthly_fee)}<small>/month</small></strong></span>
      </div>`;
    }
    html += `</div>`;
    if (data.any_unavailable) {
      html += `<p class="fee-disclaimer fee-partial">Some fees require manual confirmation. Submit your enquiry and REDDY ACADEMY will follow up.</p>`;
    } else {
      html += `<p class="fee-disclaimer">This is an estimate. REDDY ACADEMY will confirm the final fee after reviewing your enquiry.</p>`;
    }
    result.innerHTML = html;
    result.hidden = false;
  };

  // ─────────────────────────────────────────────
  // FEE FETCH LOGIC
  // ─────────────────────────────────────────────
  const buildFeePayload = () => {
    const students = currentStudentCards().map((card) => {
      const gradeText = card.querySelector('[name="grade"]').selectedOptions[0]?.textContent || "";
      const tuitionType = card.querySelector('[name="tuitionType"]').value || null;
      return { grade: gradeText, tuition_type: tuitionType };
    }).filter(s => s.grade && s.grade !== "Select a class");

    if (students.length === 0) return null;

    return {
      students,
      classes_per_week: form.elements.namedItem("classesPerWeek")?.value || null,
      session_duration: form.elements.namedItem("sessionDuration")?.value || null
    };
  };

  const scheduleFeeEstimate = () => {
    clearTimeout(feeDebounceTimer);
    feeDebounceTimer = setTimeout(fetchFeeEstimate, 350);
  };

  const fetchFeeEstimate = async () => {
    const payload = buildFeePayload();
    if (!payload) {
      feeEstimateData = null;
      feeEstimateError = null;
      feeEstimatePending = false;
      updateLiveWidget();
      renderFeePanel();
      return;
    }
    feeEstimatePending = true;
    feeEstimateError = null;
    updateLiveWidget();
    renderFeePanel();

    try {
      const res = await fetch("/api/fees/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const body = await res.json();
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Fee estimation failed.");
      feeEstimateData = body;
      feeEstimateError = null;
    } catch (err) {
      feeEstimateData = null;
      feeEstimateError = err instanceof Error
        ? `Could not estimate fee: ${err.message}`
        : "Fee estimation is temporarily unavailable. You can still submit your enquiry.";
    } finally {
      feeEstimatePending = false;
      updateLiveWidget();
      renderFeePanel();
    }
  };

  // ─────────────────────────────────────────────
  // REVIEW RENDERING
  // ─────────────────────────────────────────────
  const value = (name) => {
    const field = form.elements.namedItem(name);
    return field ? field.value.trim() : "";
  };

  const boardLabel = (card) => {
    const board = card.querySelector('[name="board"]').value;
    if (board === "other") return card.querySelector('[name="customBoard"]').value.trim() || "Other";
    const option = card.querySelector('[name="board"]').selectedOptions[0];
    return option ? option.textContent : "Not provided";
  };

  const gradeLabel = (card) => {
    const select = card.querySelector('[name="grade"]');
    return select.selectedOptions[0]?.textContent || "Not provided";
  };

  const reviewItem = (label, content) => `
    <div class="review-item"><small>${escapeHtml(label)}</small><span>${escapeHtml(content || "Not provided")}</span></div>`;

  const feeReviewSummary = () => {
    if (feeEstimatePending) return reviewItem("Fee estimate", "Calculating…");
    if (feeEstimateError)   return reviewItem("Fee estimate", "See fee panel above for details");
    if (!feeEstimateData)   return reviewItem("Fee estimate", "Select a class to see an estimate");

    const data = feeEstimateData;
    let rows = "";
    data.students.forEach((s, i) => {
      const label = data.students.length > 1 ? `Student ${i + 1} (${s.grade})` : s.grade;
      rows += reviewItem(label, s.status === "unavailable"
        ? "Unavailable — manual review"
        : `${fmt(s.estimated_fee)}/month${s.capped ? " (capped)" : ""}`);
    });
    if (data.students.length > 1 && data.combined_monthly_fee != null) {
      rows += reviewItem("Combined household total", `${fmt(data.combined_monthly_fee)}/month`);
    }
    return rows;
  };

  const renderReview = () => {
    const studentSummaries = currentStudentCards().map((card, index) => {
      const fields = [
        reviewItem("Student name", card.querySelector('[name="studentName"]').value.trim() || "Not provided"),
        reviewItem("Class or grade", gradeLabel(card)),
        reviewItem("Education board", boardLabel(card)),
        reviewItem("Academic stream", card.querySelector('[name="stream"]').value),
        reviewItem("Subjects of interest", card.querySelector('[name="subjects"]').value.trim()),
        reviewItem("Tuition type", card.querySelector('[name="tuitionType"]').value)
      ].join("");
      return `<section class="review-group"><h4>Student ${index + 1}</h4><div class="review-grid">${fields}</div></section>`;
    }).join("");

    const contactMethod = form.querySelector('[name="contactMethod"]:checked')?.value || "Not provided";
    const parentFields = [
      reviewItem("Parent or guardian", value("parentName")),
      reviewItem("Phone", value("phone")),
      reviewItem("Email", value("email")),
      reviewItem("Preferred contact", contactMethod)
    ].join("");
    const preferenceFields = [
      reviewItem("Tutor gender", value("tutorGender")),
      reviewItem("Preferred qualification", value("qualification")),
      reviewItem("Teaching language", value("language")),
      reviewItem("Preferred time", value("preferredTime")),
      reviewItem("Classes per week", value("classesPerWeek")),
      reviewItem("Session duration", value("sessionDuration"))
    ].join("");
    const locationFields = [
      reviewItem("City", value("city")),
      reviewItem("Locality or area", value("locality")),
      reviewItem("PIN code", value("pinCode")),
      reviewItem("Address", value("address")),
      reviewItem("Additional requirements", value("requirements")),
      reviewItem("Privacy consent", form.elements.namedItem("consent").checked ? "Given" : "Not given")
    ].join("");

    document.querySelector("#review-content").innerHTML = `
      <section class="review-group"><h4>Parent information</h4><div class="review-grid">${parentFields}</div></section>
      ${studentSummaries}
      <section class="review-group"><h4>Tutor preferences</h4><div class="review-grid">${preferenceFields}</div></section>
      <section class="review-group"><h4>Location &amp; requirements</h4><div class="review-grid">${locationFields}</div></section>
      <section class="review-group"><h4>Fee estimate</h4><div class="review-grid">${feeReviewSummary()}</div></section>`;
  };

  // ─────────────────────────────────────────────
  // NAVIGATION
  // ─────────────────────────────────────────────
  const showStep = (step) => {
    currentStep = step;
    steps.forEach((section) => {
      section.hidden = Number(section.dataset.step) !== step;
    });
    stepLabel.textContent = `STEP ${String(step).padStart(2, "0")} OF 04`;
    stepName.textContent = stepNames[step - 1];
    progressFill.style.width = `${step * 25}%`;
    document.querySelectorAll("[data-progress-step]").forEach((item) => {
      const itemStep = Number(item.dataset.progressStep);
      item.classList.toggle("active", itemStep === step);
      item.classList.toggle("complete", itemStep < step);
    });
    clearErrors();
    document.querySelector("#preview-result").hidden = true;
    if (step === 4) {
      renderReview();
      fetchFeeEstimate();   // fresh fetch on review step too
    }
    const heading = form.querySelector(`[data-step="${step}"] h3`);
    if (heading) heading.focus({ preventScroll: true });
  };

  const checkPhone = () => {
    const input = form.elements.namedItem("phone");
    const normalized = input.value.replace(/[\s()-]/g, "");
    const valid = /^(?:\+?91)?[6-9]\d{9}$/.test(normalized);
    input.setCustomValidity(valid ? "" : "Enter a valid 10-digit Indian mobile number, with or without +91.");
    return valid;
  };

  const validateCurrentStep = () => {
    clearErrors();
    const section = form.querySelector(`[data-step="${currentStep}"]`);
    const fields = [...section.querySelectorAll("input, select, textarea")].filter((f) => !f.disabled);
    let firstInvalid = null;
    for (const field of fields) {
      if (field.name === "phone") checkPhone();
      if (!field.checkValidity()) { firstInvalid = field; break; }
    }
    if (firstInvalid) {
      firstInvalid.reportValidity();
      if (currentStep === 2) setError(2, "Please provide a class and education board for every student.");
      if (currentStep === 3) setError(3, "Please complete the required location fields and agree to the Privacy Notice.");
      return false;
    }
    return true;
  };

  // ─────────────────────────────────────────────
  // EVENT LISTENERS
  // ─────────────────────────────────────────────

  // Grade / board / tuition type changes on student cards → trigger fee estimate
  studentList.addEventListener("change", (event) => {
    const card = event.target.closest(".student-card");
    if (!card) return;
    if (event.target.name === "board" || event.target.name === "grade") {
      toggleStudentDetails(card);
    }
    if (event.target.name === "grade" || event.target.name === "tuitionType") {
      scheduleFeeEstimate();
    }
  });

  // Classes/week and session duration → trigger fee estimate
  form.addEventListener("change", (event) => {
    if (event.target.name === "classesPerWeek" || event.target.name === "sessionDuration") {
      scheduleFeeEstimate();
    }
  });

  // Remove student button
  studentList.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-student]");
    if (!removeButton) return;
    if (currentStudentCards().length <= 1) return;
    const card = studentList.querySelector(`[data-student-id="${removeButton.dataset.removeStudent}"]`);
    if (!card) return;
    const previous = card.previousElementSibling;
    const next = card.nextElementSibling;
    card.remove();
    renumberStudents();
    syncStudentCount();
    setError(2, "");
    scheduleFeeEstimate();
    const focusTarget = previous?.querySelector("h4") || next?.querySelector("h4") || document.querySelector("#add-student");
    if (focusTarget) {
      if (focusTarget instanceof HTMLHeadingElement) focusTarget.tabIndex = -1;
      focusTarget.focus();
    }
  });

  // Student count radio buttons
  studentCountRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      if (!radio.checked) return;
      const desired = Number(radio.value);
      while (currentStudentCards().length > desired) currentStudentCards().at(-1)?.remove();
      while (currentStudentCards().length < desired) {
        studentList.insertAdjacentHTML("beforeend", studentTemplate(currentStudentCards().length + 1, nextStudentId++, desired > 1));
      }
      renumberStudents();
      scheduleFeeEstimate();
    });
  });

  form.querySelectorAll('[name="contactMethod"]').forEach((radio) => {
    radio.addEventListener("change", updateEmailRequirement);
  });

  document.querySelector("#add-student").addEventListener("click", () => {
    addStudent(true);
    scheduleFeeEstimate();
  });

  form.addEventListener("click", (event) => {
    const next = event.target.closest(".next-step");
    const previous = event.target.closest(".prev-step");
    if (next) {
      if (!validateCurrentStep()) return;
      showStep(Math.min(currentStep + 1, steps.length));
    }
    if (previous) showStep(Math.max(currentStep - 1, 1));
  });

  // ─────────────────────────────────────────────
  // FORM SUBMISSION
  // ─────────────────────────────────────────────
  const buildSubmissionPayload = () => ({
    parent_name: value("parentName"),
    phone: value("phone"),
    email: value("email") || null,
    preferred_contact_method: form.querySelector('[name="contactMethod"]:checked')?.value || "Phone",
    students: currentStudentCards().map((card) => ({
      student_name: card.querySelector('[name="studentName"]').value.trim() || null,
      grade: gradeLabel(card),
      board: card.querySelector('[name="board"]').value === "other" ? "other" : boardLabel(card),
      custom_board: card.querySelector('[name="board"]').value === "other"
        ? card.querySelector('[name="customBoard"]').value.trim() : null,
      stream: card.querySelector('[name="stream"]').value || null,
      subjects: card.querySelector('[name="subjects"]').value.trim() || null,
      tuition_type: card.querySelector('[name="tuitionType"]').value || null
    })),
    tutor_gender: value("tutorGender") || null,
    qualification: value("qualification") || null,
    language: value("language") || null,
    preferred_time: value("preferredTime") || null,
    classes_per_week: value("classesPerWeek") || null,
    session_duration: value("sessionDuration") || null,
    city: value("city"),
    locality: value("locality"),
    pin_code: value("pinCode"),
    address: value("address") || null,
    message: value("requirements") || null,
    consent: form.elements.namedItem("consent").checked
  });

  const newIdempotencyKey = () => {
    if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
    const bytes = new Uint8Array(24);
    crypto.getRandomValues(bytes);
    return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  };

  document.querySelector("#submit-enquiry").addEventListener("click", async (event) => {
    clearErrors();
    const button = event.currentTarget;
    const result = document.querySelector("#preview-result");
    const payload = buildSubmissionPayload();
    const serialized = JSON.stringify(payload);
    if (serialized !== lastSubmissionPayload) {
      submissionIdempotencyKey = newIdempotencyKey();
      lastSubmissionPayload = serialized;
    }
    button.disabled = true;
    button.querySelector("span:first-child").textContent = "Submitting…";
    result.hidden = true;
    try {
      const res = await fetch("/api/enquiries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, idempotency_key: submissionIdempotencyKey })
      });
      const body = await res.json();
      if (!res.ok) {
        const msg = typeof body.detail === "string"
          ? body.detail : "We could not save your enquiry. Please check the form and try again.";
        throw new Error(msg);
      }
      const feeNote = feeEstimateData?.combined_monthly_fee
        ? ` Estimated combined monthly fee: ${fmt(feeEstimateData.combined_monthly_fee)} (subject to confirmation).`
        : " REDDY ACADEMY will confirm applicable fees after reviewing your requirements.";
      result.textContent = `${body.message} Your reference is ${body.reference}.${feeNote}`;
      result.hidden = false;
      result.focus();
      button.textContent = "Enquiry submitted";
      form.querySelectorAll("input, select, textarea, button").forEach((f) => { f.disabled = true; });
      document.querySelectorAll(".prev-step").forEach((b) => { b.disabled = true; });
    } catch (err) {
      setError(4, err instanceof Error
        ? `${err.message} Your enquiry has not been confirmed. You can retry safely.`
        : "We could not confirm that your enquiry was saved. Please retry.");
      button.disabled = false;
      button.innerHTML = 'Submit enquiry <span aria-hidden="true">→</span>';
    }
  });

  form.addEventListener("input", (event) => {
    if (event.target.name === "phone") event.target.setCustomValidity("");
  });
  form.addEventListener("submit", (event) => event.preventDefault());

  // ─────────────────────────────────────────────
  // INIT
  // ─────────────────────────────────────────────
  studentList.insertAdjacentHTML("beforeend", studentTemplate(1, 1, false));
  updateEmailRequirement();
  showStep(1);
})();
