CREATE TABLE coopandina_analytics.hecho_autorizacion
WITH (
    format = 'PARQUET',
    external_location = 's3://datalake-fraudwatch/analytics/hecho_autorizacion/<run_id>/'
) AS
SELECT
    a.id AS id_autorizacion,
    a.tarjeta_id AS id_tarjeta,
    a.comercio_id AS id_comercio,
    a.fecha,
    year(a.fecha) AS anio,
    month(a.fecha) AS mes,
    hour(a.fecha) AS hora,
    a.monto,
    a.canal,
    a.resultado,
    a.motivo_rechazo,
    CASE WHEN c.id_autorizacion IS NULL THEN 0 ELSE 1 END AS es_fraude
FROM (
    SELECT
        id,
        tarjeta_id,
        comercio_id,
        monto,
        canal,
        resultado,
        motivo_rechazo,
        CAST(fecha_hora AT TIME ZONE 'America/Bogota' AS timestamp) AS fecha
    FROM coopandina_curated.autorizaciones
) a
LEFT JOIN (
    SELECT DISTINCT id_autorizacion
    FROM coopandina_curated.contracargos
    WHERE motivo = 'FRAUDE'
) c ON c.id_autorizacion = a.id
