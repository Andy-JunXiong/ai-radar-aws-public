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

        # 先移除明显噪音
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # 优先尝试 article 标签
        article = soup.find("article")
        if article:
            text = article.get_text(separator=" ", strip=True)
            return text

        # 如果没有 article，就退回 body
        body = soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            return text

        return ""
    except Exception as e:
        print(f"Failed to parse article HTML: {url} | error: {e}")
        return ""