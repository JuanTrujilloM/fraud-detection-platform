CREATE TABLE coopandina_analytics.dim_comercio
WITH (
    format = 'PARQUET',
    external_location = 's3://datalake-fraudwatch/analytics/dim_comercio/<run_id>/'
) AS
SELECT
    id AS id_comercio,
    nombre,
    categoria,
    ciudad,
    vende_en_linea
FROM coopandina_curated.comercios
