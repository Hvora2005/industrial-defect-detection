import type {
  Bucket,
  CameraList,
  CameraOptions,
  CameraState,
  Detection,
  Device,
  Health,
  HistoryRow,
  Runtime,
  Stats,
} from "../types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400) return 'No se pudo leer la imagen. Sube un archivo JPEG o PNG válido y con contenido.';
    if (error.status === 422) return 'Revisa los parámetros de captura: resolución, FPS y umbral deben estar dentro de los límites indicados.';
    if (error.status === 503)
      return "El modelo o el dispositivo de inferencia no está disponible. Revisa la configuración del servidor y vuelve a intentar.";
    if (error.status === 409)
      return `No se pudo completar la acción de cámara. ${error.message}`;
    return error.message;
  }
  return "No se pudo conectar con el servidor. Comprueba la conexión y vuelve a intentar.";
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      body && typeof body === "object" && "detail" in body ? body.detail : null;
    throw new ApiError(
      response.status,
      typeof detail === "string"
        ? detail
        : `El servidor respondió con un error (${response.status}).`,
    );
  }
  return response.json() as Promise<T>;
}
const post = <T>(path: string, body: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const api = {
  health: () => request<Health>("/health"),
  runtime: () => request<Runtime>("/runtime"),
  camera: () => request<CameraState>("/camera/status"),
  cameras: (backend: string) =>
    request<CameraList>(`/cameras?backend=${encodeURIComponent(backend)}`),
  start: (o: CameraOptions) =>
    post<CameraState>("/camera/start", {
      source_type: o.source === "demo" ? "demo" : "camera",
      camera_index: o.source === "demo" ? 0 : Number(o.source),
      backend: o.backend,
      width: o.width,
      height: o.height,
      fps: o.fps,
      conf: o.conf,
      device: o.device,
    }),
  stop: () => post<CameraState>("/camera/stop", {}),
  confidence: (conf: number) => post<CameraState>("/camera/settings", { conf }),
  capture: (request_id: string) =>
    post<Detection>("/camera/capture", { request_id }),
  stats: () => request<Stats>("/stats"),
  history: (limit: number) =>
    request<{ inspections: HistoryRow[] }>(`/history?limit=${limit}`),
  trend: (seconds: number) =>
    request<{ buckets: Bucket[] }>(
      `/trend?bucket_seconds=${seconds}&limit_buckets=30`,
    ),
  image: (
    file: Blob,
    endpoint: "/preview" | "/detect" | "/upload",
    conf: number,
    device: Device,
  ) => {
    const form = new FormData();
    form.append("file", file, "inspection.jpg");
    return request<Detection>(`${endpoint}?conf=${conf}&device=${device}`, {
      method: "POST",
      body: form,
    });
  },
};
