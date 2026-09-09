from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

OFFICIAL_HOME = "https://www.faw-tokico.com/"
OUT_DIR = Path("src/cdc_analyzer/assets")
USER_AGENT = "Mozilla/5.0 CDC-Test-Data-Analyzer/1.0"


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs):
        values = {str(k).lower(): str(v or "") for k, v in attrs}
        if tag.lower() == "img" and values.get("src"):
            self.images.append(values)
        elif tag.lower() == "link" and values.get("href"):
            self.links.append(values)


def _get(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(req, timeout=30) as response:
        data = response.read()
        content_type = response.headers.get("Content-Type", "")
    return data, content_type


def _extension(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico"}:
        return suffix
    ct = content_type.lower()
    if "svg" in ct:
        return ".svg"
    if "png" in ct:
        return ".png"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "webp" in ct:
        return ".webp"
    if "icon" in ct:
        return ".ico"
    return ".bin"


def _score_image(attrs: dict[str, str], order: int) -> int:
    src = attrs.get("src", "").lower()
    text = " ".join(
        [src, attrs.get("alt", "").lower(), attrs.get("class", "").lower(), attrs.get("id", "").lower()]
    )
    score = 0
    if "logo" in text:
        score += 120
    if "brand" in text:
        score += 60
    if "tokico" in text or "faw" in text or "富奥" in text or "东机工" in text:
        score += 90
    if any(token in text for token in ("header", "head", "top")):
        score += 25
    if src.endswith(".svg"):
        score += 15
    if src.endswith(".png"):
        score += 12
    if order < 8:
        score += 10 - order
    if any(token in text for token in ("search", "icon", "arrow", "more", "qr", "wechat", "wx", "bg-", "/m/")):
        score -= 100
    return score


def find_logo_url(html: str) -> str:
    parser = AssetParser()
    parser.feed(html)
    candidates: list[tuple[int, str]] = []
    for order, attrs in enumerate(parser.images):
        src = attrs.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue
        candidates.append((_score_image(attrs, order), urljoin(OFFICIAL_HOME, src)))

    # Some sites use a CSS background for the header logo. Search the raw HTML as a fallback.
    for match in re.findall(r"(?:src|href|url\()\s*[=:'\"(]*\s*([^'\"\s)>]+(?:logo|Logo|LOGO)[^'\"\s)>]*)", html):
        candidates.append((130, urljoin(OFFICIAL_HOME, match.rstrip(")"))))

    # Favicon is a last-resort official-brand fallback, never preferred over an actual logo.
    for link in parser.links:
        rel = link.get("rel", "").lower()
        href = link.get("href", "").strip()
        if href and "icon" in rel:
            candidates.append((5, urljoin(OFFICIAL_HOME, href)))

    if not candidates:
        raise RuntimeError("No image candidates were found on the official company website.")

    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_url = candidates[0]
    print("Official-site image candidates:")
    for score, url in candidates[:10]:
        print(f"  score={score:4d}  {url}")
    if best_score < 20:
        raise RuntimeError(f"No sufficiently likely logo candidate found. Best score={best_score}: {best_url}")
    return best_url


def main() -> int:
    homepage_bytes, _ = _get(OFFICIAL_HOME)
    html = homepage_bytes.decode("utf-8", errors="ignore")
    logo_url = find_logo_url(html)
    logo_bytes, content_type = _get(logo_url)
    ext = _extension(logo_url, content_type)
    if ext == ".bin":
        raise RuntimeError(f"Unsupported logo content type: {content_type!r} from {logo_url}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("faw_tokico_logo.*"):
        old.unlink()
    output = OUT_DIR / f"faw_tokico_logo{ext}"
    output.write_bytes(logo_bytes)
    (OUT_DIR / "logo_source.txt").write_text(
        f"Official company website: {OFFICIAL_HOME}\nLogo asset: {logo_url}\n",
        encoding="utf-8",
    )
    print(f"Saved official logo: {output} ({len(logo_bytes):,} bytes)")
    print(f"Source: {logo_url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
