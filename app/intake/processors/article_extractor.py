import requests
from bs4 import BeautifulSoup


def fetch_article_text(url: str, timeout: int = 15) -> str:
    if not url:
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch article: {url} | error: {e}")
        return ""

    try:
        soup = BeautifulSoup(response.text, "html.parser")

    # Remove obvious noise first.
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

    # Prefer the article element.
        article = soup.find("article")
        if article:
            text = article.get_text(separator=" ", strip=True)
            return text

    # Fall back to the body when no article element exists.
        body = soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            return text

        return ""
    except Exception as e:
        print(f"Failed to parse article HTML: {url} | error: {e}")
        return ""
