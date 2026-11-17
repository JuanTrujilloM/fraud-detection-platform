SET 'table.exec.source.idle-timeout' = '30 s';

CREATE TABLE eventos (
  event_type   STRING,
  id_tarjeta   BIGINT,
  id_comercio  BIGINT,
  monto        DOUBLE,
  event_time   TIMESTAMP_LTZ(3),
  WATERMARK FOR event_time AS event_time - INTERVAL '10' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'eventos',
  'properties.bootstrap.servers' = '172.16.3.113:19092,172.16.3.113:29092,172.16.3.113:39092',
  'properties.group.id' = 'flink-deteccion',
  'scan.startup.mode' = 'latest-offset',
  'format' = 'json',
  'json.timestamp-format.standard' = 'ISO-8601'
);

CREATE TABLE alertas_streaming (
  id_comercio     BIGINT,
  window_start    TIMESTAMP(3),
  window_end      TIMESTAMP(3),
  tarjetas        BIGINT,
  monto_promedio  DOUBLE
) WITH (
  'connector' = 'kafka',
  'topic' = 'alertas-streaming',
  'properties.bootstrap.servers' = '172.16.3.113:19092,172.16.3.113:29092,172.16.3.113:39092',
  'format' = 'json'
);

INSERT INTO alertas_streaming
SELECT id_comercio, window_start, window_end, tarjetas, monto_promedio
FROM (
  SELECT id_comercio, window_start, window_end,
         COUNT(DISTINCT id_tarjeta) AS tarjetas,
         AVG(monto) AS monto_promedio
  FROM TABLE(
    HOP(TABLE eventos, DESCRIPTOR(event_time), INTERVAL '1' MINUTE, INTERVAL '5' MINUTES)
  )
  WHERE event_type = 'AUTORIZACION'
  GROUP BY id_comercio, window_start, window_end
)
WHERE tarjetas >= 3 AND monto_promedio < 20000;
