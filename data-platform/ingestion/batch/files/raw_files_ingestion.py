import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3

_DATASET_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PROCESSED_DIR = "_processed"
_CHUNK_BYTES = 1024 * 1024


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **fields,
    }
    print(json.dumps(payload, sort_keys=True, default=str))


def validate_dataset(dataset: str) -> str:
    if not _DATASET_PATTERN.fullmatch(dataset):
        raise ValueError(
            f"Invalid dataset {dataset!r}: use lowercase letters, digits and '_'"
        )
    return dataset


def validate_run_id(run_id: str) -> str:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(
            "run_id must contain only letters, numbers, '.', '_' or '-', "
            "must start with a letter or number, and must have at most 128 characters"
        )
    return run_id


def list_landing_files(
    s3: Any, bucket: str, landing_prefix: str, dataset: str
) -> List[Dict[str, Any]]:
    
    prefix = f"{landing_prefix.strip('/')}/{dataset}/"
    files: List[Dict[str, Any]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            relative = key[len(prefix):]
            if not relative or key.endswith("/"):
                continue
            if relative.split("/")[0] == _PROCESSED_DIR:
                continue
            files.append({"key": key, "relative": relative, "size": item["Size"]})
    return sorted(files, key=lambda f: f["key"])


def profile_file(s3: Any, bucket: str, key: str) -> Dict[str, Any]:
   
    body = s3.get_object(Bucket=bucket, Key=key)["Body"]
    digest = hashlib.sha256()
    newlines = 0
    size = 0
    last_byte = b""
    first_line = bytearray()
    header_done = False
    for chunk in body.iter_chunks(chunk_size=_CHUNK_BYTES):
        if not chunk:
            continue
        digest.update(chunk)
        size += len(chunk)
        newlines += chunk.count(b"\n")
        last_byte = chunk[-1:]
        if not header_done:
            position = chunk.find(b"\n")
            if position == -1:
                first_line.extend(chunk)
            else:
                first_line.extend(chunk[:position])
                header_done = True

    total_lines = newlines + (1 if size and last_byte != b"\n" else 0)
    header = first_line.decode("utf-8-sig", errors="replace").strip("\r\n")
    return {
        "size_bytes": size,
        "sha256": digest.hexdigest(),
        "header": header,
        "data_lines": max(total_lines - 1, 0),
    }


def normalize_header(header: str) -> List[str]:
    return [column.strip().strip('"').lower() for column in header.split(",")]


def ingest_dataset(
    s3: Any,
    *,
    bucket: str,
    dataset: str,
    run_id: str,
    landing_prefix: str = "landing",
    raw_prefix: str = "raw/files",
    source_system: str = "coopandina-files",
    expected_header: Optional[str] = None,
    ingested_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    dataset = validate_dataset(dataset)
    run_id = validate_run_id(run_id)
    ingested_at = ingested_at or datetime.now(timezone.utc)
    ingestion_date = ingested_at.date().isoformat()

    files = list_landing_files(s3, bucket, landing_prefix, dataset)
    if not files:
        log_event("raw_files_no_new_files", dataset=dataset, run_id=run_id)
        return {"dataset": dataset, "run_id": run_id, "status": "no_files", "files": 0}

    expected = normalize_header(expected_header) if expected_header else None
    profiles = []
    for file in files:
        profile = profile_file(s3, bucket, file["key"])
        if profile["size_bytes"] == 0 or not profile["header"]:
            raise ValueError(f"Empty file or missing header: s3://{bucket}/{file['key']}")
        if expected and normalize_header(profile["header"]) != expected:
            raise ValueError(
                f"Unexpected header in s3://{bucket}/{file['key']}: "
                f"{profile['header']!r} (expected {expected_header!r})"
            )
        profiles.append({**file, **profile})

    raw_base = (
        f"{raw_prefix.strip('/')}/{dataset}/"
        f"_ingestion_date={ingestion_date}/_run_id={run_id}"
    )
    manifest_files = []
    for profile in profiles:
        raw_key = f"{raw_base}/{profile['relative']}"
        s3.copy(
            {"Bucket": bucket, "Key": profile["key"]},
            bucket,
            raw_key,
        )
        copied = s3.head_object(Bucket=bucket, Key=raw_key)["ContentLength"]
        if copied != profile["size_bytes"]:
            raise RuntimeError(
                f"Size mismatch copying {profile['key']}: "
                f"{profile['size_bytes']} != {copied}"
            )
        manifest_files.append(
            {
                "source_key": profile["key"],
                "raw_key": raw_key,
                "size_bytes": profile["size_bytes"],
                "sha256": profile["sha256"],
                "header": profile["header"],
                "data_lines": profile["data_lines"],
            }
        )

    manifest = {
        "dataset": dataset,
        "source_system": source_system,
        "run_id": run_id,
        "ingested_at": ingested_at.isoformat(timespec="seconds"),
        "file_count": len(manifest_files),
        "files": manifest_files,
    }
    s3.put_object(
        Bucket=bucket,
        Key=f"{raw_base}/_manifest.json",
        Body=json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
        ContentType="application/json",
    )

    processed_base = f"{landing_prefix.strip('/')}/{_PROCESSED_DIR}/{dataset}/{run_id}"
    for profile in profiles:
        s3.copy(
            {"Bucket": bucket, "Key": profile["key"]},
            bucket,
            f"{processed_base}/{profile['relative']}",
        )
        s3.delete_object(Bucket=bucket, Key=profile["key"])

    result = {
        "dataset": dataset,
        "run_id": run_id,
        "status": "ingested",
        "files": len(manifest_files),
        "data_lines": sum(f["data_lines"] for f in manifest_files),
        "raw_path": f"s3://{bucket}/{raw_base}/",
    }
    log_event("raw_files_ingested", **result)
    return result


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--run_id", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--landing_prefix", default="landing")
    parser.add_argument("--raw_prefix", default="raw/files")
    parser.add_argument("--source_system", default="coopandina-files")
    parser.add_argument("--expected_header", default=None)
    # Glue agrega argumentos propios (--JOB_NAME, --scriptLocation...): se ignoran.
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    ingest_dataset(
        boto3.client("s3"),
        bucket=args.bucket,
        dataset=args.dataset,
        run_id=args.run_id,
        landing_prefix=args.landing_prefix,
        raw_prefix=args.raw_prefix,
        source_system=args.source_system,
        expected_header=args.expected_header or None,
    )


if __name__ == "__main__":
    main()
