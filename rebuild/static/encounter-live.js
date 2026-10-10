"use strict";

// Read-only polling never submits a job. A generation is sent only by the
// doctor's form submission. The server retains one generation attempt per
// saved source revision; saving notes again is the explicit new-request action.
(() => {
  const root = document.querySelector("[data-encounter-live]");
  if (!root || !window.fetch || !window.quillmdFormState) return;
  const statusURL = new URL(root.dataset.statusUrl, location.href);
  if (statusURL.origin !== location.origin) return;
  const latest = root.querySelector("[data-latest-job]");
  const pendingNotice = root.querySelector("[data-pending-job]");
  const connection = root.querySelector("[data-live-connection]");
  const errorNotice = root.querySelector("[data-live-error]");
  const preview = root.querySelector("[data-live-result-preview]");
  const previewHelp = root.querySelector("[data-live-result-help]");
  const previewContent = root.querySelector("[data-live-result-content]");
  const showResult = root.querySelector("[data-show-saved-result]");
  const generationForm = root.querySelector("[data-generate-form]");
  const initialRevision = Number(root.dataset.revision);
  let appliedVersion = root.dataset.resultVersion;
  let snapshot = null, stagedVersion = null, timer, pollController;
  let posting = false, uncertainSubmission = false, stopped = false, rendering = false, polling = false;
  let requestEpoch = 0;
  let failures = 0;
  const stateNames = {queued:"Queued", running:"Running", succeeded:"Ready for review", failed:"Failed",
    reconciliation:"Needs administrator review", cancelled:"Cancelled"};
  const showError = (message, link = null) => {
    errorNotice.replaceChildren(document.createTextNode(message));
    if (link) {
      const anchor = document.createElement("a");
      anchor.href = link;
      anchor.textContent = link === "/login/" ? " Sign in again" : " Open the current document";
      errorNotice.append(anchor);
    }
    errorNotice.hidden = false;
  };
  const updateControls = () => {
    const pending = Boolean(snapshot?.pending);
    const stale = snapshot && snapshot.revision !== initialRevision;
    const locked = pending || posting || uncertainSubmission || stopped || stale;
    const notes = root.querySelector("[data-notes-form]");
    if (notes) {
      // Readonly preserves FormData and the doctor's local unsaved text.
      notes.querySelector("textarea").readOnly = pending;
      notes.querySelector("button[type=submit]").disabled = locked;
    }
    const voice = root.querySelector("[data-voice-form] fieldset");
    if (voice) voice.disabled = locked;
    root.querySelectorAll("[data-transcript-form] button[type=submit]").forEach((button) => {button.disabled = locked;});
    if (generationForm) {
      const button = generationForm.querySelector("button[type=submit]");
      button.disabled = locked || generationForm.dataset.generationAvailable !== "true";
      generationForm.closest(".generation-action").hidden = snapshot?.status === "review" || snapshot?.status === "finalized";
    }
    pendingNotice.hidden = !pending;
  };
  const renderStatus = (data) => {
    const badge = document.querySelector("[data-live-document-status]");
    if (badge && ["draft", "review", "finalized"].includes(data.status)) {
      badge.classList.remove("draft", "review", "finalized");
      badge.classList.add(data.status);
      badge.textContent = data.status;
    }
    const job = data.latest_job;
    latest.hidden = !job;
    latest.classList.toggle("warning", Boolean(job && ["failed", "reconciliation"].includes(job.state)));
    latest.replaceChildren();
    if (job) {
      const title = document.createElement("strong"), detail = document.createElement("p");
      title.textContent = `${job.kind === "transcription" ? "Transcription" : "Generation"} · ${stateNames[job.state] || job.state}`;
      detail.textContent = job.display_error || ({
        queued:"Your saved notes are queued. This page checks progress automatically.",
        running:"The request is processing. Results will appear here when ready.",
        succeeded:job.kind === "transcription" ? "The transcript is ready. Review it before adding it to your saved notes." : "The answer draft is ready below. Review its facts, evidence and missing information before finalizing.",
        failed:"This request failed. Review its retained entry in Document record before deciding whether to submit a new request.",
        reconciliation:"An administrator must reconcile the provider outcome. Do not submit this request again.",
        cancelled:"The queued request was cancelled. No automatic retry will be sent."
      }[job.state] || "Check the request in Document record.");
      latest.append(title, detail);
      if (job.kind === "generation" && job.state === "failed") {
        const retry = document.createElement("p");
        retry.textContent = "Review this error and Document record. To explicitly try again, save the source notes again (unchanged is fine), then generate. Refreshing or clicking Generate again on this revision reuses this attempt.";
        latest.append(retry);
      }
    }
    updateControls();
  };
  const stageResult = (data) => {
    if (stagedVersion !== data.result_version) {
      previewContent.replaceChildren();
      for (const answer of data.answers_preview || []) {
        const row = document.createElement("section"), title = document.createElement("h4"), text = document.createElement("p");
        title.textContent = `${answer.label} · ${answer.status}`;
        text.textContent = answer.text || "No answer documented; review required.";
        row.append(title, text);
        previewContent.append(row);
      }
      stagedVersion = data.result_version;
    }
    preview.hidden = false;
    previewHelp.textContent = data.revision !== initialRevision
      ? "The source revision changed in another window. Your local edits are preserved. Open the current document before saving."
      : "Your unsaved review edits are preserved. Save or undo them before opening the complete saved result and its evidence.";
    showResult.disabled = data.revision !== initialRevision;
  };
  const refreshReview = async (data) => {
    if (rendering || data.result_version === appliedVersion || data.pending) return;
    const current = document.querySelector("[data-live-review]");
    if (!current) return;
    if (data.revision !== initialRevision || window.quillmdFormState.hasUnsavedEdits(current)) {
      stageResult(data);
      return;
    }
    rendering = true;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(location.pathname, {credentials:"same-origin", cache:"no-store", signal:controller.signal,
        headers:{Accept:"text/html"}});
      if (response.redirected || !response.ok || !(response.headers.get("content-type") || "").includes("text/html")) throw new Error("result_unavailable");
      const parsed = new DOMParser().parseFromString(await response.text(), "text/html");
      const incomingRoot = parsed.querySelector("[data-encounter-live]"), incoming = parsed.querySelector("[data-live-review]");
      // A later transition or edit can arrive while HTML is in flight. Never
      // substitute a page for a different revision or overwrite newly typed edits.
      if (!incoming || incomingRoot?.dataset.encounterId !== root.dataset.encounterId
          || Number(incomingRoot.dataset.revision) !== initialRevision
          || incomingRoot.dataset.resultVersion !== data.result_version
          || snapshot?.result_version !== data.result_version) return;
      if (window.quillmdFormState.hasUnsavedEdits(current)) {stageResult(data);return;}
      current.replaceWith(incoming);
      document.dispatchEvent(new CustomEvent("quillmd:content-updated", {detail:{root:incoming}}));
      const workflow = document.querySelector("[data-live-workflow]"), incomingWorkflow = parsed.querySelector("[data-live-workflow]");
      if (workflow && incomingWorkflow) workflow.replaceWith(incomingWorkflow);
      // Transcription review is a separate form: append a new returned transcript
      // without replacing any existing local transcript corrections or notes.
      for (const transcript of parsed.querySelectorAll(".transcript-review")) {
        if (!root.querySelector(`#${CSS.escape(transcript.querySelector("h3").id)}`)) {
          root.querySelector(".voice-input").append(transcript);
          document.dispatchEvent(new CustomEvent("quillmd:content-updated", {detail:{root:transcript}}));
        }
      }
      appliedVersion = data.result_version;
      preview.hidden = true;
      stagedVersion = null;
    } catch (_) {
      connection.textContent = "The saved result could not be loaded yet. Reconnecting automatically; your edits are kept. No new request is being sent.";
      connection.hidden = false;
    } finally {
      clearTimeout(timeout);
      rendering = false;
    }
  };
  const acceptStatus = async (data) => {
    if (data?.encounter_id !== root.dataset.encounterId || !Number.isInteger(data.revision)
        || typeof data.pending !== "boolean" || typeof data.result_version !== "string") throw new Error("invalid_status");
    const reconciledSubmission = uncertainSubmission;
    snapshot = data;
    uncertainSubmission = false;
    if (reconciledSubmission) {
      if (data.latest_job) errorNotice.hidden = true;
      else showError("No accepted request is listed for this document. Check your saved notes, then submit Generate when ready; no automatic retry was sent.");
    }
    renderStatus(data);
    if (data.revision !== initialRevision) {
      showError("This document changed in another window. Your local edits are kept. Open the current document before saving.", location.pathname);
    }
    await refreshReview(data);
  };
  const schedule = (delay) => {
    clearTimeout(timer);
    if (!stopped) timer = setTimeout(poll, delay);
  };
  const poll = async () => {
    if (posting || stopped || polling) return;
    if (!navigator.onLine) {
      connection.textContent = "You are offline. Your edits are kept. Progress will reconnect automatically; no new request will be sent.";
      connection.hidden = false;
      return;
    }
    if (document.hidden) {schedule(15000);return;}
    polling = true;
    const epoch = requestEpoch, controller = new AbortController();
    pollController = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(statusURL, {credentials:"same-origin", cache:"no-store", signal:controller.signal,
        headers:{Accept:"application/json"}});
      if (response.redirected || [401,403,404].includes(response.status)) {
        stopped = true;
        showError("Your session or access ended. Your unsaved edits are kept; sign in again before continuing.", "/login/");
        updateControls();
        return;
      }
      if (!response.ok || !(response.headers.get("content-type") || "").includes("application/json")) throw new Error("status_unavailable");
      const data = await response.json();
      if (posting || epoch !== requestEpoch) return;
      connection.hidden = true;
      await acceptStatus(data);
      failures = 0;
    } catch (error) {
      if (posting || stopped || epoch !== requestEpoch) return;
      failures += 1;
      connection.textContent = "Progress is temporarily unavailable. Reconnecting automatically; your edits are kept. No new request is being sent.";
      connection.hidden = false;
    } finally {
      clearTimeout(timeout);
      polling = false;
      if (!posting) schedule(failures ? Math.min(30000, 1500 * 2 ** Math.min(failures, 5)) : snapshot?.pending ? 1500 : 10000);
    }
  };
  generationForm?.addEventListener("submit", async (event) => {
    if (event.defaultPrevented) return; // Existing unsaved-note/audio guards run first.
    event.preventDefault();
    if (posting || uncertainSubmission || snapshot?.pending || stopped) return;
    posting = true;
    requestEpoch += 1;
    errorNotice.hidden = true;
    pollController?.abort();
    clearTimeout(timer);
    updateControls();
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(generationForm.action, {method:"POST", credentials:"same-origin", cache:"no-store",
        headers:{Accept:"application/json"}, body:new FormData(generationForm), signal:controller.signal});
      if (response.redirected || [401,403,404].includes(response.status)) {
        stopped = true;
        showError("Your session or access ended. Your unsaved edits are kept; sign in again before continuing.", "/login/");
        return;
      }
      if (!(response.headers.get("content-type") || "").includes("application/json")) throw new Error("submission_outcome_unknown");
      const data = await response.json();
      if (!response.ok) {
        showError(data.message || "The request was refused. Check the saved notes and Document record before submitting again.");
      } else {
        await acceptStatus(data);
      }
    } catch (_) {
      // A response can be lost after the server accepted a job. Reconcile with
      // GET, keeping the same source revision. Never replay POST automatically.
      uncertainSubmission = true;
      showError("The submission response was interrupted. Checking the existing request automatically; do not submit again while its status is unknown.");
    } finally {
      clearTimeout(timeout);
      posting = false;
      delete generationForm.dataset.submitting;
      const button = generationForm.querySelector("button[type=submit]");
      if (button.dataset.originalLabel) {button.textContent = button.dataset.originalLabel;button.removeAttribute("aria-disabled");}
      updateControls();
      schedule(100);
    }
  });
  showResult.addEventListener("click", () => {
    const current = document.querySelector("[data-live-review]");
    if (current && window.quillmdFormState.hasUnsavedEdits(current)) {
      previewHelp.textContent = "Save or undo your unsaved review edits first. Your current answers have not been replaced.";
      current.querySelector("textarea, input, select")?.focus();
      return;
    }
    if (snapshot) refreshReview(snapshot);
  });
  window.addEventListener("online", () => schedule(0));
  document.addEventListener("visibilitychange", () => {if (!document.hidden) schedule(0);});
  window.addEventListener("pageshow", (event) => {if (event.persisted) schedule(0);});
  window.addEventListener("pagehide", () => {clearTimeout(timer);pollController?.abort();});
  schedule(100);
})();
