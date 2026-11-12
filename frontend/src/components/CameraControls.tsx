import { RefreshCw, SlidersHorizontal } from "lucide-react";
import type { CameraController } from "../hooks/useCamera";
import type { Runtime } from "../types";

export function CameraControls({
  camera,
  runtime,
  compact = false,
}: {
  camera: CameraController;
  runtime?: Runtime;
  compact?: boolean;
}) {
  const { options, setOptions, data, busy } = camera;
  const locked = data?.running || !!busy;
  function number(key: "width" | "height" | "fps" | "conf", value: string) {
    setOptions((o) => ({ ...o, [key]: Number(value) }));
  }
  return (
    <div className={`camera-settings ${compact ? "compact" : ""}`}>
      <div className="form-grid">
        <label>
          Fuente de cámara
          <select
            value={options.source}
            disabled={locked || !camera.sources.length}
            onChange={(e) =>
              setOptions((o) => ({ ...o, source: e.target.value }))
            }
          >
            {camera.sources.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Dispositivo de inferencia
          <select
            value={options.device}
            disabled={locked}
            onChange={(e) =>
              setOptions((o) => ({
                ...o,
                device: e.target.value as typeof o.device,
              }))
            }
          >
            <option value="auto">Automático</option>
            <option value="cuda" disabled={!runtime?.cuda_available}>
              GPU · CUDA
            </option>
            <option value="cpu">CPU</option>
          </select>
        </label>
        <label>
          Ancho solicitado (px)
          <input
            type="number"
            min="64"
            max="4096"
            required
            value={options.width}
            disabled={locked}
            onChange={(e) => number("width", e.target.value)}
          />
        </label>
        <label>
          Alto solicitado (px)
          <input
            type="number"
            min="64"
            max="4096"
            required
            value={options.height}
            disabled={locked}
            onChange={(e) => number("height", e.target.value)}
          />
        </label>
        <label>
          FPS solicitados
          <input
            type="number"
            min="1"
            max="120"
            required
            value={options.fps}
            disabled={locked}
            onChange={(e) => number("fps", e.target.value)}
          />
        </label>
        <label>
          Controlador de cámara
          <select
            value={options.backend}
            disabled={locked}
            onChange={(e) =>
              setOptions((o) => ({
                ...o,
                backend: e.target.value as typeof o.backend,
              }))
            }
          >
            <option value="auto">Automático</option>
            <option value="dshow">DirectShow</option>
            <option value="msmf">Media Foundation</option>
          </select>
        </label>
      </div>
      <div className="confidence-control">
        <label htmlFor="confidence">
          Umbral de confianza <strong>{Math.round(options.conf * 100)}%</strong>
        </label>
        <input
          id="confidence"
          aria-label="Umbral de confianza"
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={options.conf}
          onChange={(e) => number("conf", e.target.value)}
        />
        <p>
          Se muestran detecciones con una confianza igual o mayor a este valor.
        </p>
      </div>
      <div className="button-row">
        <button
          className="button secondary"
          disabled={locked}
          onClick={() => void camera.scan()}
        >
          <RefreshCw size={15} className={busy === "scan" ? "spin" : ""} />
          Buscar cámaras
        </button>
        <button
          className="button secondary"
          disabled={!data?.running || !!busy}
          onClick={() => void camera.apply()}
        >
          <SlidersHorizontal size={15} />
          Aplicar umbral en vivo
        </button>
      </div>
      <p className="microcopy">
        La resolución y los FPS efectivos dependen de la cámara. Detén la
        captura para cambiar de fuente o dispositivo.
      </p>
    </div>
  );
}
