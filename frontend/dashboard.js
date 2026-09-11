const REFRESH_INTERVAL_MS = 5000;

function formatDefectName(name) {
  return name.replace(/_/g, " ").replace(/-/g, " ");
}

function renderStats(stats) {
  document.getElementById("statTotal").textContent = stats.total_inspected;
  document.getElementById("statPass").textContent = stats.pass_count;
  document.getElementById("statFail").textContent = stats.fail_count;
  document.getElementById("statRate").textContent = `${stats.defect_rate}%`;
  document.getElementById("statCommon").textContent = stats.most_common_defect
    ? formatDefectName(stats.most_common_defect)
    : "None";
  document.getElementById("statAvgConf").textContent =
    stats.avg_confidence != null ? `${stats.avg_confidence}%` : "—";

  renderPassFailChart(stats.pass_count, stats.fail_count);
  renderDefectChart(stats.defect_distribution);
  renderSeverityChart(stats.severity_distribution);
}

function renderSeverityChart(severity) {
  const container = document.getElementById("severityChart");
  const levels = [
    { key: "MINOR", cls: "minor" },
    { key: "MAJOR", cls: "major" },
    { key: "CRITICAL", cls: "critical" },
  ];
  const counts = levels.map((l) => (severity ? severity[l.key] || 0 : 0));
  const max = Math.max(...counts, 1);

  container.innerHTML = levels
    .map(
      (l, i) => `
        <div class="bar-row">
          <div class="bar-row-label">${l.key}</div>
          <div class="bar-track"><div class="bar-fill ${l.cls}" style="width:${(counts[i] / max) * 100}%"></div></div>
          <div class="bar-row-value">${counts[i]}</div>
        </div>`
    )
    .join("");
}

function renderPassFailChart(passCount, failCount) {
  const max = Math.max(passCount, failCount, 1);
  const container = document.getElementById("passFailChart");
  container.innerHTML = `
    <div class="bar-row">
      <div class="bar-row-label">PASS</div>
      <div class="bar-track"><div class="bar-fill pass" style="width:${(passCount / max) * 100}%"></div></div>
      <div class="bar-row-value">${passCount}</div>
    </div>
    <div class="bar-row">
      <div class="bar-row-label">FAIL</div>
      <div class="bar-track"><div class="bar-fill fail" style="width:${(failCount / max) * 100}%"></div></div>
      <div class="bar-row-value">${failCount}</div>
    </div>
  `;
}

function renderDefectChart(distribution) {
  const container = document.getElementById("defectChart");
  const entries = Object.entries(distribution || {}).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    container.innerHTML = `<div class="result-empty">No defects logged yet.</div>`;
    return;
  }

  const max = entries[0][1];
  container.innerHTML = entries
    .map(
      ([name, count]) => `
        <div class="bar-row">
          <div class="bar-row-label">${formatDefectName(name)}</div>
          <div class="bar-track"><div class="bar-fill accent" style="width:${(count / max) * 100}%"></div></div>
          <div class="bar-row-value">${count}</div>
        </div>`
    )
    .join("");
}

function renderHistory(inspections) {
  const container = document.getElementById("historyList");

  if (inspections.length === 0) {
    container.innerHTML = `<div class="result-empty">No inspections yet.</div>`;
    return;
  }

  container.innerHTML = inspections
    .map((insp) => {
      const time = new Date(insp.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      const isPass = insp.status === "PASS";
      const defectLabel = insp.primary_defect ? formatDefectName(insp.primary_defect) : "-";
      const conf = insp.primary_confidence != null ? `${insp.primary_confidence.toFixed(1)}%` : "";
      const severityBadge = insp.severity
        ? `<span class="severity-badge ${insp.severity.toLowerCase()}">${insp.severity}</span>`
        : "<span></span>";
      return `
        <div class="history-row">
          <span class="history-time">${time}</span>
          <span class="history-badge ${isPass ? "pass" : "fail"}">${isPass ? "PASS" : "FAIL"}</span>
          ${severityBadge}
          <span class="history-defect">${defectLabel}</span>
          <span class="history-conf">${conf}</span>
        </div>`;
    })
    .join("");
}

function renderTrendChart(buckets) {
  const wrap = document.getElementById("trendChartWrap");

  if (!buckets || buckets.length < 2) {
    wrap.innerHTML = `<div class="result-empty">Not enough data yet — keep inspecting to build the trend.</div>`;
    return;
  }

  const width = 320;
  const height = 100;
  const padTop = 10;
  const padBottom = 18;
  const padRight = 34; // room for end labels
  const plotHeight = height - padTop - padBottom;

  const maxCount = Math.max(...buckets.map((b) => Math.max(b.pass, b.fail)), 1);
  const stepX = (width - padRight) / (buckets.length - 1);

  const xAt = (i) => i * stepX;
  const yAt = (v) => padTop + plotHeight - (v / maxCount) * plotHeight;

  const buildPath = (key) =>
    buckets.map((b, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(b[key]).toFixed(1)}`).join(" ");

  const buildDots = (key, cls) =>
    buckets
      .map((b, i) => `<circle class="trend-dot ${cls}" cx="${xAt(i).toFixed(1)}" cy="${yAt(b[key]).toFixed(1)}" r="2.5" />`)
      .join("");

  const lastIdx = buckets.length - 1;
  const firstLabel = buckets[0].time;
  const lastLabel = buckets[lastIdx].time;
  const midLabel = buckets[Math.floor(lastIdx / 2)].time;
  const midX = xAt(Math.floor(lastIdx / 2));

  const svg = `
    <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <line class="trend-baseline" x1="0" y1="${(padTop + plotHeight).toFixed(1)}" x2="${width - padRight}" y2="${(padTop + plotHeight).toFixed(1)}" />
      <path class="trend-line pass" d="${buildPath("pass")}" />
      <path class="trend-line fail" d="${buildPath("fail")}" />
      ${buildDots("pass", "pass")}
      ${buildDots("fail", "fail")}
      <text class="trend-end-label pass" x="${(width - padRight + 5).toFixed(1)}" y="${yAt(buckets[lastIdx].pass).toFixed(1) - 2}">${buckets[lastIdx].pass}</text>
      <text class="trend-end-label fail" x="${(width - padRight + 5).toFixed(1)}" y="${yAt(buckets[lastIdx].fail).toFixed(1) + 8}">${buckets[lastIdx].fail}</text>
      <text class="trend-label" x="0" y="${height - 4}" text-anchor="start">${firstLabel}</text>
      <text class="trend-label" x="${midX.toFixed(1)}" y="${height - 4}" text-anchor="middle">${midLabel}</text>
      <text class="trend-label" x="${(width - padRight).toFixed(1)}" y="${height - 4}" text-anchor="end">${lastLabel}</text>
    </svg>
  `;

  wrap.innerHTML = svg;
}

async function refresh() {
  try {
    const [statsRes, historyRes, trendRes] = await Promise.all([
      fetch("/stats"),
      fetch("/history?limit=25"),
      fetch("/trend"),
    ]);
    const stats = await statsRes.json();
    const history = await historyRes.json();
    const trend = await trendRes.json();
    renderStats(stats);
    renderHistory(history.inspections);
    renderTrendChart(trend.buckets);
  } catch (err) {
    // Server briefly unreachable - next interval will retry.
  }
}

refresh();
setInterval(refresh, REFRESH_INTERVAL_MS);
