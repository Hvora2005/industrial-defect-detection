/* Server-owned USB capture in the existing dashboard. Only the capture button records. */
(() => {
  const byId = (id) => document.getElementById(id);
  const source = byId("serverCameraSource");
  const start = byId("serverCameraStart");
  const stop = byId("serverCameraStop");
  const capture = byId("serverCameraCapture");
  const scan = byId("serverCameraRefresh");
  const status = byId("serverCameraStatus");
  const image = byId("serverCameraImage");
  let running = false;
  let busy = false;
  let polling = false;
  let pendingRequest = null;
  let actionMessage = "";
  function message(text) { actionMessage = text; status.textContent = text; }

  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    return data;
  }

  async function gpu() {
    const info = await api("/runtime");
    const hardware = info.cuda_available ? info.gpus.map((g) => `${g.name} (${g.memory_mb} MB)`).join(", ") : "CUDA no disponible; auto utilizará CPU";
    byId("gpuStatus").textContent = `${hardware} · PyTorch ${info.torch_version} · runtime CUDA ${info.cuda_runtime || "ninguno"}`;
  }

  function state(data) {
    running = data.running;
    start.disabled = scan.disabled = running;
    stop.disabled = !running;
    capture.disabled = busy || data.state !== "running";
    for (const id of ["serverCameraSource", "serverCameraBackend", "serverCameraWidth", "serverCameraHeight", "serverCameraFps", "serverCameraDevice"]) {
      byId(id).disabled = running;
    }
    status.textContent = data.error || actionMessage || `Captura: ${data.state} · inspecciones manuales en esta sesión: ${data.inspections_recorded}`;
    const number = (value) => value == null ? "—" : Number(value).toFixed(1);
    const effective = data.effective || {};
    const requested = data.requested || {};
    byId("serverCameraMetrics").textContent = [
      `Solicitado ${requested.width || "—"}×${requested.height || "—"} a ${requested.fps || "—"} FPS`,
      `Efectivo ${data.frame_width || effective.width || "—"}×${data.frame_height || effective.height || "—"} a ${number(effective.fps)} FPS`,
      `Dispositivo ${data.inference_device === "cpu" ? "CPU" : data.inference_device ? "GPU CUDA (" + data.inference_device + ")" : "—"}`,
      `Inferencia ${data.inference_ms == null ? "—" : data.inference_ms.toFixed(1)} ms`,
      `Procesamiento ${data.processing_fps || "—"} FPS`,
    ].join(" · ");
  }

  scan.addEventListener("click", async () => {
    scan.disabled = true;
    try {
      const data = await api(`/cameras?backend=${byId("serverCameraBackend").value}`);
      source.replaceChildren();
      for (const camera of data.cameras) {
        const option = document.createElement("option");
        option.value = String(camera.index); option.textContent = camera.name; source.appendChild(option);
      }
      if (data.demo_available) {
        const option = document.createElement("option");
        option.value = "demo"; option.textContent = "Demo: sample.avi"; source.appendChild(option);
      }
      message(data.cameras.length ? "Selecciona la cámara. Los índices pueden incluir la integrada y USB." : "No se encontraron cámaras; puedes usar el video de demostración.");
    } catch (error) { message(error.message); }
    finally { scan.disabled = running; }
  });

  start.addEventListener("click", async () => {
    actionMessage = "";
    start.disabled = true;
    try {
      const data = await api("/camera/start", {
        source_type: source.value === "demo" ? "demo" : "camera",
        camera_index: source.value === "demo" ? 0 : Number(source.value),
        backend: byId("serverCameraBackend").value,
        width: Number(byId("serverCameraWidth").value), height: Number(byId("serverCameraHeight").value),
        fps: Number(byId("serverCameraFps").value), conf: Number(byId("serverCameraConfidence").value),
        device: byId("serverCameraDevice").value,
      });
      state(data); image.src = `/camera/stream?session=${Date.now()}`; image.hidden = false;
      await gpu();
    } catch (error) { message(error.message); start.disabled = false; }
  });

  stop.addEventListener("click", async () => {
    actionMessage = "";
    try { state(await api("/camera/stop", {})); image.removeAttribute("src"); image.hidden = true; }
    catch (error) { message(error.message); }
  });

  byId("serverCameraApplyConfidence").addEventListener("click", async () => {
    try {
      const data = await api("/camera/settings", {conf: Number(byId("serverCameraConfidence").value)});
      state(data); message(`Confianza aplicada: ${data.confidence}`);
    }
    catch (error) { message(error.message); }
  });

  capture.addEventListener("click", async () => {
    if (busy) return;
    busy = true; capture.disabled = true;
    // Retain the UUID on network errors so a retry cannot register the same event twice.
    pendingRequest ||= crypto.randomUUID();
    try {
      const result = await api("/camera/capture", {request_id: pendingRequest});
      pendingRequest = null;
      const links = byId("serverCaptureDownloads"); links.replaceChildren();
      for (const [key, label] of [["original_url", "Descargar original"], ["annotated_url", "Descargar anotada"]]) {
        const link = document.createElement("a"); link.href = result.captures[key]; link.textContent = label;
        link.download = ""; links.appendChild(link);
      }
      message(`${result.defects_found ? "Defectos detectados" : "Sin detecciones; calidad no verificada"} · ${result.duplicate ? "captura ya registrada" : "inspección registrada"}`);
      if (typeof refresh === "function") await refresh();
    } catch (error) { message(error.message); }
    finally { busy = false; capture.disabled = !running; }
  });

  async function poll() {
    if (polling) return;
    polling = true;
    try { state(await api("/camera/status")); }
    catch (error) { message(error.message); }
    finally { polling = false; }
  }
  gpu().catch((error) => { byId("gpuStatus").textContent = error.message; });
  poll(); setInterval(poll, 1000);
})();
