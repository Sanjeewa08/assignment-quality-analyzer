const app = document.querySelector("#app");
const nav = document.querySelector("#navigation");
const notice = document.querySelector("#notice");
const state = { user: null, csrf: "" };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function showNotice(message, type = "danger") {
  notice.innerHTML = message
    ? `<div class="alert alert-${type} alert-dismissible" role="alert">${escapeHtml(message)}<button type="button" class="btn-close" aria-label="Dismiss"></button></div>`
    : "";
  notice.querySelector(".btn-close")?.addEventListener("click", () => { notice.innerHTML = ""; });
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.csrf && options.method && options.method !== "GET") {
    headers.set("X-CSRFToken", state.csrf);
  }
  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    const body = contentType.includes("application/json") ? await response.json() : {};
    throw new Error(body.error || `Request failed (${response.status}).`);
  }
  if (contentType.includes("application/pdf")) return response.blob();
  return response.json();
}

function renderNav() {
  nav.innerHTML = state.user
    ? `<a class="btn btn-sm btn-outline-primary" href="#/">Analyze</a>
       <a class="btn btn-sm btn-outline-primary" href="#/history">History</a>
       ${state.user.role === "lecturer" ? '<a class="btn btn-sm btn-outline-primary" href="#/rubrics">Rubrics</a>' : ""}
       <span class="small text-secondary d-none d-md-inline">${escapeHtml(state.user.email)}</span>
       <button class="btn btn-sm btn-outline-secondary" id="sign-out" type="button">Sign out</button>`
    : `<a class="btn btn-sm btn-outline-primary" href="#/login">Sign in</a>
       <a class="btn btn-sm btn-primary" href="#/register">Create account</a>`;
  document.querySelector("#sign-out")?.addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST" });
      state.user = null;
      renderNav();
      navigate("/");
    } catch (error) {
      showNotice(error.message);
    }
  });
}

function navigate(path) {
  location.hash = path === "/" ? "#/" : `#${path}`;
  render();
}

function renderLanding() {
  if (!state.user) {
    app.innerHTML = `
      <section class="hero-panel p-4 p-lg-5 mb-4">
        <div class="eyebrow">ACADEMIC WRITING QA</div>
        <h1 class="display-4 fw-bold mt-2">Improve the work.<br><em>Keep the integrity.</em></h1>
        <p class="lead mb-0">A transparent revision checklist for clarity, structure, citations, and formatting—not an automated grade or misconduct verdict.</p>
      </section>
      <section class="card shadow-sm border-0 text-center p-4">
        <h2 class="h4">Sign in to analyze and track your work</h2>
        <p class="text-secondary">Your submission history is private to your account. Lecturers can create shared rubrics.</p>
        <div><a class="btn btn-primary" href="#/login">Sign in</a> <a class="btn btn-outline-primary" href="#/register">Create student account</a></div>
      </section>`;
    return;
  }
  loadUpload();
}

async function loadUpload() {
  try {
    const { rubrics } = await api("/rubrics");
    const rubricOptions = rubrics.map((row) => `<option value="${row.id}">${escapeHtml(row.title)}</option>`).join("");
    app.innerHTML = `
      <section class="hero-panel p-4 p-lg-5 mb-4">
        <div class="eyebrow">ACADEMIC WRITING QA</div>
        <h1 class="display-4 fw-bold mt-2">Improve the work.<br><em>Keep the integrity.</em></h1>
        <p class="lead mb-0">A transparent revision checklist for clarity, structure, citations, and formatting—not an automated grade or misconduct verdict.</p>
      </section>
      <section class="card shadow-sm border-0 p-3 p-lg-4">
        <form id="upload-form">
          <label class="dropzone w-100 p-4 text-center" for="assignment">
            <input class="form-control" id="assignment" type="file" name="assignment" accept=".txt,.docx,.pdf,.ppt,.pptx,.jpg,.jpeg,.png" required>
            <strong class="d-block fs-5 mt-2">Choose an assignment to analyze</strong>
            <span class="text-secondary">TXT, DOCX, PDF, PPT, PPTX, JPG, JPEG, PNG · 10 MB max</span>
          </label>
          <div class="row g-3 mt-2">
            <div class="col-sm-4"><label class="form-label" for="min_words">Minimum words</label><input class="form-control" id="min_words" type="number" name="min_words" min="1" placeholder="Optional"></div>
            <div class="col-sm-4"><label class="form-label" for="max_words">Maximum words</label><input class="form-control" id="max_words" type="number" name="max_words" min="1" placeholder="Optional"></div>
            <div class="col-sm-4"><label class="form-label" for="min_references">Minimum references</label><input class="form-control" id="min_references" type="number" name="min_references" min="1" placeholder="Optional"></div>
          </div>
          ${rubrics.length ? `<div class="mt-3"><label class="form-label" for="rubric_id">Lecturer rubric</label><select class="form-select" id="rubric_id" name="rubric_id"><option value="">No rubric</option>${rubricOptions}</select></div>` : ""}
          <div class="mt-3"><label class="form-label" for="reference_text">Optional reference passage for comparison</label><textarea class="form-control" id="reference_text" name="reference_text" rows="3" placeholder="Compared locally for possible overlap; this app does not search the internet."></textarea></div>
          <button class="btn btn-primary btn-lg w-100 mt-4" type="submit">Analyze assignment</button>
        </form>
      </section>
      <section class="row g-3 mt-3">
        <div class="col-md-4"><div class="feature-card h-100"><strong>Explainable signals</strong><p>Readability, writing style, structure, and citation checks are shown with limitations.</p></div></div>
        <div class="col-md-4"><div class="feature-card h-100"><strong>Local comparison</strong><p>Possible overlaps compare only to local submissions and optional reference passages.</p></div></div>
        <div class="col-md-4"><div class="feature-card h-100"><strong>Guidance, not rewriting</strong><p>Get revision suggestions while keeping authorship and academic integrity in your hands.</p></div></div>
      </section>
      <p class="small text-secondary mt-4">AI-style signals are weak heuristics, not authorship tests. Never use them alone for academic or disciplinary decisions.</p>`;
    document.querySelector("#upload-form").addEventListener("submit", submitAssignment);
  } catch (error) {
    showNotice(error.message);
  }
}

function renderAuth(mode) {
  const register = mode === "register";
  app.innerHTML = `
    <section class="card shadow-sm border-0 p-4 mx-auto" style="max-width:520px">
      <h1 class="h3">${register ? "Create student account" : "Sign in"}</h1>
      <form id="auth-form">
        <label class="form-label mt-3" for="email">Email</label>
        <input class="form-control" id="email" name="email" type="email" maxlength="255" autocomplete="email" required>
        <label class="form-label mt-3" for="password">Password</label>
        <input class="form-control" id="password" name="password" type="password" minlength="${register ? 10 : 1}" autocomplete="${register ? "new-password" : "current-password"}" required>
        <button class="btn btn-primary w-100 mt-4" type="submit">${register ? "Create account" : "Sign in"}</button>
      </form>
      <p class="small text-secondary mt-3 mb-0">${register ? 'Already registered? <a href="#/login">Sign in</a>' : 'New here? <a href="#/register">Create a student account</a>'}</p>
    </section>`;
  document.querySelector("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const { user } = await api(`/auth/${register ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      state.user = user;
      renderNav();
      showNotice(register ? "Account created." : "Signed in.", "success");
      navigate("/");
    } catch (error) {
      showNotice(error.message);
    }
  });
}

async function submitAssignment(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Analyzing…";
  try {
    const result = await api("/analyze", { method: "POST", body: new FormData(event.currentTarget) });
    showReport(result.submission);
  } catch (error) {
    showNotice(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Analyze assignment";
  }
}

function showReport(submission) {
  const report = submission.report;
  const categories = Object.entries(report.category_scores || {}).map(([name, score]) => `
    <div class="col-md-6"><div class="d-flex justify-content-between"><span>${escapeHtml(name)}</span><strong>${escapeHtml(score)}%</strong></div>
    <div class="progress" role="progressbar" aria-valuenow="${Number(score) || 0}" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar" style="width:${Math.max(0, Math.min(100, Number(score) || 0))}%"></div></div></div>`).join("");
  const feedback = (report.feedback || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const grammarErrors = (report.writing?.grammar?.errors || []).slice(0, 8)
    .map((item) => `<li>“${escapeHtml(item.text)}” — possible suggestion: “${escapeHtml(item.suggestion)}”</li>`).join("");
  const formatting = report.formatting?.available ? `
    <section class="card shadow-sm border-0 p-4 mb-4"><h2 class="h4">DOCX formatting review · ${escapeHtml(report.formatting.score)}%</h2>
    ${(report.formatting.checks || []).map((check) => `<p>${check.passed ? "✓" : "!"} <strong>${escapeHtml(check.name)}</strong> — ${escapeHtml(check.detail)}</p>`).join("")}
    <p class="small text-secondary">${escapeHtml(report.formatting.note)}</p></section>` : "";
  const rubric = report.rubric?.criteria?.length ? `
    <section class="card shadow-sm border-0 p-4 mb-4"><h2 class="h4">Rubric checklist${report.rubric.score == null ? "" : ` · ${escapeHtml(report.rubric.score)}%`}</h2>
    ${(report.rubric.criteria || []).map((item) => `<p>${item.passed === true ? "✓" : item.passed === false ? "!" : "·"} <strong>${escapeHtml(item.label)}</strong> — ${escapeHtml(item.detail)}</p>`).join("")}</section>` : "";
  const highlights = (report.highlights || []).map((item) => `
    <p class="border-bottom py-2"><mark>${escapeHtml(item.text)}</mark> <span class="badge text-bg-secondary">${escapeHtml(item.type)}</span>
    <small class="d-block text-secondary">${escapeHtml(item.detail)}</small></p>`).join("");
  app.innerHTML = `
    <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
      <a href="#/">← Analyze another file</a>
      <a class="btn btn-outline-primary" href="/api/reports/${submission.id}/pdf">Download PDF report</a>
    </div>
    <header class="report-heading mb-4"><div class="eyebrow">ANALYSIS REPORT</div><h1 class="h2 mt-2">${escapeHtml(submission.file_name)}</h1>
      <p class="text-secondary">Use these signals as a revision checklist, not as an academic verdict.</p></header>
    <section class="card shadow-sm border-0 p-4 mb-4">
      <div class="d-flex flex-wrap align-items-center gap-3"><div class="score-circle">${escapeHtml(report.overall_score)}</div><div><div class="eyebrow">OVERALL QUALITY SCORE</div><p class="mb-0">An equally weighted checklist, not a grade. Requirements vary by course.</p></div></div>
      <div class="row g-3 mt-3">${categories}</div>
    </section>
    <div class="row g-4 mb-4">
      <div class="col-lg-7"><section class="card shadow-sm border-0 p-4 h-100"><h2 class="h4">Actionable feedback</h2><ul>${feedback}</ul></section></div>
      <div class="col-lg-5"><section class="card shadow-sm border-0 p-4 h-100"><h2 class="h4">Document overview</h2><div class="stats-grid">
        <div><strong>${escapeHtml(report.writing?.counts?.words)}</strong><span>Words</span></div>
        <div><strong>${escapeHtml(report.writing?.counts?.characters)}</strong><span>Characters</span></div>
        <div><strong>${escapeHtml(report.writing?.counts?.sentences)}</strong><span>Sentences</span></div>
        <div><strong>${escapeHtml(report.writing?.counts?.paragraphs)}</strong><span>Paragraphs</span></div></div>
        <p class="mt-3 mb-1"><strong>Readability:</strong> ${escapeHtml(report.writing?.readability?.interpretation)}</p>
        <p class="small text-secondary">Flesch ${escapeHtml(report.writing?.readability?.flesch_reading_ease)} · Grade ${escapeHtml(report.writing?.readability?.flesch_kincaid_grade)} · Gunning Fog ${escapeHtml(report.writing?.readability?.gunning_fog)}</p></section></div>
    </div>
    <div class="row g-4 mb-4">
      <div class="col-lg-6"><section class="card shadow-sm border-0 p-4 h-100"><h2 class="h4">Structure</h2>
        ${Object.entries(report.writing?.structure?.sections || {}).map(([name, present]) => `<p>${present ? "✓" : "!"} <strong>${escapeHtml(name)}</strong> — ${present ? `${escapeHtml(report.writing.structure.section_word_counts?.[name] || 0)} words` : "Missing"}</p>`).join("")}
        <p class="small text-secondary">Detected headings: ${escapeHtml((report.writing?.structure?.headings || []).join(", ") || "None recognized")}</p></section></div>
      <div class="col-lg-6"><section class="card shadow-sm border-0 p-4 h-100"><h2 class="h4">Citations & references</h2>
        <p>Likely style: <strong>${escapeHtml(report.citations?.style_detected)}</strong> · ${escapeHtml(report.citations?.in_text_count)} in-text citation(s) · ${escapeHtml(report.citations?.reference_count)} reference(s)</p>
        ${(report.citations?.issues || []).map((issue) => `<p class="alert alert-warning">${escapeHtml(issue)}</p>`).join("")}
        ${(report.citations?.suggestions || []).map((item) => `<p class="small text-secondary">${escapeHtml(item)}</p>`).join("")}
        <h3 class="h5 mt-3">Originality & AI-style signals</h3>
        <p>Originality review score: <strong>${escapeHtml(report.originality?.score)}/100</strong></p>
        <p class="small text-secondary">${escapeHtml(report.originality?.disclaimer)}</p>
        <p>Compared with ${escapeHtml(report.originality?.breakdown?.compared_documents)} local/reference document(s). Highest similarity: ${escapeHtml(report.originality?.breakdown?.highest_document_similarity)}%.</p>
        <p>AI-style heuristic confidence: <strong>${escapeHtml(report.writing?.ai_likelihood?.confidence)}/100</strong></p>
        <p class="small text-secondary">${escapeHtml(report.writing?.ai_likelihood?.disclaimer)}</p>
        ${(report.writing?.ai_likelihood?.signals || []).length ? `<p>Signals: ${escapeHtml(report.writing.ai_likelihood.signals.join("; "))}.</p>` : ""}</section></div>
    </div>
    <div class="row g-4 mb-4">
      <div class="col-lg-6"><section class="card shadow-sm border-0 p-4 h-100"><h2 class="h4">Writing style & mechanics</h2>
        <p>Average sentence: <strong>${escapeHtml(report.writing?.style?.average_sentence_words)} words</strong> · Tone: <strong>${escapeHtml(report.writing?.style?.tone)}</strong> · Vocabulary diversity: <strong>${escapeHtml(report.writing?.style?.vocabulary_diversity)}</strong></p>
        <p>Possible grammar/spelling flags: <strong>${(report.writing?.grammar?.errors || []).length}</strong> · Check engine: ${escapeHtml(report.writing?.grammar?.engine)}</p>
        ${grammarErrors ? `<ul>${grammarErrors}</ul>` : ""}
        ${(report.writing?.style?.passive_voice_examples || []).length ? `<p>Possible passive constructions: ${escapeHtml(report.writing.style.passive_voice_examples.join(", "))}</p>` : ""}
        ${(report.writing?.style?.repeated_words || []).length ? `<p>Repeated terms: ${report.writing.style.repeated_words.map((item) => `${escapeHtml(item.word)} (${escapeHtml(item.count)})`).join(", ")}</p>` : ""}
      </section></div>
      <div class="col-lg-6"><section class="card shadow-sm border-0 p-4 h-100"><h2 class="h4">Requirements</h2>
        ${report.word_requirement?.minimum || report.word_requirement?.maximum ? `<p><strong>Word target:</strong> ${escapeHtml(report.word_requirement.minimum || "No minimum")}–${escapeHtml(report.word_requirement.maximum || "No maximum")} · ${report.word_requirement.passed ? "Met" : "Not met"}</p>` : ""}
        ${report.reference_requirement?.minimum ? `<p><strong>Reference target:</strong> at least ${escapeHtml(report.reference_requirement.minimum)} · ${report.reference_requirement.passed ? "Met" : "Not met"}</p>` : ""}
      </section></div>
    </div>
    ${formatting}
    ${rubric}
    <section class="card shadow-sm border-0 p-4 mb-4"><h2 class="h4">Highlighted text</h2>
      <p class="small text-secondary">Highlights identify possible review items. Check context before making changes.</p>
      ${highlights || "<p>No inline issues were flagged by the available checks.</p>"}</section>
    <p class="small text-secondary">${escapeHtml(report.ethics)}</p>`;
}

async function renderReport(id) {
  try {
    const { submission } = await api(`/reports/${encodeURIComponent(id)}`);
    showReport(submission);
  } catch (error) {
    showNotice(error.message);
  }
}

async function renderHistory() {
  try {
    const { submissions } = await api("/history");
    const rows = submissions.map((item) => `<tr><td>${escapeHtml(new Date(item.created_at).toLocaleString())}</td>
      <td>${escapeHtml(item.file_name)}</td><td>${escapeHtml(item.word_count)}</td><td>${escapeHtml(item.quality_score)}/100</td>
      <td><a href="#/report/${item.id}">View report</a></td></tr>`).join("");
    app.innerHTML = `<div class="d-flex justify-content-between align-items-center mb-3"><div><div class="eyebrow">PRIVATE TO YOUR ACCOUNT</div><h1 class="h2">Submission history</h1></div><a class="btn btn-primary" href="#/">Analyze assignment</a></div>
      <section class="card shadow-sm border-0 p-0 overflow-hidden"><div class="table-responsive"><table class="table table-hover mb-0">
      <thead><tr><th>Date</th><th>Assignment</th><th>Words</th><th>Score</th><th></th></tr></thead><tbody>${rows || '<tr><td colspan="5" class="text-center py-4 text-secondary">No submissions yet.</td></tr>'}</tbody></table></div></section>`;
  } catch (error) {
    showNotice(error.message);
  }
}

async function renderRubrics() {
  if (state.user.role !== "lecturer") {
    showNotice("Lecturer access is required.");
    navigate("/");
    return;
  }
  try {
    const { rubrics } = await api("/rubrics");
    app.innerHTML = `<div class="eyebrow">LECTURER TOOLS</div><h1 class="h2 mb-4">Rubric library</h1>
      <div class="row g-4"><div class="col-lg-5"><section class="card shadow-sm border-0 p-4"><h2 class="h5">Create a rubric</h2>
      <p class="small text-secondary">One rule per line. Supported auto-checks: “must include a conclusion”, “min 1500 words”, and “min 5 references”. Other lines require lecturer review.</p>
      <form id="rubric-form"><label class="form-label" for="title">Rubric title</label><input class="form-control mb-3" id="title" name="title" maxlength="120" required>
      <label class="form-label" for="criteria">Criteria</label><textarea class="form-control mb-3" id="criteria" name="criteria" rows="6" required></textarea><button class="btn btn-primary">Save rubric</button></form></section></div>
      <div class="col-lg-7"><section class="card shadow-sm border-0 p-4"><h2 class="h5">Saved rubrics</h2>
      ${rubrics.map((rubric) => `<article class="border-bottom py-3"><strong>${escapeHtml(rubric.title)}</strong></article>`).join("") || '<p class="text-secondary">No rubrics created yet.</p>'}
      </section></div></div>`;
    document.querySelector("#rubric-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      try {
        await api("/rubrics", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: form.get("title"), criteria: form.get("criteria") }),
        });
        showNotice("Rubric saved.", "success");
        renderRubrics();
      } catch (error) {
        showNotice(error.message);
      }
    });
  } catch (error) {
    showNotice(error.message);
  }
}

async function render() {
  showNotice("");
  renderNav();
  const path = location.hash.replace(/^#/, "") || "/";
  if (path === "/login" || path === "/register") {
    renderAuth(path.slice(1));
  } else if (path === "/history") {
    if (state.user) await renderHistory();
    else navigate("/login");
  } else if (path === "/rubrics") {
    if (state.user) await renderRubrics();
    else navigate("/login");
  } else if (path.startsWith("/report/")) {
    if (state.user) await renderReport(path.slice("/report/".length));
    else navigate("/login");
  } else {
    renderLanding();
  }
}

async function start() {
  try {
    const csrf = await fetch("/api/csrf", { credentials: "same-origin" });
    if (!csrf.ok) throw new Error("Could not initialize a secure session.");
    state.csrf = (await csrf.json()).csrf_token;
    const { user } = await api("/me");
    state.user = user;
    render();
  } catch (error) {
    showNotice(error.message);
    app.innerHTML = '<p class="text-secondary">The application API is unavailable. Check the Vercel API rewrite and Azure backend.</p>';
  }
}

window.addEventListener("hashchange", render);
start();
