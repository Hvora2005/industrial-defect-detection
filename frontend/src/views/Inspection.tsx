import { useEffect, useMemo, useRef, useState } from "react";
import {
  Aperture,
  Camera,
  CameraOff,
  Circle,
  Maximize2,
  Play,
  Square,
  Upload,
} from "lucide-react";
import { CameraControls } from "../components/CameraControls";
import { ErrorNotice, ResultPanel } from "../components/Common";
import type { CameraController } from "../hooks/useCamera";
import type { Detection, Runtime } from "../types";
import { api, errorMessage } from "../services/api";
import { num } from "../format";

export interface InspectionProps {
  camera: CameraController;
  runtime?: Runtime;
  result?: Detection;
  originalUrl?: string;
  onResult: (result: Detection, original?: Blob) => void;
}
export function Inspection({
  camera,
  runtime,
  result,
  originalUrl,
  onResult,
}: InspectionProps) {
  const [mode, setMode] = useState<"usb" | "browser">("usb");
  const [localRunning, setLocalRunning] = useState(false);
  const [live, setLive] = useState(false);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [opening, setOpening] = useState(false);
  const openingRef = useRef(false);
  const localRequest = useRef(0);
  const stream = useRef<MediaStream | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const lock = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const running = !!camera.data?.running;
  const session = useMemo(() => (running ? Date.now() : 0), [running]);
  function stopLocal() {
    localRequest.current += 1;
    openingRef.current = false;
    setOpening(false);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setLocalRunning(false);
    setLive(false);
    setPreview("");
  }
  useEffect(
    () => () => {
      localRequest.current += 1;
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );
  async function startLocal() {
    if (openingRef.current || stream.current) return;
    const token = ++localRequest.current;
    openingRef.current = true;
    setOpening(true);
    try {
      setError("");
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "La cámara del navegador requiere localhost o una conexión HTTPS.",
        );
      const acquired = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: camera.options.width },
          height: { ideal: camera.options.height },
        },
        audio: false,
      });
      if (token !== localRequest.current || !video.current) {
        acquired.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = acquired;
      video.current.srcObject = acquired;
      setLocalRunning(true);
      await video.current.play();
    } catch (e) {
      if (token !== localRequest.current) return;
      const messages: Record<string, string> = {
        NotAllowedError:
          "Autoriza el acceso a la cámara en el navegador y vuelve a intentar.",
        NotFoundError: "No se encontró una cámara en este dispositivo.",
        NotReadableError:
          "La cámara está ocupada o no puede abrirse. Cierra otras aplicaciones que la utilicen.",
        OverconstrainedError:
          "La cámara no admite los parámetros solicitados. Prueba otra resolución.",
      };
      setError(
        e instanceof Error
          ? messages[e.name] ||
              (e.message.includes("HTTPS")
                ? e.message
                : "No se pudo abrir la cámara. Revisa sus permisos y conexión.")
          : "No se pudo abrir la cámara.",
      );
      stopLocal();
    } finally {
      if (token === localRequest.current) {
        openingRef.current = false;
        setOpening(false);
      }
    }
  }
  async function frame(): Promise<Blob> {
    if (!video.current?.videoWidth)
      throw new Error("Espera a que la cámara muestre una imagen.");
    const canvas = document.createElement("canvas");
    const v = video.current;
    const scale = Math.min(1, 960 / Math.max(v.videoWidth, v.videoHeight));
    canvas.width = Math.round(v.videoWidth * scale);
    canvas.height = Math.round(v.videoHeight * scale);
    canvas.getContext("2d")!.drawImage(v, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve, reject) =>
      canvas.toBlob(
        (b) =>
          b ? resolve(b) : reject(new Error("No se pudo capturar la imagen.")),
        "image/jpeg",
        0.85,
      ),
    );
  }
  async function inspect(
    file: Blob,
    endpoint: "/preview" | "/detect" | "/upload",
  ) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const data = await api.image(
        file,
        endpoint,
        camera.options.conf,
        camera.options.device,
      );
      if (endpoint === "/preview")
        setPreview(`data:image/jpeg;base64,${data.annotated_image}`);
      else onResult(data, file);
    } catch (e) {
      setError(errorMessage(e));
      if (endpoint === "/preview") setLive(false);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!live || !localRunning) return;
    let disposed = false;
    const timer = window.setInterval(() => {
      if (!lock.current)
        void frame()
          .then((blob) => {
            if (!disposed) void inspect(blob, "/preview");
          })
          .catch((e) => {
            setError(String(e));
            setLive(false);
          });
    }, 2000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
    // Camera settings are captured explicitly for each preview cycle.
  }, [live, localRunning, camera.options.conf, camera.options.device]);
  const active = mode === "usb" ? running : localRunning;
  const canCapture =
    mode === "usb" ? camera.data?.state === "running" : localRunning;
  const capture = async () => {
    if (mode === "usb") await camera.capture();
    else
      try {
        await inspect(await frame(), "/detect");
      } catch (e) {
        setError(String(e));
      }
  };
  return (
    <>
      <div className="inspection-layout">
        <section className="camera-workspace">
          <div className="camera-heading">
            <div className="segmented" aria-label="Origen de la cámara">
              <button
                aria-pressed={mode === "usb"}
                onClick={() => {
                  stopLocal();
                  setMode("usb");
                }}
              >
                Cámara USB / servidor
              </button>
              <button
                aria-pressed={mode === "browser"}
                onClick={() => setMode("browser")}
              >
                Este dispositivo
              </button>
            </div>
            <button
              className="icon-button"
              aria-label="Ampliar cámara"
              onClick={() =>
                void viewport.current
                  ?.requestFullscreen?.()
                  .catch(() => setError("No se pudo ampliar la cámara."))
              }
            >
              <Maximize2 size={17} />
            </button>
          </div>
          <div className="camera-viewport" ref={viewport}>
            {mode === "usb" && running && (
              <img
                src={`/camera/stream?session=${session}`}
                alt="Vista previa de la cámara USB con detecciones"
                onError={() =>
                  setError(
                    "No se recibe la vista previa. Revisa el estado de la cámara y vuelve a iniciarla.",
                  )
                }
              />
            )}
            <video
              ref={video}
              autoPlay
              muted
              playsInline
              hidden={mode !== "browser" || !localRunning}
            />
            {mode === "browser" && live && preview && (
              <img
                className="preview-overlay"
                src={preview}
                alt="Vista previa analizada sin registrar"
              />
            )}
            {!active && (
              <div className="camera-empty">
                <div className="aperture-mark">
                  <Aperture size={45} strokeWidth={1} />
                </div>
                <h2>Tu próxima inspección empieza aquí</h2>
                <p>
                  {mode === "usb"
                    ? "Conecta una cámara USB y selecciona la fuente para comenzar."
                    : "Usa la cámara de este teléfono o computadora."}
                </p>
                <span>Vista previa sin registro automático</span>
              </div>
            )}
            <div className="viewport-label">
              <span className={`live-indicator ${active ? "active" : ""}`}>
                <Circle size={7} fill="currentColor" />
                {active ? "Vista previa" : "Cámara detenida"}
              </span>
              <span>{mode === "usb" ? "OpenCV" : "Cámara del navegador"}</span>
            </div>
            <div className="viewfinder-corner top-left" />
            <div className="viewfinder-corner bottom-right" />
          </div>
          <div className="camera-telemetry">
            <span>
              Resolución{" "}
              <strong>
                {camera.data?.frame_width && mode === "usb"
                  ? `${camera.data.frame_width} × ${camera.data.frame_height}`
                  : mode === "browser" && localRunning
                    ? `${video.current?.videoWidth} × ${video.current?.videoHeight}`
                    : "—"}
              </strong>
              <small className="source-fps">
                {num(mode === "usb" ? camera.data?.effective?.fps : stream.current?.getVideoTracks()[0]?.getSettings().frameRate, 1)} FPS de fuente
              </small>
            </span>
            <span>
              Inferencia{" "}
              <strong>
                {mode === "usb"
                  ? num(camera.data?.inference_ms, 1)
                  : num(result?.inference_ms, 1)}{" "}
                ms
              </strong>
            </span>
            <span>
              Procesamiento{" "}
              <strong>
                {mode === "usb"
                  ? num(camera.data?.processing_fps, 1)
                  : num(result?.processing_fps, 1)}{" "}
                FPS
              </strong>
            </span>
          </div>
          <div className="capture-toolbar">
            <div className="button-row">
              {!active ? (
                <button
                  className="button secondary"
                  disabled={
                    opening ||
                    !!camera.busy ||
                    (mode === "usb" &&
                      (!runtime?.model_loaded || !camera.sources.length))
                  }
                  onClick={() =>
                    mode === "usb" ? void camera.start() : void startLocal()
                  }
                >
                  <Play size={16} />
                  {opening ? "Abriendo cámara…" : "Iniciar cámara"}
                </button>
              ) : (
                <button
                  className="button secondary"
                  disabled={!!camera.busy}
                  onClick={() =>
                    mode === "usb" ? void camera.stop() : stopLocal()
                  }
                >
                  <Square size={15} />
                  Detener
                </button>
              )}
              <button
                className="button primary"
                disabled={
                  !canCapture || busy || !!camera.busy || !runtime?.model_loaded
                }
                onClick={() => void capture()}
              >
                <Camera size={18} />
                {camera.busy === "capture" || busy
                  ? "Procesando…"
                  : "Capturar e inspeccionar"}
              </button>
            </div>
            <button
              className="button ghost"
              disabled={busy || !runtime?.model_loaded}
              onClick={() => input.current?.click()}
            >
              <Upload size={16} />
              Subir imagen
            </button>
            <input
              className="sr-only"
              type="file"
              accept="image/*"
              ref={input}
              aria-label="Subir imagen de inspección"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void inspect(file, "/upload");
                e.target.value = "";
              }}
            />
          </div>
          {mode === "browser" && localRunning && (
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={live}
                onChange={(e) => {
                  setLive(e.target.checked);
                  setPreview("");
                }}
              />
              Analizar vista previa cada 2 segundos · no registra inspecciones
            </label>
          )}
          <div className="preview-note">
            <CameraOff size={15} />
            <p>
              La vista previa no suma inspecciones. Captura una sola vez por
              pieza para registrar el resultado.
            </p>
          </div>
          {(error ||
            camera.actionError ||
            camera.error ||
            camera.data?.error) && (
            <ErrorNotice
              message={
                error ||
                camera.actionError ||
                camera.error ||
                camera.data?.error ||
                ""
              }
            />
          )}
          {camera.message && (
            <p className="action-message" role="status">
              {camera.message}
            </p>
          )}
        </section>
        <ResultPanel result={result} originalUrl={originalUrl} />
      </div>
      <details className="panel capture-configuration" open>
        <summary>
          Parámetros de captura <span>Fuente, resolución y umbral</span>
        </summary>
        <CameraControls camera={camera} runtime={runtime} compact />
      </details>
    </>
  );
}
