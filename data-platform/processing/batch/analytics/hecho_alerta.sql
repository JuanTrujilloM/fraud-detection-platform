CREATE TABLE coopandina_analytics.hecho_alerta
WITH (
    format = 'PARQUET',
    external_location = 's3://datalake-fraudwatch/analytics/hecho_alerta/<run_id>/'
) AS
SELECT
    c.id_alerta,
    c.tipo,
    c.id_comercio,
    c.id_tarjeta,
    c.fecha,
    year(c.fecha) AS anio,
    month(c.fecha) AS mes,
    hour(c.fecha) AS hora,
    COALESCE(r.estado, 'PENDIENTE') AS estado,
    date_diff('minute', c.event_time, r.event_time) AS minutos_resolucion
FROM (
    SELECT
        id_alerta,
        tipo,
        id_comercio,
        id_tarjeta,
        event_time,
        CAST(event_time AT TIME ZONE 'America/Bogota' AS timestamp) AS fecha
    FROM coopandina_curated.eventos
    WHERE event_type = 'ALERTA_CREADA'
) c
LEFT JOIN (
    SELECT
        id_alerta,
        estado,
        event_time
    FROM coopandina_curated.eventos
    WHERE event_type = 'ALERTA_RESUELTA'
) r ON r.id_alerta = c.id_alerta
