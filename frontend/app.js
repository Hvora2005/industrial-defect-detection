const API_BASE = window.location.origin;

const video = document.getElementById("video");
const frozenFrame = document.getElementById("frozenFrame");
const cameraPlaceholder = document.getElementById("cameraPlaceholder");
const viewfinder = document.getElementById("viewfinder");
const recIndicator = document.getElementById("recIndicator");
const processingBanner = document.getElementById("processingBanner");

const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const captureBtn = document.getElementById("captureBtn");
const liveModeBtn = document.getElementById("liveModeBtn");
const uploadInput = document.getElementById("uploadInput");

const LIVE_MODE_INTERVAL_MS = 2000; // frame-skipping: send at most one frame every 2s
let liveModeTimer = null;
let liveModeBusy = false; // skip a tick if the previous frame is still being processed

const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");
const inspectionCountEl = document.getElementById("inspectionCount");
const resultCard = document.getElementById("resultCard");

let mediaStream = null;
let inspectionCount = 0;

// Hidden canvas used only to grab a still frame from the live video
const captureCanvas = document.createElement("canvas");

function setCameraUiState(isRunning) {
  video.style.display = isRunning ? "block" : "none";
  cameraPlaceholder.style.display = isRunning ? "none" : "flex";
  viewfinder.classList.toggle("active", isRunning);
  recIndicator.style.display = isRunning ? "flex" : "none";
  recIndicator.classList.toggle("live", isRunning);
  startBtn.disabled = isRunning;
  stopBtn.disabled = !isRunning;
  captureBtn.disabled = !isRunning;
  liveModeBtn.disabled = !isRunning;
  frozenFrame.style.display = "none";
  if (!isRunning) stopLiveMode();
}

function startLiveMode() {
  liveModeBtn.classList.add("active");
  liveModeBtn.querySelector("svg").nextSibling.textContent = " Live Mode: ON";
  liveModeTimer = setInterval(async () => {
    if (liveModeBusy || !mediaStream) return;
    liveModeBusy = true;
    try {
      const blob = await captureFrameAsBlob();
      frozenFrame.src = URL.createObjectURL(blob);
      await runInspection(blob, "/detect");
    } finally {
      liveModeBusy = false;
    }
  }, LIVE_MODE_INTERVAL_MS);
}

function stopLiveMode() {
  if (liveModeTimer) {
    clearInterval(liveModeTimer);
    liveModeTimer = null;
  }
  liveModeBusy = false;
  liveModeBtn.classList.remove("active");
  const textNode = liveModeBtn.querySelector("svg").nextSibling;
  if (textNode) textNode.textContent = " Live Mode: OFF";
}

function toggleLiveMode() {
  if (liveModeTimer) {
    stopLiveMode();
  } else {
    startLiveMode();
  }
}

async function startCamera() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      // Cap the requested resolution: full phone-camera resolution (often
      // 1080p-4K) makes every frame several MB, which is what causes the
      // lag over Wi-Fi. 960x720 is plenty for defect visibility.
      video: { facingMode: "environment", width: { ideal: 960 }, height: { ideal: 720 } },
      audio: false,
    });
    video.srcObject = mediaStream;
    setCameraUiState(true);
  } catch (err) {
    let message = "Could not access the camera.";
    if (err.name === "NotAllowedError") {
      message = "Camera permission denied. Allow camera access in your browser's site settings and try again.";
    } else if (err.name === "NotFoundError") {
      message = "No camera found on this device.";
    } else if (location.protocol !== "https:" && location.hostname !== "localhost") {
      message = "Camera access needs a secure (HTTPS) connection on phones. See the setup notes for this project.";
    }
    showError(message);
  }
}

function stopCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  setCameraUiState(false);
}

const MAX_CAPTURE_DIMENSION = 640; // longest side, px - keeps upload/response payloads small

function captureFrameAsBlob() {
  const scale = Math.min(1, MAX_CAPTURE_DIMENSION / Math.max(video.videoWidth, video.videoHeight));
  captureCanvas.width = Math.round(video.videoWidth * scale);
  captureCanvas.height = Math.round(video.videoHeight * scale);
  const ctx = captureCanvas.getContext("2d");
  ctx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
  return new Promise((resolve) => {
    captureCanvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.8);
  });
}

async function captureAndInspect() {
  processingBanner.classList.add("active");
  captureBtn.disabled = true;
  try {
    const blob = await captureFrameAsBlob();
    frozenFrame.src = URL.createObjectURL(blob);
    await runInspection(blob, "/detect");
  } finally {
    processingBanner.classList.remove("active");
    captureBtn.disabled = !mediaStream;
  }
}

async function uploadAndInspect(file) {
  processingBanner.classList.add("active");
  try {
    await runInspection(file, "/upload");
  } finally {
    processingBanner.classList.remove("active");
  }
}

async function runInspection(imageBlob, endpoint) {
  const formData = new FormData();
  formData.append("file", imageBlob, "frame.jpg");

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }
    const data = await response.json();
    inspectionCount += 1;
    inspectionCountEl.textContent = inspectionCount;
    renderResult(data);
  } catch (err) {
    showError("Could not reach the inspection server. Check that the laptop server is running and the phone is on the same Wi-Fi.");
  }
}

function renderResult(data) {
  const isPass = data.status === "PASS";

  const defectRows = data.defects
    .map(
      (d) => `
        <div class="defect-row">
          <span class="defect-name">${d.class_name.replace(/_/g, " ").replace(/-/g, " ")}</span>
          <span class="defect-right">
            <span class="severity-badge ${d.severity.toLowerCase()}">${d.severity}</span>
            <span class="defect-conf">${d.confidence.toFixed(1)}%</span>
          </span>
        </div>`
    )
    .join("");

  const severityNote = data.severity
    ? `<span class="severity-badge ${data.severity.toLowerCase()}">${data.severity}</span>`
    : "";

  resultCard.innerHTML = `
    <div class="result-status-row">
      <span class="result-status-badge ${isPass ? "pass" : "fail"}">${isPass ? "PASS" : "FAIL"}</span>
      <span class="result-count">DEFECTS FOUND: <strong>${data.defects_found}</strong> ${severityNote}</span>
    </div>
    <img class="result-image" src="data:image/jpeg;base64,${data.annotated_image}" alt="Annotated inspection result" />
    ${data.defects_found > 0 ? `<div class="defect-list">${defectRows}</div>` : ""}
  `;
}

function showError(message) {
  resultCard.innerHTML = `<div class="result-error">${message}</div>`;
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) throw new Error();
    const data = await response.json();
    statusPill.classList.remove("offline");
    statusPill.classList.add("online");
    statusText.textContent = data.model_loaded ? "MODEL READY" : "MODEL LOADING";
  } catch (err) {
    statusPill.classList.remove("online");
    statusPill.classList.add("offline");
    statusText.textContent = "SERVER OFFLINE";
  }
}

startBtn.addEventListener("click", startCamera);
stopBtn.addEventListener("click", stopCamera);
captureBtn.addEventListener("click", captureAndInspect);
liveModeBtn.addEventListener("click", toggleLiveMode);
uploadInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) uploadAndInspect(file);
  uploadInput.value = "";
});

checkHealth();
