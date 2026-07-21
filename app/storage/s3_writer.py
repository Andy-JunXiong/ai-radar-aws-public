import json
from datetime import datetime
from pathlib import Path

import boto3

from app.config import settings


class S3Writer:
    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self.region = settings.aws_region
        self.s3_client = boto3.client("s3", region_name=self.region)

    def get_today_str(self) -> str:
        return datetime.now(settings.timezone).strftime("%Y-%m-%d")

    def upload_json(self, data: dict | list, s3_key: str) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2)

        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )

    def upload_text(
        self,
        text: str,
        s3_key: str,
        *,
        content_type: str = "text/plain",
    ) -> None:
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=text.encode("utf-8"),
            ContentType=content_type,
        )

    def _build_dedup_key(self, item: dict) -> str:
        """
        Generate a unique key for signals.
        Priority:
        1. URL
        2. title + source
        """
        url = (
            item.get("url")
            or item.get("link")
            or ""
        ).strip().lower()
        if url:
            return f"url::{url}"

        title = (item.get("title") or "").strip().lower()
        source = (item.get("source") or "").strip().lower()

        return f"title::{title}::{source}"

    def _load_existing_history_keys(self, base_prefix: str, filename: str):
        paginator = self.s3_client.get_paginator("list_objects_v2")
        existing_keys = set()

        for page in paginator.paginate(
            Bucket=self.bucket,
            Prefix=f"{base_prefix}/",
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]

                if not key.endswith(filename):
                    continue

                if "/latest/" in key:
                    continue

                try:
                    response = self.s3_client.get_object(
                        Bucket=self.bucket,
                        Key=key,
                    )

                    data = json.loads(response["Body"].read())

                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get("items", [])
                    else:
                        items = []

                    for item in items:
                        existing_keys.add(self._build_dedup_key(item))

                except Exception:
                    continue

        return existing_keys

    def upload_json_with_history(
        self,
        data: dict | list,
        base_prefix: str,
        filename: str,
    ) -> tuple[str, str]:
        today = self.get_today_str()

        history_key = f"{base_prefix}/{today}/{filename}"
        latest_key = f"{base_prefix}/latest/{filename}"

        if isinstance(data, dict):
            items = data.get("items", [])
        else:
            items = data

        print("===== CHECK HISTORY SIGNALS =====")

        # Try load latest signals instead of scanning full history
        existing_keys = set()
        items_latest = []

        try:
            latest_key = f"{base_prefix}/latest/{filename}"

            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=latest_key,
            )

            data = json.loads(response["Body"].read())

            if isinstance(data, list):
                items_latest = data
            elif isinstance(data, dict):
                items_latest = data.get("items", [])
            else:
                items_latest = []

            for item in items_latest:
                existing_keys.add(self._build_dedup_key(item))

        except Exception:
            # latest may not exist on first run
            pass

        print("existing signals:", len(existing_keys))

        new_items = []

        for item in items:
            key = self._build_dedup_key(item)

            if key in existing_keys:
                continue

            new_items.append(item)

        print("new signals:", len(new_items))

        if not new_items:
            print("No new signals today. Skip writing history.")
            return history_key, latest_key

        body = json.dumps(new_items, ensure_ascii=False, indent=2)

        # merge with latest
        merged = items_latest + new_items

        merged_body = json.dumps(merged, ensure_ascii=False, indent=2)

        # update latest
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=latest_key,
            Body=merged_body.encode("utf-8"),
            ContentType="application/json",
        )

        # write history
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=history_key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )

        print("History written:", history_key)
        print("Latest updated:", latest_key)

        return history_key, latest_key

    def upload_file(self, local_path: str | Path, s3_key: str) -> None:
        self.s3_client.upload_file(str(local_path), self.bucket, s3_key)
