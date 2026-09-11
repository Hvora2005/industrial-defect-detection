const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");
const inspectionCountEl = document.getElementById("inspectionCount");
const resultCard = document.getElementById("resultCard");
const lastUpdate = document.getElementById("lastUpdate");

let inspectionCount = 0;
let socket = null;

function setConnected(isConnected) {
  statusPill.classList.toggle("online", isConnected);
  statusPill.classList.toggle("offline", !isConnected);
  statusText.textContent = isConnected ? "LIVE" : "DISCONNECTED";
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
    <img class="result-image" src="data:image/jpeg;base64,${data.annotated_image}" alt="Latest inspection frame" />
    ${data.defects_found > 0 ? `<div class="defect-list">${defectRows}</div>` : ""}
  `;

  inspectionCount += 1;
  inspectionCountEl.textContent = inspectionCount;
  lastUpdate.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${location.host}/ws/monitor`);

  socket.addEventListener("open", () => setConnected(true));
  socket.addEventListener("close", () => {
    setConnected(false);
    setTimeout(connect, 2000); // auto-reconnect if the server restarts or Wi-Fi blips
  });
  socket.addEventListener("error", () => setConnected(false));
  socket.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    renderResult(data);
  });
}

connect();
