SELECT
    h.anio,
    h.mes,
    h.hora,
    c.categoria,
    c.ciudad,
    h.canal,
    t.franquicia,
    COUNT(*) AS autorizaciones,
    SUM(CASE WHEN h.resultado = 'APROBADA' THEN 1 ELSE 0 END) AS aprobadas,
    SUM(h.es_fraude) AS fraudes,
    SUM(h.monto) AS monto,
    SUM(CASE WHEN h.es_fraude = 1 THEN h.monto ELSE 0 END) AS monto_fraude
FROM coopandina_analytics.hecho_autorizacion h
JOIN coopandina_analytics.dim_comercio c ON c.id_comercio = h.id_comercio
JOIN coopandina_analytics.dim_tarjeta t ON t.id_tarjeta = h.id_tarjeta
GROUP BY h.anio, h.mes, h.hora, c.categoria, c.ciudad, h.canal, t.franquicia
