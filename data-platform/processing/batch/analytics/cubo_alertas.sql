SELECT
    h.anio,
    h.mes,
    h.tipo,
    h.estado,
    c.categoria,
    COUNT(*) AS alertas,
    COALESCE(SUM(h.minutos_resolucion), 0) AS minutos_resolucion
FROM coopandina_analytics.hecho_alerta h
JOIN coopandina_analytics.dim_comercio c ON c.id_comercio = h.id_comercio
GROUP BY h.anio, h.mes, h.tipo, h.estado, c.categoria
