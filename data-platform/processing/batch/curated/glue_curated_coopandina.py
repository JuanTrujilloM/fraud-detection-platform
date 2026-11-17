import json
import sys
from datetime import datetime, timezone
from typing import Any

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import Window
from pyspark.sql import functions as F

from common_libs.schema_registry import get_entity_config
from common_libs.utils import format_utc_timestamp


REQUIRED_ARGUMENTS = [
    "JOB_NAME",
    "source",
    "run_id",
    "raw_path",
    "curated_path",
    "curated_database",
]


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": format_utc_timestamp(datetime.now(timezone.utc)),
        **fields,
    }
    print(json.dumps(payload, sort_keys=True, default=str))


def read_oltp(spark, raw_path: str, source: str):
    entity_config = get_entity_config(source)
    raw_df = spark.read.parquet(f"{raw_path}/operational/coopandina-postgresql/{source}/")
    order = Window.partitionBy(*entity_config.primary_key).orderBy(
        F.col(entity_config.watermark_column).desc(),
        F.col("_ingested_at").desc(),
    )
    latest_df = raw_df.withColumn("row_number", F.row_number().over(order)).filter(
        F.col("row_number") == 1
    )
    columns = []
    for i in range(len(raw_df.columns)):
        if not raw_df.columns[i].startswith("_"):
            columns.append(raw_df.columns[i])
    return raw_df, latest_df.select(*columns)


def read_eventos(spark, raw_path: str):
    raw_df = spark.read.option("recursiveFileLookup", "true").json(f"{raw_path}/eventos/")
    curated_df = (
        raw_df.filter(F.col("event_id").isNotNull() & F.col("event_type").isNotNull())
        .drop("_corrupt_record")
        .dropDuplicates(["event_id"])
        .withColumn("event_time", F.col("event_time").cast("timestamp"))
        .withColumn("ingested_at", F.col("ingested_at").cast("timestamp"))
        .withColumn("fecha_evento", F.to_date(F.col("event_time")))
    )
    return raw_df, curated_df


def read_contracargos(spark, raw_path: str):
    raw_df = (
        spark.read.option("header", "true")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "*.csv")
        .csv(f"{raw_path}/files/contracargos/")
    )
    curated_df = (
        raw_df.select(
            F.col("id_contracargo").cast("bigint").alias("id_contracargo"),
            F.col("id_autorizacion").cast("bigint").alias("id_autorizacion"),
            F.col("id_tarjeta").cast("bigint").alias("id_tarjeta"),
            F.col("ultimos_4").alias("ultimos_4"),
            F.col("monto").cast("decimal(14,2)").alias("monto"),
            F.col("fecha_compra").cast("date").alias("fecha_compra"),
            F.col("fecha_contracargo").cast("date").alias("fecha_contracargo"),
            F.col("motivo").alias("motivo"),
        )
        .filter(F.col("id_contracargo").isNotNull() & F.col("id_autorizacion").isNotNull())
        .dropDuplicates(["id_contracargo"])
    )
    return raw_df, curated_df


def run_job(args) -> None:
    spark_context = SparkContext.getOrCreate()
    glue_context = GlueContext(spark_context)
    spark = glue_context.spark_session
    spark.conf.set("spark.sql.session.timeZone", "UTC")

    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    source = args["source"]
    raw_path = args["raw_path"].rstrip("/")
    target_path = f"{args['curated_path'].rstrip('/')}/{source}/"
    table_name = f"{args['curated_database']}.{source}"

    if source == "eventos":
        raw_df, curated_df = read_eventos(spark, raw_path)
    elif source == "contracargos":
        raw_df, curated_df = read_contracargos(spark, raw_path)
    else:
        raw_df, curated_df = read_oltp(spark, raw_path, source)

    rows_read = raw_df.count()
    rows_written = curated_df.count()

    writer = curated_df.write.mode("overwrite").format("parquet").option("path", target_path)
    if source == "eventos":
        writer = writer.partitionBy("fecha_evento")
    writer.saveAsTable(table_name)

    log_event(
        "curated_completed",
        source=source,
        run_id=args["run_id"],
        rows_read=rows_read,
        rows_discarded=rows_read - rows_written,
        rows_written=rows_written,
        target_path=target_path,
        table=table_name,
    )
    job.commit()


def main() -> None:
    args = getResolvedOptions(sys.argv, REQUIRED_ARGUMENTS)
    run_job(args)


if __name__ == "__main__":
    main()
