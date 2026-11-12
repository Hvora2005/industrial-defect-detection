export type Device = "auto" | "cpu" | "cuda";
export interface Defect {
  class_name: string;
  confidence: number;
  severity: string;
  bbox?: { x1: number; y1: number; x2: number; y2: number };
}
export interface Detection {
  status: string;
  defects_found: number;
  defects: Defect[];
  severity: string | null;
  annotated_image: string;
  inference_device?: string;
  inference_ms?: number;
  processing_fps?: number;
  captures?: { original_url: string; annotated_url: string };
  capture_id?: string;
  duplicate?: boolean;
}
export interface HistoryRow {
  id: number;
  timestamp: string;
  status: string;
  defects_found: number;
  primary_defect: string | null;
  primary_confidence: number | null;
  severity: string | null;
}
export interface Stats {
  total_inspected: number;
  fail_count: number;
  no_detections_count: number;
  pass_count: number;
  defect_rate: number;
  most_common_defect: string | null;
  avg_confidence: number | null;
  defect_distribution: Record<string, number>;
  severity_distribution: Record<string, number>;
}
export interface Bucket {
  time: string;
  fail: number;
  no_detections: number;
  pass: number;
}
export interface Runtime {
  cuda_available: boolean;
  gpus: { index: number; name: string; memory_mb: number }[];
  torch_version: string;
  cuda_runtime: string | null;
  model_loaded: boolean;
  requested_device: Device;
  active_device: string | null;
}
export interface Health {
  status: string;
  model_loaded: boolean;
  classes: string[];
}
export interface CameraState {
  state: string;
  running: boolean;
  error?: string | null;
  confidence: number;
  requested_device: Device;
  source?: string;
  source_type?: string;
  frames_processed: number;
  inspections_recorded: number;
  effective?: { width: number; height: number; fps: number };
  requested?: { width: number; height: number; fps: number };
  frame_width?: number;
  frame_height?: number;
  inference_device?: string;
  inference_ms?: number;
  processing_fps?: number;
}
export interface CameraOptions {
  source: string;
  backend: "auto" | "dshow" | "msmf";
  width: number;
  height: number;
  fps: number;
  conf: number;
  device: Device;
}
export interface CameraList {
  cameras: { index: number; name: string }[];
  demo_available: boolean;
}
export type View =
  | "inspeccion"
  | "resumen"
  | "historial"
  | "estadisticas"
  | "configuracion"
  | "monitor";
