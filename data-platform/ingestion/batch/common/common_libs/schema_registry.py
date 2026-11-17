from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    spark_type: str


@dataclass(frozen=True)
class EntityConfig:
    name: str
    source_table: str
    primary_key: Tuple[str, ...]
    watermark_column: str
    columns: Tuple[ColumnSpec, ...]


ENTITY_CONFIGS: Dict[str, EntityConfig] = {
    "asociados": EntityConfig(
        name="asociados",
        source_table="asociado",
        primary_key=("id",),
        watermark_column="fecha_actualizacion",
        columns=(
            ColumnSpec("id", "bigint"),
            ColumnSpec("tipo_documento", "string"),
            ColumnSpec("fecha_nacimiento", "date"),
            ColumnSpec("ciudad", "string"),
            ColumnSpec("ingreso_anual", "decimal(14,2)"),
            ColumnSpec("puntaje_crediticio", "int"),
            ColumnSpec("fecha_afiliacion", "date"),
            ColumnSpec("estado", "string"),
            ColumnSpec("fecha_actualizacion", "timestamp"),
        ),
    ),
    "comercios": EntityConfig(
        name="comercios",
        source_table="comercio",
        primary_key=("id",),
        watermark_column="fecha_actualizacion",
        columns=(
            ColumnSpec("id", "bigint"),
            ColumnSpec("nombre", "string"),
            ColumnSpec("nit", "string"),
            ColumnSpec("categoria", "string"),
            ColumnSpec("ciudad", "string"),
            ColumnSpec("vende_en_linea", "boolean"),
            ColumnSpec("estado", "string"),
            ColumnSpec("fecha_actualizacion", "timestamp"),
        ),
    ),
    "tarjetas": EntityConfig(
        name="tarjetas",
        source_table="tarjeta",
        primary_key=("id",),
        watermark_column="fecha_actualizacion",
        columns=(
            ColumnSpec("id", "bigint"),
            ColumnSpec("asociado_id", "bigint"),
            ColumnSpec("ultimos_4", "string"),
            ColumnSpec("franquicia", "string"),
            ColumnSpec("fecha_vencimiento", "date"),
            ColumnSpec("tiene_chip", "boolean"),
            ColumnSpec("cupo_total", "decimal(14,2)"),
            ColumnSpec("cupo_disponible", "decimal(14,2)"),
            ColumnSpec("fecha_emision", "date"),
            ColumnSpec("estado", "string"),
            ColumnSpec("fecha_actualizacion", "timestamp"),
        ),
    ),
    "autorizaciones": EntityConfig(
        name="autorizaciones",
        source_table="autorizacion",
        primary_key=("id",),
        watermark_column="fecha_hora",
        columns=(
            ColumnSpec("id", "bigint"),
            ColumnSpec("tarjeta_id", "bigint"),
            ColumnSpec("comercio_id", "bigint"),
            ColumnSpec("monto", "decimal(14,2)"),
            ColumnSpec("canal", "string"),
            ColumnSpec("modo_lectura", "string"),
            ColumnSpec("resultado", "string"),
            ColumnSpec("motivo_rechazo", "string"),
            ColumnSpec("probabilidad_fraude", "double"),
            ColumnSpec("ip", "string"),
            ColumnSpec("fecha_hora", "timestamp"),
        ),
    ),
}


def get_entity_config(entity_name: str) -> EntityConfig:
    normalized_name = entity_name.strip().lower()
    try:
        return ENTITY_CONFIGS[normalized_name]
    except KeyError as exc:
        supported = ", ".join(sorted(ENTITY_CONFIGS))
        raise ValueError(
            f"Unsupported entity '{entity_name}'. Supported entities: {supported}"
        ) from exc

