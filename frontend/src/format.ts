import type { HistoryRow } from "./types";
const names: Record<string, string> = {
  crazing: "Grietas superficiales",
  inclusion: "Inclusiones",
  patches: "Manchas o parches",
  pitted_surface: "Picaduras superficiales",
  "rolled-in_scale": "Cascarilla incrustada",
  scratches: "Rayaduras",
};
export const defectName = (name: string | null) =>
  name ? names[name] || name.replace(/[_-]/g, " ") : "Sin detecciones";
export const severityName = (name: string | null) =>
  ({ MINOR: "Leve", MAJOR: "Moderada", CRITICAL: "Alta" })[name || ""] ||
  "Sin estimar";
export const statusName = (status: string) =>
  status === "FAIL"
    ? "Con hallazgos"
    : status === "NO_DETECTIONS"
      ? "Sin detecciones"
      : "Histórico sin verificar";
export const num = (value?: number | null, digits = 0) =>
  value == null
    ? "—"
    : value.toLocaleString("es-MX", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
export const dateTime = (value: string) =>
  new Date(value).toLocaleString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
export function filterHistory(
  rows: HistoryRow[],
  search: string,
  status: string,
  from: string,
  to: string,
) {
  return rows.filter((row) => {
    const day = `${new Date(row.timestamp).getFullYear()}-${String(new Date(row.timestamp).getMonth() + 1).padStart(2, "0")}-${String(new Date(row.timestamp).getDate()).padStart(2, "0")}`;
    return (
      (!status || row.status === status) &&
      (!from || day >= from) &&
      (!to || day <= to) &&
      `${row.id} ${defectName(row.primary_defect)} ${row.primary_defect || ""} ${statusName(row.status)}`
        .toLocaleLowerCase("es")
        .includes(search.toLocaleLowerCase("es"))
    );
  });
}
