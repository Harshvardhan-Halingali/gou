let currentJobId = null;
let eventSource = null;
let currentDossier = null;

const TASK_DEFINITIONS = [
  { id: "PREPROCESSING", name: "Image Ingestion & Header Verification" },
  { id: "hashing_engine", name: "Multi-Algorithm Hashing (SHA-256, pHash, dHash, wHash, ColorHash, Crop)" },
  { id: "metadata_engine", name: "EXIF Extraction, Editing Tags & C2PA Credentials" },
  { id: "manipulation_ela", name: "Error Level Analysis (ELA), Noise Variance & Clone Detection" },
  { id: "sift_engine", name: "OpenCV SIFT/ORB Local Homography Keypoint Matching" },
  { id: "reverse_engine", name: "OpenCLIP Semantic Vector Index Search" },
  { id: "ai_detector", name: "AI-Generated Image & Deepfake Classifier" },
  { id: "context_osint_engine", name: "Contextual OSINT & Public Figure Incongruity Check" },
  { id: "connector_instagram", name: "Instagram Authorized Media Ingest Queue" },
  { id: "connector_facebook", name: "Facebook Pages Authorized Media Queue" },
  { id: "connector_telegram", name: "Telegram Bot Media Ingest Queue" },
  { id: "FINAL_REPORT", name: "Forensic Evidence Compilation & Dossier Synthesis" }
];

document.addEventListener("DOMContentLoaded", () => {
  initModeSwitcher();
  initDropzone();
  initAudioDropzone();
  initVideoDropzone();
  initTabs();
  renderTaskMatrix();
  checkConnectorStatus();
});

function initDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const analyzeBtn = document.getElementById("analyzeBtn");

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  analyzeBtn.addEventListener("click", () => {
    const file = fileInput.files[0];
    if (file) {
      startInvestigation(file);
    }
  });
}

function handleFileSelected(file) {
  const previewContainer = document.getElementById("previewContainer");
  const previewImg = document.getElementById("previewImg");
  const previewFilename = document.getElementById("previewFilename");
  const previewSize = document.getElementById("previewSize");
  const previewType = document.getElementById("previewType");
  const analyzeBtn = document.getElementById("analyzeBtn");

  previewFilename.textContent = file.name;
  previewSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
  previewType.textContent = file.type || "image/jpeg";

  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    previewContainer.style.display = "block";
    analyzeBtn.disabled = false;
  };
  reader.readAsDataURL(file);
}

function renderTaskMatrix() {
  const matrix = document.getElementById("taskMatrix");
  matrix.innerHTML = "";

  TASK_DEFINITIONS.forEach((t) => {
    const item = document.createElement("div");
    item.className = "task-item";
    item.id = `task-${t.id}`;
    item.innerHTML = `
      <div class="task-info">
        <span class="task-status-tag PENDING" id="tag-${t.id}">PENDING</span>
        <span>${t.name}</span>
      </div>
      <div class="task-duration" id="duration-${t.id}">--</div>
    `;
    matrix.appendChild(item);
  });
}

async function checkConnectorStatus() {
  try {
    const res = await fetch("/api/v1/connectors/status");
    const data = await res.json();
    const badges = document.getElementById("connectorBadges");
    badges.innerHTML = "";
    data.connectors.forEach((c) => {
      const b = document.createElement("span");
      b.className = `badge ${c.configured ? "online" : ""}`;
      b.textContent = `${c.platform.split(" ")[0]}: ${c.status}`;
      badges.appendChild(b);
    });
  } catch (err) {
    console.warn("Could not fetch connector status", err);
  }
}

async function startInvestigation(file) {
  const analyzeBtn = document.getElementById("analyzeBtn");
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Investigating...";

  renderTaskMatrix();
  document.getElementById("resultsContainer").style.display = "none";
  document.getElementById("progressBar").style.width = "5%";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/v1/investigate", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Upload rejected: ${err.detail || "Validation error"}`);
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Start Forensic Investigation";
      return;
    }

    const data = await res.json();
    currentJobId = data.job_id;

    // Immediately mark PREPROCESSING as COMPLETED since file upload & magic-byte validation succeeded
    updateTaskUI({
      step: "PREPROCESSING",
      status: "COMPLETED",
      elapsed_ms: 15,
      progress_pct: 10,
    });

    connectEventSource(currentJobId);
  } catch (err) {
    alert("Connection error starting investigation: " + err.message);
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Start Forensic Investigation";
  }
}

function connectEventSource(jobId) {
  if (eventSource) {
    eventSource.close();
  }

  eventSource = new EventSource(`/api/v1/stream/${jobId}`);

  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      updateTaskUI(payload);

      if (payload.step === "FINAL_REPORT" || payload.progress_pct >= 100) {
        eventSource.close();
        document.getElementById("analyzeBtn").disabled = false;
        document.getElementById("analyzeBtn").textContent = "Start New Investigation";
        loadFinalReport(jobId);
      }
    } catch (e) {
      console.error("Error parsing SSE frame", e);
    }
  };

  eventSource.onerror = (err) => {
    console.warn("EventSource stream disconnected or completed", err);
    eventSource.close();
    loadFinalReport(jobId);
  };
}

function updateTaskUI(data) {
  const step = data.step;
  const status = data.status;
  const elapsed = data.elapsed_ms;
  const pct = data.progress_pct;

  if (pct) {
    document.getElementById("progressBar").style.width = `${pct}%`;
  }

  const row = document.getElementById(`task-${step}`);
  const tag = document.getElementById(`tag-${step}`);
  const duration = document.getElementById(`duration-${step}`);

  if (row && tag) {
    row.className = `task-item ${status}`;
    tag.className = `task-status-tag ${status}`;
    tag.textContent = status;
    if (elapsed > 0 && duration) {
      duration.textContent = `${elapsed} ms`;
    }
  }
}

async function loadFinalReport(jobId) {
  try {
    const res = await fetch(`/api/v1/report/${jobId}`);
    if (!res.ok) return;
    const dossier = await res.json();
    currentDossier = dossier;
    renderDossier(dossier);
  } catch (err) {
    console.error("Failed to load final report", err);
  }
}

function renderDossier(dossier) {
  document.getElementById("resultsContainer").style.display = "block";

  // Ensure PREPROCESSING reflects completed state in the matrix
  updateTaskUI({
    step: "PREPROCESSING",
    status: "COMPLETED",
    elapsed_ms: 15,
    progress_pct: 100
  });

  // 1. Verdict & Summary
  const v = dossier.verdict || {};
  const vBanner = document.getElementById("verdictBanner");
  vBanner.className = `verdict-banner ${v.verdict_type}`;
  document.getElementById("verdictTitle").textContent = (v.verdict_type || "ASSESSMENT").replace(/_/g, " ");
  document.getElementById("verdictSummary").textContent = v.summary || "Analysis completed.";
  
  if (v.authenticity_score !== undefined && v.tamper_score !== undefined) {
    document.getElementById("verdictConfidence").innerHTML = `
      <div style="font-size: 1.15rem; color: ${v.authenticity_score >= 65 ? 'var(--accent-emerald)' : (v.authenticity_score >= 35 ? 'var(--accent-amber)' : 'var(--accent-rose)')};">
        ${v.authenticity_score >= 50 ? 'Authenticity' : 'Tamper Risk'}: ${v.authenticity_score >= 50 ? v.authenticity_score : v.tamper_score}%
      </div>
      <div style="font-size: 0.75rem; color: var(--text-dim); text-align: right; margin-top: 2px;">
        Confidence: ${(v.confidence_rating * 100).toFixed(1)}%
      </div>
    `;
  } else {
    document.getElementById("verdictConfidence").textContent = `Confidence: ${(v.confidence_rating * 100).toFixed(1)}%`;
  }

  const indList = document.getElementById("indicatorList");
  indList.innerHTML = "";
  if (v.key_indicators && v.key_indicators.length > 0) {
    v.key_indicators.forEach((ind) => {
      const li = document.createElement("li");
      li.textContent = ind;
      indList.appendChild(li);
    });
  } else {
    const li = document.createElement("li");
    li.textContent = "No adverse manipulation or duplicate matches flagged across tests.";
    indList.appendChild(li);
  }

  // Dual-Pass Synthesis Cards
  const dp = dossier.dual_pass_evaluation || {};
  const p1 = dp.pass_1_contextual_osint || {};
  const p2 = dp.pass_2_blind_forensic || {};

  if (document.getElementById("pass1Badge")) {
    const p1Badge = document.getElementById("pass1Badge");
    p1Badge.textContent = (p1.verdict || "PROCESSED").replace(/_/g, " ");
    p1Badge.className = `badge ${p1.tamper_risk >= 65 ? "failed" : "online"}`;
    document.getElementById("pass1Text").textContent = p1.details || "Context evaluation complete.";
  }

  if (document.getElementById("pass2Badge")) {
    const p2Badge = document.getElementById("pass2Badge");
    p2Badge.textContent = (p2.verdict || "PROCESSED").replace(/_/g, " ");
    p2Badge.className = `badge ${p2.blind_tamper_score >= 65 ? "failed" : "online"}`;
    document.getElementById("pass2Text").textContent = p2.details || "Blind forensic analysis complete.";
  }

  // OSINT Contextual Entity & Scenario
  const osint = dossier.context_osint || {};
  document.getElementById("osintEntity").textContent = osint.entity_identified || "None Identified";
  document.getElementById("osintRole").textContent = osint.entity_profession || osint.entity_role || "";
  if (document.getElementById("osintActivity")) {
    document.getElementById("osintActivity").textContent = osint.depicted_activity || "--";
  }
  
  if (osint.scenario_incongruity_detected) {
    document.getElementById("osintPlausibility").textContent = "IMPLAUSIBLE / FABRICATION";
    document.getElementById("osintPlausibility").style.color = "var(--accent-rose)";
  } else if (osint.scenario_aligned_detected) {
    document.getElementById("osintPlausibility").textContent = "PLAUSIBLE / AUTHENTIC VOCATION";
    document.getElementById("osintPlausibility").style.color = "var(--accent-emerald)";
  } else {
    document.getElementById("osintPlausibility").textContent = osint.entity_identified ? "PLAUSIBLE / CIVILIAN" : "NOT APPLICABLE";
    document.getElementById("osintPlausibility").style.color = "var(--accent-cyan)";
  }

  document.getElementById("osintConfidence").textContent = osint.entity_identified ? `${((osint.entity_match_confidence || 0) * 100).toFixed(1)}%` : "--";

  const alertBox = document.getElementById("osintAlertBox");
  const verifiedBox = document.getElementById("osintVerifiedBox");

  if (osint.scenario_incongruity_detected) {
    alertBox.style.display = "block";
    document.getElementById("osintConflictText").textContent = osint.conflict_explanation || "Contextual mismatch identified.";
    if (verifiedBox) verifiedBox.style.display = "none";
  } else if (osint.scenario_aligned_detected) {
    alertBox.style.display = "none";
    if (verifiedBox) {
      verifiedBox.style.display = "block";
      document.getElementById("osintVerifiedText").textContent = osint.alignment_explanation || "Authentic career alignment verified.";
    }
  } else {
    alertBox.style.display = "none";
    if (verifiedBox) verifiedBox.style.display = "none";
  }

  // 2. Hashes
  const hashes = dossier.fingerprints || {};
  const hashRows = document.getElementById("hashRows");
  hashRows.innerHTML = `
    <tr><td>SHA-256 (Bitwise Exact)</td><td class="code">${hashes.sha256 || "--"}</td></tr>
    <tr><td>pHash (Discrete Cosine Transform)</td><td class="code">${hashes.phash || "--"}</td></tr>
    <tr><td>dHash (Difference / Gradient)</td><td class="code">${hashes.dhash || "--"}</td></tr>
    <tr><td>aHash (Average Luminance)</td><td class="code">${hashes.ahash || "--"}</td></tr>
    <tr><td>wHash (Haar Wavelet DWT)</td><td class="code">${hashes.whash || "--"}</td></tr>
    <tr><td>ColorHash (Color Palette Profile)</td><td class="code">${hashes.colorhash || "--"}</td></tr>
    <tr><td>Crop-Resistant Hash (3x3 Grid Matrix)</td><td class="code">${hashes.crop_resistant_hash || "--"}</td></tr>
  `;

  // 3. ELA & Manipulation
  const fi = dossier.forensic_integrity || {};
  const ela = fi.ela || {};
  const noise = fi.noise_analysis || {};
  const copymove = fi.copy_move || {};

  document.getElementById("elaOrigImg").src = dossier.metadata ? `/static/uploads/${currentJobId}_${dossier.metadata.filename}` : "";
  document.getElementById("elaHeatmapImg").src = ela.ela_image_url || "";
  document.getElementById("elaAnomaly").textContent = ela.ela_anomaly_detected ? "POSITIVE (Anomalous variance detected)" : "NEGATIVE (Consistent compression)";
  document.getElementById("elaStats").textContent = `Mean Error: ${ela.mean_error || 0} | StdDev: ${ela.std_error || 0} | Max Error: ${ela.max_error || 0}`;
  document.getElementById("noiseInconsistency").textContent = noise.inconsistent_noise ? `YES (Ratio: ${noise.noise_inconsistency_ratio})` : `NO (Ratio: ${noise.noise_inconsistency_ratio || 0})`;
  document.getElementById("copyMoveClones").textContent = copymove.cloned_regions_found ? `YES (${copymove.candidate_matches} clusters)` : "NO";

  // 4. AI & Synthetic Analysis
  const ai = dossier.ai_generation_detection || {};
  const synthScore = ai.synthetic_likelihood !== undefined ? (ai.synthetic_likelihood * 100).toFixed(1) : "--";
  document.getElementById("aiLikelihoodScore").textContent = `${synthScore}%`;
  document.getElementById("aiClassificationBracket").textContent = (ai.classification_bracket || "INCONCLUSIVE").replace(/_/g, " ");
  document.getElementById("aiModelUsed").textContent = ai.model_name || "Organika/sdxl-detector";
  const fft = ai.fourier_spectrum_signals || {};
  document.getElementById("fftSignals").textContent = fft.fft_anomaly_detected ? `High-Freq Ratio Anomaly (${fft.high_to_low_freq_energy_ratio})` : `Normal Spectral Falloff (${fft.high_to_low_freq_energy_ratio || 0})`;

  // 5. Metadata & Provenance
  const meta = dossier.metadata_provenance || {};
  const tags = meta.tags || {};
  const metaRows = document.getElementById("metadataRows");
  metaRows.innerHTML = `
    <tr><td>Camera Make / Model</td><td>${meta.camera_make || "--"} / ${meta.camera_model || "--"}</td></tr>
    <tr><td>Date & Time Original</td><td>${meta.date_time || "--"}</td></tr>
    <tr><td>Editing Software Detected</td><td>${(meta.editing_software_detected && meta.editing_software_detected.length > 0) ? meta.editing_software_detected.join(", ") : "None Detected"}</td></tr>
    <tr><td>C2PA Content Credentials</td><td>${meta.c2pa ? meta.c2pa.details : "Not Found"}</td></tr>
    <tr><td>Total EXIF Tags Extracted</td><td>${meta.exif_tags_count || 0}</td></tr>
  `;

  // 6. Reverse Search & Matching
  const revMatches = dossier.reverse_matches || [];
  const revRows = document.getElementById("reverseMatchRows");
  if (revMatches.length > 0) {
    revRows.innerHTML = revMatches.map(m => `
      <tr>
        <td>${m.reference_file || m.matched_file || "Ref Item"}</td>
        <td>${m.source_platform || "LOCAL_ARCHIVE"}</td>
        <td>${((m.cosine_similarity || 0) * 100).toFixed(1)}%</td>
        <td>${m.match_interpretation || "SIMILARITY"}</td>
      </tr>
    `).join("");
  } else {
    revRows.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-dim);">No visual vector matches above threshold found in local verified archive.</td></tr>`;
  }
}

function initTabs() {
  const btns = document.querySelectorAll(".tab-btn");
  btns.forEach((btn) => {
    btn.addEventListener("click", () => {
      btns.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const target = btn.getAttribute("data-tab");
      const pane = document.getElementById(target);
      if (pane) pane.classList.add("active");
    });
  });

  const exportBtn = document.getElementById("exportJsonBtn");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      if (!currentDossier) return;
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentDossier, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `forensic_report_${currentJobId || "export"}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    });
  }
}

/* ==========================================================================
   AUDIO DEEPFAKE DETECTION (DF Arena 1B) INTEGRATION
   ========================================================================== */

let selectedAudioFile = null;
let currentAudioResult = null;

function initModeSwitcher() {
  const modeImageBtn = document.getElementById("modeImageBtn");
  const modeAudioBtn = document.getElementById("modeAudioBtn");
  const modeVideoBtn = document.getElementById("modeVideoBtn");
  const imageWorkspace = document.getElementById("imageWorkspace");
  const audioWorkspace = document.getElementById("audioWorkspace");
  const videoWorkspace = document.getElementById("videoWorkspace");

  if (!modeImageBtn || !modeAudioBtn || !imageWorkspace || !audioWorkspace) return;

  function setMode(mode) {
    modeImageBtn.classList.toggle("active", mode === "image");
    modeAudioBtn.classList.toggle("active", mode === "audio");
    if (modeVideoBtn) modeVideoBtn.classList.toggle("active", mode === "video");

    imageWorkspace.style.display = mode === "image" ? "block" : "none";
    audioWorkspace.style.display = mode === "audio" ? "block" : "none";
    if (videoWorkspace) videoWorkspace.style.display = mode === "video" ? "block" : "none";
  }

  modeImageBtn.addEventListener("click", () => setMode("image"));
  modeAudioBtn.addEventListener("click", () => setMode("audio"));
  if (modeVideoBtn) modeVideoBtn.addEventListener("click", () => setMode("video"));
}

function initAudioDropzone() {
  const dropzone = document.getElementById("audioDropzone");
  const fileInput = document.getElementById("audioFileInput");
  const detectBtn = document.getElementById("detectAudioBtn");

  if (!dropzone || !fileInput || !detectBtn) return;

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleAudioFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleAudioFileSelected(e.target.files[0]);
    }
  });

  detectBtn.addEventListener("click", () => {
    if (selectedAudioFile) {
      startAudioDetection(selectedAudioFile);
    }
  });
}

function handleAudioFileSelected(file) {
  selectedAudioFile = file;
  const previewContainer = document.getElementById("audioPreviewContainer");
  const audioFilename = document.getElementById("audioFilename");
  const audioMetaSize = document.getElementById("audioMetaSize");
  const audioFormatBadge = document.getElementById("audioFormatBadge");
  const audioPlayer = document.getElementById("audioPlayer");
  const detectBtn = document.getElementById("detectAudioBtn");
  const statusText = document.getElementById("audioStatusText");

  audioFilename.textContent = file.name;
  audioMetaSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB (${file.size.toLocaleString()} bytes)`;
  
  const ext = file.name.split(".").pop().toUpperCase();
  audioFormatBadge.textContent = ext || "AUDIO";

  const audioUrl = URL.createObjectURL(file);
  audioPlayer.src = audioUrl;

  previewContainer.style.display = "block";
  detectBtn.disabled = false;
  
  if (statusText) {
    statusText.textContent = `Loaded: ${file.name}. Ready for neural classification.`;
  }
}

async function startAudioDetection(file) {
  const detectBtn = document.getElementById("detectAudioBtn");
  const btnText = document.getElementById("audioBtnText");
  const statusText = document.getElementById("audioStatusText");
  const resultsContainer = document.getElementById("audioResultsContainer");

  detectBtn.disabled = true;
  btnText.innerHTML = `<span class="spinner"></span> Analyzing with DF Arena 1B...`;
  
  if (statusText) {
    statusText.textContent = "Processing audio: Resampling to 16 kHz mono & computing 48-layer Conformer embeddings...";
  }
  
  resultsContainer.style.display = "none";

  const formData = new FormData();
  formData.append("file", file);

  const startTime = performance.now();

  try {
    const res = await fetch("/api/v1/detect/audio", {
      method: "POST",
      body: formData,
    });

    const elapsedMs = Math.round(performance.now() - startTime);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown server error" }));
      alert(`Audio Detection Error: ${err.detail || err.error || "Failed to process audio"}`);
      detectBtn.disabled = false;
      btnText.textContent = "Detect Audio Deepfake";
      if (statusText) {
        statusText.textContent = "Audio processing rejected. Please upload a valid audio recording.";
      }
      return;
    }

    const data = await res.json();
    currentAudioResult = data;
    renderAudioResults(data, elapsedMs);

    detectBtn.disabled = false;
    btnText.textContent = "Detect Audio Deepfake";
    if (statusText) {
      statusText.textContent = `Classification complete (${elapsedMs} ms). Verdict: ${data.prediction.toUpperCase()}`;
    }
  } catch (err) {
    console.error("Audio detection error:", err);
    alert(`Inference connection error: ${err.message}`);
    detectBtn.disabled = false;
    btnText.textContent = "Detect Audio Deepfake";
    if (statusText) {
      statusText.textContent = "Error executing inference.";
    }
  }
}

function renderAudioResults(data, elapsedMs) {
  const resultsContainer = document.getElementById("audioResultsContainer");
  const executionTime = document.getElementById("audioExecutionTime");
  const banner = document.getElementById("audioVerdictBanner");
  const verdictTitle = document.getElementById("audioVerdictTitle");
  const verdictSummary = document.getElementById("audioVerdictSummary");
  const verdictScore = document.getElementById("audioVerdictScore");

  const spoofProbVal = document.getElementById("spoofProbVal");
  const spoofBarFill = document.getElementById("spoofBarFill");
  const bonafideProbVal = document.getElementById("bonafideProbVal");
  const bonafideBarFill = document.getElementById("bonafideBarFill");

  const metaRows = document.getElementById("audioMetaRows");
  const chunksWrap = document.getElementById("audioChunksWrap");
  const chunkRows = document.getElementById("audioChunkRows");

  executionTime.textContent = `${elapsedMs} ms`;

  // Safely extract probabilities
  const spoofP = Number(data.spoof_probability ?? (data.spoof_percentage != null ? data.spoof_percentage / 100 : 0));
  const bonafideP = Number(data.bonafide_probability ?? (data.bonafide_percentage != null ? data.bonafide_percentage / 100 : 0));

  const spoofPct = (spoofP * 100).toFixed(2);
  const bonafidePct = (bonafideP * 100).toFixed(2);
  const isSpoof = (data.prediction || "").toLowerCase() === "spoof" || spoofP >= 0.50;

  if (isSpoof) {
    banner.style.background = "linear-gradient(90deg, rgba(255, 23, 68, 0.15), rgba(0, 0, 0, 0.4))";
    banner.style.borderColor = "var(--accent-rose)";
    verdictTitle.textContent = "SUSPICIOUS / SPOOFED AUDIO DETECTED";
    verdictTitle.style.color = "var(--accent-rose)";
    verdictSummary.textContent = "High probability of speech synthesis, text-to-speech (TTS), or generative voice cloning.";
    verdictScore.textContent = `${spoofPct}% SPOOF`;
    verdictScore.style.color = "var(--accent-rose)";
  } else {
    banner.style.background = "linear-gradient(90deg, rgba(0, 230, 118, 0.15), rgba(0, 0, 0, 0.4))";
    banner.style.borderColor = "var(--accent-emerald)";
    verdictTitle.textContent = "GENUINE / BONAFIDE AUDIO VERIFIED";
    verdictTitle.style.color = "var(--accent-emerald)";
    verdictSummary.textContent = "Acoustic signatures match natural human vocal tract dynamics and biological timbre.";
    verdictScore.textContent = `${bonafidePct}% BONAFIDE`;
    verdictScore.style.color = "var(--accent-emerald)";
  }

  // Update probability meters with exact percentages
  spoofProbVal.textContent = `${spoofPct}%`;
  spoofBarFill.style.width = `${Math.min(100, Math.max(0, spoofP * 100))}%`;

  bonafideProbVal.textContent = `${bonafidePct}%`;
  bonafideBarFill.style.width = `${Math.min(100, Math.max(0, bonafideP * 100))}%`;

  // Duration formatting safely
  const rawDur = data.duration_seconds ?? data.audio_metadata?.duration_seconds;
  const durStr = rawDur != null ? `${Number(rawDur).toFixed(2)} seconds` : "--";

  // Populate technical parameter table
  metaRows.innerHTML = `
    <tr><td>Neural Model</td><td><strong>${data.model || "DF Arena 1B Fine-tuned"}</strong></td></tr>
    <tr><td>Backbone Architecture</td><td>${data.architecture || "DF_Arena_1B_Antispoofing (Wav2Vec2 + 48-Layer Conformer)"}</td></tr>
    <tr><td>Restored Fine-Tuned Layer</td><td><code>${data.fine_tuned_layer || "model.backbone.conformer.fc5"}</code></td></tr>
    <tr><td>Spoof Likelihood (Class 0)</td><td><strong style="color: var(--accent-rose); font-size: 1rem;">${spoofPct}%</strong></td></tr>
    <tr><td>Bonafide Likelihood (Class 1)</td><td><strong style="color: var(--accent-emerald); font-size: 1rem;">${bonafidePct}%</strong></td></tr>
    <tr><td>Audio Duration Evaluated</td><td>${durStr}</td></tr>
    <tr><td>Model Ingestion Sample Rate</td><td>${data.sample_rate || 16000} Hz (Mono Float32)</td></tr>
    <tr><td>Evaluated Sliding Windows</td><td>${data.num_chunks_evaluated || data.audio_metadata?.chunk_count || 1} window(s) (64,600 samples / ~4.04s each)</td></tr>
    <tr><td>File Name</td><td>${data.filename || data.file_name || "audio"}</td></tr>
    <tr><td>Empirical Interpretation</td><td>${data.summary || data.interpretation || "--"}</td></tr>
  `;

  // Populate chunk breakdown if multiple chunks or chunk detail exists
  const chunks = data.chunk_predictions || [];
  if (chunks.length > 0) {
    chunksWrap.style.display = "block";
    chunkRows.innerHTML = chunks.map((c, i) => {
      const cIndex = c.chunk_index != null ? c.chunk_index : (i + 1);
      const startT = Number(c.start_time_sec ?? 0).toFixed(2);
      const endT = Number(c.end_time_sec ?? 0).toFixed(2);
      const cSpoof = Number(c.spoof_probability ?? c.spoof_prob ?? 0);
      const cBonafide = Number(c.bonafide_probability ?? c.bonafide_prob ?? 0);
      const cSpoofPct = (cSpoof * 100).toFixed(2);
      const cBonafidePct = (cBonafide * 100).toFixed(2);
      const cPred = (c.prediction || (cSpoof >= 0.50 ? "spoof" : "bonafide")).toUpperCase();

      return `
        <tr>
          <td>Window #${cIndex} (${startT}s - ${endT}s)</td>
          <td style="color: var(--accent-rose); font-family: var(--font-mono); font-weight: 600;">${cSpoofPct}%</td>
          <td style="color: var(--accent-emerald); font-family: var(--font-mono); font-weight: 600;">${cBonafidePct}%</td>
          <td>
            <span class="badge ${cPred === 'BONAFIDE' ? 'online' : ''}" style="${cPred === 'SPOOF' ? 'border-color: rgba(255,23,68,0.5); color: var(--accent-rose);' : ''}">
              ${cPred}
            </span>
          </td>
        </tr>
      `;
    }).join("");
  } else {
    chunksWrap.style.display = "none";
  }

  resultsContainer.style.display = "block";
}

/* ==========================================================================
   VIDEO DEEPFAKE DETECTION (HongguLiu / FaceForensics++) INTEGRATION
   ========================================================================== */

let selectedVideoFile = null;
let currentVideoResult = null;

function initVideoDropzone() {
  const dropzone = document.getElementById("videoDropzone");
  const fileInput = document.getElementById("videoFileInput");
  const detectBtn = document.getElementById("detectVideoBtn");

  if (!dropzone || !fileInput || !detectBtn) return;

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleVideoFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleVideoFileSelected(e.target.files[0]);
    }
  });

  detectBtn.addEventListener("click", () => {
    if (selectedVideoFile) {
      startVideoDetection(selectedVideoFile);
    }
  });
}

function handleVideoFileSelected(file) {
  selectedVideoFile = file;
  const previewContainer = document.getElementById("videoPreviewContainer");
  const videoFilename = document.getElementById("videoFilename");
  const videoMetaSize = document.getElementById("videoMetaSize");
  const videoFormatBadge = document.getElementById("videoFormatBadge");
  const videoPlayer = document.getElementById("videoPlayer");
  const detectBtn = document.getElementById("detectVideoBtn");
  const statusText = document.getElementById("videoStatusText");
  const metaDuration = document.getElementById("videoMetaDuration");
  const metaResolution = document.getElementById("videoMetaResolution");
  const metaFps = document.getElementById("videoMetaFps");

  videoFilename.textContent = file.name;
  videoMetaSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB (${file.size.toLocaleString()} bytes)`;
  
  const ext = file.name.split(".").pop().toUpperCase();
  videoFormatBadge.textContent = ext || "VIDEO";

  const videoUrl = URL.createObjectURL(file);
  videoPlayer.src = videoUrl;

  videoPlayer.onloadedmetadata = () => {
    if (metaDuration) metaDuration.textContent = `Duration: ${videoPlayer.duration ? videoPlayer.duration.toFixed(1) + 's' : '--'}`;
    if (metaResolution) metaResolution.textContent = `Res: ${videoPlayer.videoWidth}x${videoPlayer.videoHeight}`;
    if (metaFps) metaFps.textContent = `Type: ${file.type || 'video/mp4'}`;
  };

  previewContainer.style.display = "block";
  detectBtn.disabled = false;
  
  if (statusText) {
    statusText.textContent = `Loaded: ${file.name}. Ready for neural video inference.`;
  }
}

async function startVideoDetection(file) {
  const detectBtn = document.getElementById("detectVideoBtn");
  const btnText = document.getElementById("videoBtnText");
  const statusText = document.getElementById("videoStatusText");
  const resultsContainer = document.getElementById("videoResultsContainer");
  const scanOverlay = document.getElementById("videoScanOverlay");

  detectBtn.disabled = true;
  btnText.innerHTML = `<span class="spinner"></span> Scanning Video Frames (FaceForensics++)...`;
  
  // Activate visual neural scanning animation over the video preview
  if (scanOverlay) {
    scanOverlay.style.display = "block";
  }

  if (statusText) {
    statusText.textContent = "Processing: Sampling frames & executing YuNet face extraction & Xception analysis...";
  }
  
  resultsContainer.style.display = "none";

  const formData = new FormData();
  formData.append("file", file);

  const startTime = performance.now();

  try {
    const res = await fetch("/api/v1/detect/video", {
      method: "POST",
      body: formData,
    });

    const elapsedMs = Math.round(performance.now() - startTime);

    // Stop scanning animation overlay
    if (scanOverlay) {
      scanOverlay.style.display = "none";
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown server error" }));
      alert(`Video Detection Error: ${err.detail || err.error || "Failed to process video"}`);
      detectBtn.disabled = false;
      btnText.textContent = "Detect Video Deepfake";
      if (statusText) {
        statusText.textContent = "Video analysis rejected. Please check video codec and format.";
      }
      return;
    }

    const data = await res.json();
    currentVideoResult = data;
    renderVideoResults(data, elapsedMs);

    detectBtn.disabled = false;
    btnText.textContent = "Detect Video Deepfake";
    if (statusText) {
      statusText.textContent = `Analysis complete (${elapsedMs} ms). Verdict: ${data.verdict_badge || (data.is_bonafide ? "BONAFIDE" : "SPOOF")}`;
    }
  } catch (err) {
    console.error("Video detection error:", err);
    if (scanOverlay) {
      scanOverlay.style.display = "none";
    }
    alert(`Inference connection error: ${err.message}`);
    detectBtn.disabled = false;
    btnText.textContent = "Detect Video Deepfake";
    if (statusText) {
      statusText.textContent = "Connection error during video inference.";
    }
  }
}

function renderVideoResults(data, elapsedMs) {
  const resultsContainer = document.getElementById("videoResultsContainer");
  const executionTime = document.getElementById("videoExecutionTime");
  const banner = document.getElementById("videoVerdictBanner");
  const verdictTitle = document.getElementById("videoVerdictTitle");
  const verdictSummary = document.getElementById("videoVerdictSummary");
  const verdictScore = document.getElementById("videoVerdictScore");

  // Dual Model Gauge Elements
  const aiBadge = document.getElementById("videoAiBadge");
  const aiSpoofVal = document.getElementById("videoAiSpoofVal");
  const aiSpoofBar = document.getElementById("videoAiSpoofBar");
  const aiBonafideVal = document.getElementById("videoAiBonafideVal");
  const aiBonafideBar = document.getElementById("videoAiBonafideBar");

  const dfBadge = document.getElementById("videoDfBadge");
  const dfSpoofVal = document.getElementById("videoDfSpoofVal");
  const dfSpoofBar = document.getElementById("videoDfSpoofBar");
  const dfBonafideVal = document.getElementById("videoDfBonafideVal");
  const dfBonafideBar = document.getElementById("videoDfBonafideBar");

  const metaRows = document.getElementById("videoMetaRows");
  const frameRows = document.getElementById("videoFrameRows");

  executionTime.textContent = `${elapsedMs} ms`;

  // Extract Dual Model Percentages
  const spoofAiNum = Number(data.spoof_ai_percentage ?? 0);
  const bonafideAiNum = Number(data.bonafide_ai_percentage ?? (100 - spoofAiNum));
  const spoofDfNum = Number(data.spoof_deepfake_percentage ?? 0);
  const bonafideDfNum = Number(data.bonafide_deepfake_percentage ?? (100 - spoofDfNum));

  const isBonafide = Boolean(data.is_bonafide ?? (spoofAiNum < 50.0 && spoofDfNum < 50.0));
  const isAiGenerated = spoofAiNum >= 50.0;
  const isDeepfake = spoofDfNum >= 50.0;

  // 1. Update AI-Generated Video Meter (DeMamba)
  if (aiSpoofVal && aiSpoofBar && aiBonafideVal && aiBonafideBar) {
    aiSpoofVal.textContent = `${spoofAiNum.toFixed(2)}%`;
    aiSpoofBar.style.width = `${Math.min(100, Math.max(0, spoofAiNum))}%`;

    aiBonafideVal.textContent = `${bonafideAiNum.toFixed(2)}%`;
    aiBonafideBar.style.width = `${Math.min(100, Math.max(0, bonafideAiNum))}%`;

    if (aiBadge) {
      if (isAiGenerated) {
        aiBadge.textContent = "SPOOF (AI GENERATED)";
        aiBadge.className = "badge";
        aiBadge.style.borderColor = "var(--accent-rose)";
        aiBadge.style.color = "var(--accent-rose)";
      } else {
        aiBadge.textContent = "BONAFIDE (CAMERA)";
        aiBadge.className = "badge online";
        aiBadge.style.borderColor = "var(--accent-cyan)";
        aiBadge.style.color = "var(--accent-cyan)";
      }
    }
  }

  // 2. Update Deepfake Facial Manipulation Meter (GenD)
  if (dfSpoofVal && dfSpoofBar && dfBonafideVal && dfBonafideBar) {
    dfSpoofVal.textContent = `${spoofDfNum.toFixed(2)}%`;
    dfSpoofBar.style.width = `${Math.min(100, Math.max(0, spoofDfNum))}%`;

    dfBonafideVal.textContent = `${bonafideDfNum.toFixed(2)}%`;
    dfBonafideBar.style.width = `${Math.min(100, Math.max(0, bonafideDfNum))}%`;

    if (dfBadge) {
      if (isDeepfake) {
        dfBadge.textContent = "SPOOF (DEEPFAKE)";
        dfBadge.className = "badge";
        dfBadge.style.borderColor = "var(--accent-rose)";
        dfBadge.style.color = "var(--accent-rose)";
      } else {
        dfBadge.textContent = "BONAFIDE (HUMAN)";
        dfBadge.className = "badge online";
        dfBadge.style.borderColor = "var(--accent-emerald)";
        dfBadge.style.color = "var(--accent-emerald)";
      }
    }
  }

  // 3. Verdict Banner Update
  if (isBonafide) {
    banner.style.background = "linear-gradient(90deg, rgba(0, 230, 118, 0.18), rgba(0, 0, 0, 0.5))";
    banner.style.borderColor = "var(--accent-emerald)";
    verdictTitle.textContent = "BONAFIDE &bull; GENUINE HUMAN / REAL CAMERA RECORDING";
    verdictTitle.style.color = "var(--accent-emerald)";
    verdictSummary.textContent = "Camera optical capture verified by DeMamba and natural human biometrics verified by GenD.";
    verdictScore.textContent = `${Math.min(bonafideAiNum, bonafideDfNum).toFixed(2)}% BONAFIDE`;
    verdictScore.style.color = "var(--accent-emerald)";
  } else if (isAiGenerated && isDeepfake) {
    banner.style.background = "linear-gradient(90deg, rgba(255, 23, 68, 0.2), rgba(0, 0, 0, 0.5))";
    banner.style.borderColor = "var(--accent-rose)";
    verdictTitle.textContent = "SPOOF &bull; AI-GENERATED VIDEO & FACIAL DEEPFAKE";
    verdictTitle.style.color = "var(--accent-rose)";
    verdictSummary.textContent = "Both synthetic generative models (Sora/Gen-2) and facial reenactment artifacts detected.";
    verdictScore.textContent = `${Math.max(spoofAiNum, spoofDfNum).toFixed(2)}% SPOOF`;
    verdictScore.style.color = "var(--accent-rose)";
  } else if (isAiGenerated) {
    banner.style.background = "linear-gradient(90deg, rgba(255, 23, 68, 0.18), rgba(0, 0, 0, 0.5))";
    banner.style.borderColor = "var(--accent-cyan)";
    verdictTitle.textContent = "SPOOF &bull; AI-GENERATED VIDEO DETECTED";
    verdictTitle.style.color = "var(--accent-cyan)";
    verdictSummary.textContent = "DeMamba identified temporal & spatial signatures characteristic of synthetic video diffusion models.";
    verdictScore.textContent = `${spoofAiNum.toFixed(2)}% SPOOF AI`;
    verdictScore.style.color = "var(--accent-cyan)";
  } else {
    banner.style.background = "linear-gradient(90deg, rgba(255, 23, 68, 0.18), rgba(0, 0, 0, 0.5))";
    banner.style.borderColor = "var(--accent-rose)";
    verdictTitle.textContent = "SPOOF &bull; DEEPFAKE FACIAL MANIPULATION DETECTED";
    verdictTitle.style.color = "var(--accent-rose)";
    verdictSummary.textContent = "GenD identified facial swap, reenactment, or boundary blending inconsistencies.";
    verdictScore.textContent = `${spoofDfNum.toFixed(2)}% SPOOF DEEPFAKE`;
    verdictScore.style.color = "var(--accent-rose)";
  }

  // Duration formatting safely
  const rawDur = data.duration_seconds;
  const durStr = rawDur != null ? `${Number(rawDur).toFixed(2)} seconds` : "--";

  // 4. Populate Technical Parameter Table
  metaRows.innerHTML = `
    <tr><td>Dual Neural Pipeline</td><td><strong>DeMamba (GenVideo-100K) + GenD CLIP-L/14 (WACV 2026)</strong></td></tr>
    <tr><td>Overall Status</td><td><strong style="color: ${isBonafide ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; font-size: 1.05rem;">${data.verdict_badge || (isBonafide ? "BONAFIDE" : "SPOOF")}</strong></td></tr>
    <tr><td>AI-Generated Video Score (DeMamba)</td><td>Spoof AI: <strong style="color: var(--accent-rose);">${spoofAiNum.toFixed(2)}%</strong> &bull; Bonafide: <strong style="color: var(--accent-emerald);">${bonafideAiNum.toFixed(2)}%</strong></td></tr>
    <tr><td>Facial Deepfake Score (GenD)</td><td>Spoof Deepfake: <strong style="color: var(--accent-rose);">${spoofDfNum.toFixed(2)}%</strong> &bull; Bonafide: <strong style="color: var(--accent-emerald);">${bonafideDfNum.toFixed(2)}%</strong></td></tr>
    <tr><td>Video Duration & Resolution</td><td>${durStr} &bull; ${data.resolution || "--"} (${data.fps || "--"} FPS)</td></tr>
    <tr><td>Frames Analyzed</td><td>${data.frames_analyzed || 0} frames sampled (across ${data.total_frames_in_video || "--"} total frames)</td></tr>
    <tr><td>Faces Detected by YuNet</td><td>${data.faces_detected_count || 0} facial instance(s) (${data.low_res_faces_count || 0} low-resolution)</td></tr>
    <tr><td>Model Links</td><td>
      <a href="https://huggingface.co/Ahsanz/DeMamba-GenVideo100K" target="_blank" style="color: var(--accent-cyan); text-decoration: underline;">DeMamba (GenVideo-100K)</a> &bull; 
      <a href="https://huggingface.co/collections/yermandy/gend" target="_blank" style="color: var(--accent-emerald); text-decoration: underline;">GenD (WACV 2026)</a>
    </td></tr>
    <tr><td>Forensic Synthesis</td><td>${data.summary || data.interpretation || "--"}</td></tr>
  `;

  // 5. Populate Temporal Frame Breakdown Table
  const frames = data.frame_predictions || [];
  if (frames.length > 0) {
    frameRows.innerHTML = frames.map((f) => {
      const fIdx = f.frame_index != null ? f.frame_index : 0;
      const tSec = Number(f.timestamp_sec ?? 0).toFixed(2);
      const isNoFace = !f.face_detected || f.verdict === "NO_FACE";
      const isDfSpoof = (f.verdict || "").toUpperCase() === "SPOOF_DEEPFAKE";

      const fSpoof = !isNoFace && f.spoof_deepfake_percentage != null ? `${Number(f.spoof_deepfake_percentage).toFixed(2)}%` : "—";
      const fReal = !isNoFace && f.bonafide_facial_percentage != null ? `${Number(f.bonafide_facial_percentage).toFixed(2)}%` : "—";

      let boxStr = "Bypassed (Background)";
      if (f.face_detected && f.bounding_box) {
        boxStr = `[${f.bounding_box.x}, ${f.bounding_box.y}, ${f.bounding_box.w}x${f.bounding_box.h}]`;
      }

      let badgeHtml = "";
      if (isNoFace) {
        badgeHtml = `<span class="badge" style="border-color: rgba(255,255,255,0.15); color: var(--text-dim); background: rgba(255,255,255,0.03);">NO FACE</span>`;
      } else if (isDfSpoof) {
        badgeHtml = `<span class="badge" style="border-color: rgba(255,23,68,0.5); color: var(--accent-rose); background: rgba(255,23,68,0.1);">SPOOF</span>`;
      } else {
        badgeHtml = `<span class="badge online" style="border-color: rgba(0,230,118,0.5); color: var(--accent-emerald); background: rgba(0,230,118,0.1);">BONAFIDE</span>`;
      }

      return `
        <tr>
          <td>Frame #${fIdx}</td>
          <td>${tSec}s</td>
          <td>
            <span style="font-size: 0.8rem; color: ${f.face_detected ? 'var(--accent-emerald)' : 'var(--text-dim)'};">
              ${f.face_detected ? '✓ Face (' + ((f.face_confidence || 1) * 100).toFixed(0) + '%)' : 'No Face'}
            </span>
            ${f.low_res ? '<span style="font-size: 0.7rem; color: #ffb300; background: rgba(255,179,0,0.1); border: 1px solid rgba(255,179,0,0.3); border-radius: 3px; padding: 1px 4px; margin-left: 4px;">Low-Res</span>' : ''}
            <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-dim); margin-left: 6px;">${boxStr}</span>
          </td>
          <td style="color: ${!isNoFace ? 'var(--accent-rose)' : 'var(--text-dim)'}; font-family: var(--font-mono); font-weight: 600;">${fSpoof}</td>
          <td style="color: ${!isNoFace ? 'var(--accent-emerald)' : 'var(--text-dim)'}; font-family: var(--font-mono); font-weight: 600;">${fReal}</td>
          <td>${badgeHtml}</td>
        </tr>
      `;
    }).join("");
  } else {
    frameRows.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim);">No individual frames recorded.</td></tr>`;
  }

  resultsContainer.style.display = "block";
}
