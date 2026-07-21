from __future__ import annotations

import base64
import os
import requests
from pydantic import BaseModel

from app.reflection.settings_store import load_reflection_settings


class GitHubFile(BaseModel):
    path: str
    name: str
    sha: str
    html_url: str


class GitHubReflectionClient:
    BASE_URL = "https://api.github.com"

    def __init__(self) -> None:
        saved_settings = load_reflection_settings()
        saved_enabled = bool(saved_settings.get("enabled"))
        self.token = os.getenv("GITHUB_REFLECTIONS_PAT")
        self.repo = (
            str(saved_settings.get("repo") or "").strip() if saved_enabled else ""
            or os.getenv("GITHUB_REFLECTIONS_REPO")
        )
        self.branch = (
            str(saved_settings.get("branch") or "").strip() if saved_enabled else ""
            or os.getenv("GITHUB_REFLECTIONS_BRANCH", "main")
        )
        self.timeout = float(os.getenv("GITHUB_REFLECTIONS_TIMEOUT_SECONDS", "30"))

        if not self.token or not self.repo:
            raise ValueError(
                "Missing GitHub reflection config. Set GITHUB_REFLECTIONS_PAT and GITHUB_REFLECTIONS_REPO."
            )

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, path: str, *, params: dict | None = None) -> dict | list:
        response = requests.get(
            f"{self.BASE_URL}{path}",
            headers=self.headers,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _put(self, path: str, *, data: dict | None = None) -> dict | list:
        response = requests.put(
            f"{self.BASE_URL}{path}",
            headers=self.headers,
            json=data or {},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_latest_commit_sha(self) -> str:
        payload = self._get(f"/repos/{self.repo}/commits/{self.branch}")
        if not isinstance(payload, dict):
            raise ValueError("Unexpected GitHub response when reading latest commit.")
        return str(payload["sha"])

    def list_reflection_source_files(self, path: str = "") -> list[GitHubFile]:
        files: list[GitHubFile] = []
        payload = self._get(f"/repos/{self.repo}/contents/{path}")
        if not isinstance(payload, list):
            raise ValueError("Unexpected GitHub contents response.")

        for item in payload:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            name = str(item.get("name") or "")
            item_path = str(item.get("path") or "")

            if item_type == "dir":
                if name.startswith(".") or name == "archives":
                    continue
                files.extend(self.list_reflection_source_files(item_path))
                continue

            if item_type != "file":
                continue
            if name == "README.md":
                continue
            if not any(name.endswith(extension) for extension in (".md", ".json", ".html")):
                continue

            files.append(
                GitHubFile(
                    path=item_path,
                    name=name,
                    sha=str(item.get("sha") or ""),
                    html_url=str(item.get("html_url") or ""),
                )
            )
        return files

    def list_markdown_files(self, path: str = "") -> list[GitHubFile]:
        return [
            file_info
            for file_info in self.list_reflection_source_files(path)
            if file_info.name.endswith(".md")
        ]

    def get_file_content(self, path: str) -> str:
        payload = self._get(
            f"/repos/{self.repo}/contents/{path}",
            params={"ref": self.branch},
        )
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected GitHub file response for {path}")

        encoded = str(payload.get("content") or "")
        if not encoded:
            raise ValueError(f"No content returned for {path}")

        content_bytes = base64.b64decode(encoded)
        return content_bytes.decode("utf-8")

    def get_file_entry(self, path: str) -> dict:
        payload = self._get(
            f"/repos/{self.repo}/contents/{path}",
            params={"ref": self.branch},
        )
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected GitHub file response for {path}")
        return payload

    def get_file_metadata(self, path: str) -> dict[str, str]:
        payload = self._get(
            f"/repos/{self.repo}/commits",
            params={"path": path, "per_page": 1, "sha": self.branch},
        )
        if not isinstance(payload, list) or not payload:
            return {}

        latest = payload[0]
        commit = latest.get("commit", {}) if isinstance(latest, dict) else {}
        committer = commit.get("committer", {}) if isinstance(commit, dict) else {}
        return {
            "last_modified": str(committer.get("date") or ""),
            "commit_sha": str(latest.get("sha") or ""),
        }

    def build_raw_url(self, path: str) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/{path}"

    def update_file_content(self, *, path: str, content: str, message: str) -> dict:
        entry = self.get_file_entry(path)
        sha = str(entry.get("sha") or "")
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "branch": self.branch,
        }
        if sha:
            payload["sha"] = sha
        result = self._put(f"/repos/{self.repo}/contents/{path}", data=payload)
        if not isinstance(result, dict):
            return {}
        return result
