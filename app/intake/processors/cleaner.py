import re
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    if not text:
        return ""

    # Remove HTML first.
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(separator=" ", strip=True)

    # Collapse whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned

def build_short_summary(text: str, max_chars: int = 220) -> str:
    if not text:
        return ""

    text = text.strip()
    if len(text) <= max_chars:
        return text

    return text[:max_chars].rstrip() + "..."
