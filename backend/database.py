
"""Base de datos SQLite para almacenar el historial de inspecciones
y los defectos detectados mediante SQLAlchemy."""

import datetime
import json
from pathlib import Path
from collections import Counter

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    text,
    inspect,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship


# --------------------------------------------------
# CONFIGURACIÓN DE LA BASE DE DATOS
# --------------------------------------------------

# Ruta donde se almacenará el archivo de la base de datos.
DB_PATH = Path(__file__).resolve().parent.parent / "outputs" / "inspections.db"

# Crear el directorio de salida si todavía no existe.
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Crear la conexión con SQLite.
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False}
)


# Habilitar las claves foráneas en SQLite.
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Configurar las sesiones para interactuar con la base de datos.
SessionLocal = sessionmaker(bind=engine)

# Clase base para definir las tablas mediante SQLAlchemy.
Base = declarative_base()


# --------------------------------------------------
# TABLA 1: INSPECTIONS
# --------------------------------------------------

class Inspection(Base):
    """Almacena la información general de cada inspección."""

    __tablename__ = "inspections"

    # Identificador único de la inspección.
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Fecha y hora en que se realizó la inspección.
    timestamp = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    # Resultado de la inspección.
    status = Column(String, nullable=False)

    # Cantidad total de defectos encontrados.
    defects_found = Column(Integer, nullable=False, default=0)

    # Defecto principal de la inspección.
    primary_defect = Column(String, nullable=True)

    # Confianza del defecto principal.
    primary_confidence = Column(Float, nullable=True)

    # Severidad general de la inspección.
    severity = Column(String, nullable=True)

    # Campo antiguo conservado temporalmente para
    # realizar la migración de los datos históricos.
    all_defects_json = Column(
        String,
        nullable=False,
        default="[]"
    )

    # Relación uno a muchos con la tabla defects.
    defects = relationship(
        "Defect",
        back_populates="inspection",
        cascade="all, delete-orphan"
    )


# --------------------------------------------------
# TABLA 2: DEFECTS
# --------------------------------------------------

class Defect(Base):
    """Almacena individualmente cada defecto detectado."""

    __tablename__ = "defects"

    # Identificador único de cada defecto.
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Clave foránea que relaciona el defecto con su inspección.
    inspection_id = Column(
        Integer,
        ForeignKey("inspections.id"),
        nullable=False,
        index=True
    )

    # Nombre o clase del defecto.
    class_name = Column(String, nullable=False)

    # Confianza registrada para el defecto.
    confidence = Column(Float, nullable=True)

    # Severidad del defecto, si está disponible.
    severity = Column(String, nullable=True)

    # Relación inversa con la inspección.
    inspection = relationship(
        "Inspection",
        back_populates="defects"
    )


# --------------------------------------------------
# CREACIÓN DE LAS TABLAS
# --------------------------------------------------

# Crear las tablas si todavía no existen.
Base.metadata.create_all(engine)


# --------------------------------------------------
# MIGRACIÓN DE LOS DEFECTOS ANTERIORES
# --------------------------------------------------

def migrate_legacy_defects() -> None:
    """
    Migra los defectos almacenados anteriormente en formato JSON
    desde inspections hacia la nueva tabla defects.

    Conserva los registros originales y evita duplicar
    las detecciones durante la migración.
    """

    inspector = inspect(engine)

    # Obtener las columnas existentes en inspections.
    columns = [
        column["name"]
        for column in inspector.get_columns("inspections")
    ]

    # Comprobar si existe la columna antigua.
    if "all_defects_json" not in columns:
        return

    session = SessionLocal()

    try:
        # Recuperar los registros históricos.
        rows = session.execute(
            text("""
                SELECT id, all_defects_json
                FROM inspections
                ORDER BY id
            """)
        ).fetchall()

        for row in rows:
            inspection_id = row[0]
            defects_json = row[1]

            if not defects_json:
                continue

            # Convertir el contenido JSON.
            try:
                defects = json.loads(defects_json)
            except (json.JSONDecodeError, TypeError):
                # Continuar si algún registro tiene JSON inválido.
                continue

            if not isinstance(defects, list):
                continue

            # Recuperar los defectos que ya existen
            # para esta inspección.
            existing_rows = session.query(Defect).filter_by(
                inspection_id=inspection_id
            ).all()

            # Contabilizar las detecciones existentes.
            # Counter permite conservar defectos repetidos.
            existing_counts = Counter(
                (
                    defect.class_name,
                    defect.confidence,
                    defect.severity
                )
                for defect in existing_rows
            )

            # Procesar cada defecto del JSON original.
            for defect in defects:

                if not isinstance(defect, dict):
                    continue

                class_name = defect.get("class_name")

                if not class_name:
                    continue

                confidence = defect.get("confidence")
                severity = defect.get("severity")

                defect_key = (
                    class_name,
                    confidence,
                    severity
                )

                # Evitar insertar nuevamente una detección
                # que ya se encuentra registrada.
                if existing_counts[defect_key] > 0:
                    existing_counts[defect_key] -= 1
                    continue

                # Insertar el defecto en la nueva tabla.
                session.add(
                    Defect(
                        inspection_id=inspection_id,
                        class_name=class_name,
                        confidence=confidence,
                        severity=severity
                    )
                )

                # Solo se consumen filas que existían antes de migrar.
                # Las detecciones repetidas del JSON son ocurrencias distintas.

        # Guardar todos los cambios.
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


# Ejecutar la migración de los registros anteriores.
migrate_legacy_defects()


# --------------------------------------------------
# GUARDAR UNA NUEVA INSPECCIÓN
# --------------------------------------------------

def save_inspection(result: dict) -> None:
    """Guarda una inspección y todos sus defectos relacionados."""

    session = SessionLocal()

    try:
        # Recuperar la lista de defectos.
        defects = result.get("defects", [])

        # Identificar el defecto principal.
        top = defects[0] if defects else None

        # Crear el registro general de la inspección.
        record = Inspection(
            status=result["status"],
            defects_found=result.get("defects_found", len(defects)),
            primary_defect=top["class_name"] if top else None,
            primary_confidence=top.get("confidence") if top else None,
            severity=result.get("severity"),
            all_defects_json=json.dumps(defects),
        )

        # Relacionar cada defecto con la inspección.
        for defect in defects:
            record.defects.append(
                Defect(
                    class_name=defect["class_name"],
                    confidence=defect.get("confidence"),
                    severity=defect.get("severity")
                )
            )

        # Guardar la inspección y sus defectos
        # dentro de una misma transacción.
        session.add(record)
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


# --------------------------------------------------
# OBTENER LAS INSPECCIONES MÁS RECIENTES
# --------------------------------------------------

def get_recent_inspections(limit: int = 50) -> list[dict]:
    """Recupera las inspecciones más recientes."""

    session = SessionLocal()

    try:
        # Consultar las inspecciones ordenadas por ID.
        rows = (
            session.query(Inspection)
            .order_by(Inspection.id.desc())
            .limit(limit)
            .all()
        )

        # Convertir los registros en diccionarios.
        return [
            {
                "id": r.id,
                "timestamp": (
                    r.timestamp.replace(tzinfo=datetime.timezone.utc)
                    if r.timestamp.tzinfo is None
                    else r.timestamp
                ).isoformat().replace("+00:00", "Z"),
                "status": r.status,
                "defects_found": r.defects_found,
                "primary_defect": r.primary_defect,
                "primary_confidence": r.primary_confidence,
                "severity": r.severity,
            }
            for r in rows
        ]

    finally:
        session.close()


# --------------------------------------------------
# OBTENER ESTADÍSTICAS GENERALES
# --------------------------------------------------

def get_stats() -> dict:
    """Calcula las estadísticas generales de las inspecciones."""

    session = SessionLocal()

    try:
        # Recuperar las inspecciones y los defectos.
        inspections = session.query(Inspection).all()
        defects = session.query(Defect).all()

        # Cantidad total de inspecciones.
        total = len(inspections)

        # Contabilizar los resultados.
        pass_count = sum(
            1 for r in inspections if r.status == "PASS"
        )

        fail_count = sum(
            1 for r in inspections if r.status == "FAIL"
        )

        no_detections_count = sum(
            1 for r in inspections if r.status == "NO_DETECTIONS"
        )

        # Contabilizar los defectos por clasificación.
        defect_counts: dict[str, int] = {}

        for defect in defects:
            name = defect.class_name
            defect_counts[name] = defect_counts.get(name, 0) + 1

        # Identificar el defecto más frecuente.
        most_common = (
            max(defect_counts, key=defect_counts.get)
            if defect_counts
            else None
        )

        # Inicializar los contadores de severidad.
        severity_counts = {
            "MINOR": 0,
            "MAJOR": 0,
            "CRITICAL": 0
        }

        # Contabilizar la severidad general de las inspecciones.
        for inspection in inspections:
            if inspection.severity in severity_counts:
                severity_counts[inspection.severity] += 1

        # Recuperar las confianzas disponibles.
        all_confidences = [
            defect.confidence
            for defect in defects
            if defect.confidence is not None
        ]

        # Calcular el promedio de confianza.
        avg_confidence = (
            round(sum(all_confidences) / len(all_confidences), 1)
            if all_confidences
            else None
        )

        # Devolver las estadísticas.
        return {
            "total_inspected": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "no_detections_count": no_detections_count,
            "defect_rate": (
                round((fail_count / total) * 100, 1)
                if total > 0
                else 0.0
            ),
            "most_common_defect": most_common,
            "defect_distribution": defect_counts,
            "severity_distribution": severity_counts,
            "avg_confidence": avg_confidence,
        }

    finally:
        session.close()


# --------------------------------------------------
# OBTENER TENDENCIAS DE INSPECCIÓN
# --------------------------------------------------

def get_trend(
    bucket_seconds: int = 60,
    limit_buckets: int = 15
) -> list[dict]:
    """
    Agrupa las inspecciones en intervalos de tiempo
    y contabiliza los resultados PASS, FAIL y NO_DETECTIONS.
    """

    session = SessionLocal()

    try:
        # Recuperar las inspecciones ordenadas cronológicamente.
        rows = (
            session.query(Inspection)
            .order_by(Inspection.timestamp.asc())
            .all()
        )

        # Almacenar los resultados por intervalo.
        buckets: dict[int, dict] = {}

        for inspection in rows:

            timestamp = inspection.timestamp

            # Asignar UTC si la fecha no tiene zona horaria.
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=datetime.timezone.utc
                )

            # Convertir la fecha a marca de tiempo.
            ts = timestamp.timestamp()

            # Calcular el intervalo correspondiente.
            bucket_key = int(ts // bucket_seconds) * bucket_seconds

            # Crear el intervalo si todavía no existe.
            bucket = buckets.setdefault(
                bucket_key,
                {
                    "pass": 0,
                    "fail": 0,
                    "no_detections": 0
                }
            )

            # Contabilizar el resultado.
            if inspection.status == "PASS":
                bucket["pass"] += 1

            elif inspection.status == "FAIL":
                bucket["fail"] += 1

            elif inspection.status == "NO_DETECTIONS":
                bucket["no_detections"] += 1

        # Seleccionar los intervalos más recientes.
        sorted_keys = sorted(buckets.keys())[-limit_buckets:]

        # Preparar los datos para la gráfica.
        return [
            {
                "time": datetime.datetime.fromtimestamp(
                    key,
                    tz=datetime.timezone.utc
                ).strftime("%H:%M"),
                "pass": buckets[key]["pass"],
                "fail": buckets[key]["fail"],
                "no_detections": buckets[key]["no_detections"],
            }
            for key in sorted_keys
        ]

    finally:
        session.close()
