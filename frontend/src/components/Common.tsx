import {
  AlertCircle,
  Aperture,
  ArrowUpRight,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";
import type { Detection, HistoryRow } from "../types";
import { dateTime, defectName, num, severityName, statusName } from "../format";

export function Badge({ status }: { status: string }) {
  return (
    <span
      className={`badge ${status === "FAIL" ? "warn" : status === "NO_DETECTIONS" ? "neutral" : "legacy"}`}
    >
      <i />
      {statusName(status)}
    </span>
  );
}
export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice error" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
      {retry && (
        <button className="icon-button" onClick={retry} aria-label="Reintentar">
          <RefreshCw size={16} />
        </button>
      )}
    </div>
  );
}
export function Loading() {
  return (
    <div className="empty" role="status">
      <LoaderCircle className="spin" size={24} />
      <p>Cargando información…</p>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Aperture size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Panel({
  title,
  detail,
  action,
  children,
  className = "",
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {detail && <p>{detail}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function HistoryTable({
  rows,
  onSelect,
}: {
  rows: HistoryRow[];
  onSelect: (row: HistoryRow) => void;
}) {
  if (!rows.length)
    return (
      <Empty title="Sin inspecciones para mostrar">
        Captura una pieza o ajusta los filtros de búsqueda.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Inspección</th>
            <th>Fecha y hora</th>
            <th>Hallazgo principal</th>
            <th>Confianza</th>
            <th>Resultado</th>
            <th>
              <span className="sr-only">Detalles</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="record-id">#{String(row.id).padStart(4, "0")}</td>
              <td>{dateTime(row.timestamp)}</td>
              <td>{defectName(row.primary_defect)}</td>
              <td>
                {num(row.primary_confidence, 1)}
                {row.primary_confidence != null ? "%" : ""}
              </td>
              <td>
                <Badge status={row.status} />
              </td>
              <td>
                <button
                  className="icon-button"
                  onClick={() => onSelect(row)}
                  aria-label={`Ver inspección ${row.id}`}
                >
                  <ArrowUpRight size={17} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function ResultPanel({
  result,
  originalUrl,
}: {
  result?: Detection;
  originalUrl?: string;
}) {
  return (
    <Panel
      title="Última inspección"
      detail="Resultado de la captura registrada"
      action={result && <Badge status={result.status} />}
      className="result-panel"
    >
      {!result ? (
        <Empty title="Todo listo para inspeccionar">
          Inicia la cámara y captura una pieza. La vista previa no registra
          inspecciones.
        </Empty>
      ) : (
        <>
          <div className="result-photo">
            <img
              src={`data:image/jpeg;base64,${result.annotated_image}`}
              alt="Última inspección con detecciones anotadas"
            />
          </div>
          <div className="result-summary">
            <strong>{result.defects_found}</strong>
            <span>
              {result.defects_found === 1 ? "zona señalada" : "zonas señaladas"}
              <small>
                Severidad{" "}
                {severityName(result.severity).toLocaleLowerCase("es")}
              </small>
            </span>
          </div>
          <div className="detection-list">
            {result.defects.map((d, index) => (
              <div className="detection" key={index}>
                <span className="detection-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <strong>{defectName(d.class_name)}</strong>
                  <small>{severityName(d.severity)}</small>
                </div>
                <strong>
                  {num(d.confidence, 1)}
                  <small>% confianza</small>
                </strong>
              </div>
            ))}
          </div>
          {!result.defects_found && (
            <p className="muted">
              Sin detecciones con el umbral actual. La calidad de la pieza no
              está verificada.
            </p>
          )}
          <p className="microcopy">
            La confianza expresa la certeza del modelo sobre su etiqueta, no el
            porcentaje de daño. La severidad es orientativa.
          </p>
          <div className="download-links">
            {(result.captures?.original_url || originalUrl) && (
              <a
                href={result.captures?.original_url || originalUrl}
                download="original.jpg"
              >
                Imagen original <ArrowUpRight size={14} />
              </a>
            )}
            <a
              href={
                result.captures?.annotated_url ||
                `data:image/jpeg;base64,${result.annotated_image}`
              }
              download="anotada.jpg"
            >
              Imagen anotada <ArrowUpRight size={14} />
            </a>
          </div>
        </>
      )}
    </Panel>
  );
}
