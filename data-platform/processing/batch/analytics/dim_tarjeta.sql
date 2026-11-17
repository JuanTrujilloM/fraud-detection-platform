CREATE TABLE coopandina_analytics.dim_tarjeta
WITH (
    format = 'PARQUET',
    external_location = 's3://datalake-fraudwatch/analytics/dim_tarjeta/<run_id>/'
) AS
SELECT
    t.id AS id_tarjeta,
    t.franquicia,
    t.estado,
    a.ciudad AS ciudad_asociado,
    date_diff('year', a.fecha_nacimiento, current_date) AS edad_asociado,
    a.ingreso_anual
FROM coopandina_curated.tarjetas t
JOIN coopandina_curated.asociados a ON a.id = t.asociado_id
