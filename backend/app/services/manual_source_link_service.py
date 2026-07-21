import re
from typing import Any


SOURCE_URL_PATTERN = re.compile(r"(?im)^\s*Source URL:\s*(https?://\S+)\s*$")


def extract_manual_source_urls(files: list[dict[str, Any]] | None) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for item in files or []:
        if not isinstance(item, dict):
            continue

        candidates = [
            item.get("source_url"),
            item.get("url"),
            item.get("link"),
        ]
        preview_text = item.get("preview_text")
        if isinstance(preview_text, str):
            candidates.extend(SOURCE_URL_PATTERN.findall(preview_text))

        for raw_url in candidates:
            url = str(raw_url or "").strip()
            if not url or not url.lower().startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)

    return urls


def apply_manual_source_url_metadata(session: dict[str, Any]) -> dict[str, Any]:
    urls = extract_manual_source_urls(session.get("files") if isinstance(session, dict) else None)
    if not urls:
        return session

    session["source_urls"] = urls
    primary_url = urls[0]
    for candidate in (session.get("source_url"), session.get("url"), session.get("link")):
        candidate_url = str(candidate or "").strip()
        if candidate_url.lower().startswith(("http://", "https://")):
            primary_url = candidate_url
            break
    session["source_url"] = primary_url
    session["url"] = primary_url
    session["link"] = primary_url
    return session
