"""Select reusable Wikimedia Commons photos and create original AI covers."""

from __future__ import annotations

import hashlib
import html
import io
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from statistics import median
from threading import Lock
from urllib.parse import quote, unquote, urlsplit

import requests
from PIL import Image, ImageColor, ImageEnhance, ImageOps, ImageStat


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_HEADERS = {"User-Agent": "AI-Vision-Cover/2.0 (https://aivision.altervista.org/)"}
MODEL_ID = "SimianLuo/LCM_Dreamshaper_v7"
MODEL_REVISION = "a85df6a8bd976cdd08b4fd8f3b73f229c9e54df5"
CREATIVE_COMMONS = re.compile(r"^https://creativecommons\.org/(?:licenses/by(?:-sa)?/(?:2\.0|2\.5|3\.0|4\.0)|publicdomain/(?:zero|mark)/1\.0)/?$")
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")
MODEL_LOCK = Lock()
EDITORIAL_LIGHT = "Bright editorial photography, clear directional light, rich natural colors, crisp subject contrast"


class CoverUnavailable(RuntimeError):
    """The article has no verified usable image."""


@dataclass(frozen=True)
class CoverCredit:
    text: str
    source_url: str = ""
    license_name: str = ""
    license_url: str = ""

    def markup(self) -> str:
        text = html.escape(self.text)
        links = []
        if safe_https_url(self.source_url):
            links.append(f'<a href="{html.escape(self.source_url, quote=True)}">Fonte foto</a>')
        if safe_https_url(self.license_url):
            name = html.escape(self.license_name or "Licenza")
            links.append(f'<a href="{html.escape(self.license_url, quote=True)}">{name}</a>')
        return " · ".join(filter(None, [text, *links]))


def safe_https_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return parts.scheme == "https" and bool(parts.hostname) and not parts.username
    except ValueError:
        return False


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", value.casefold()))


def commons_file_title(image_url: str) -> str:
    url = urlsplit(image_url)
    if url.scheme != "https":
        return ""
    path = unquote(url.path)
    if url.netloc == "commons.wikimedia.org" and path.startswith("/wiki/File:"):
        return path.removeprefix("/wiki/")
    if url.netloc in {"upload.wikimedia.org", "thumb.wikimedia.org"} and url.path.startswith("/wikipedia/commons/"):
        parts = unquote(url.path).split("/")
        return "File:" + (parts[-2] if "thumb" in parts else parts[-1])
    return ""


def commons_photo(image_url: str, subject: str, title: str, session: requests.Session) -> tuple[str, CoverCredit] | None:
    """Resolve a known Commons asset or search only for the exact named subject."""
    file_title = commons_file_title(image_url)
    terms = normalized(subject)
    if not file_title and (len(terms.split()) < 2 or f" {terms} " not in f" {normalized(title)} "):
        return None
    params = {
        "action": "query", "format": "json", "formatversion": 2, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1280,
        "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|Restrictions|Copyrighted",
    }
    if file_title:
        params["titles"] = file_title
    else:
        params.update(generator="search", gsrnamespace=6, gsrlimit=5,
                      gsrsearch=f'intitle:"{terms}" filetype:bitmap')
    try:
        response = session.get(COMMONS_API, headers=COMMONS_HEADERS, params=params, timeout=9)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", [])
    except (requests.RequestException, ValueError):
        return None

    for page in pages:
        filename = page.get("title", "").removeprefix("File:")
        if not filename.casefold().endswith(PHOTO_EXTENSIONS):
            continue
        if not file_title and f" {terms} " not in f" {normalized(filename)} ":
            continue
        for photo in page.get("imageinfo", []):
            width, height = photo.get("width", 0), photo.get("height", 0)
            if width < 800 or height < 400 or (not file_title and width < height):
                continue
            image = str(photo.get("thumburl") or photo.get("url") or "")
            if not safe_https_url(image) or urlsplit(image).netloc not in {"upload.wikimedia.org", "thumb.wikimedia.org"}:
                continue
            metadata = photo.get("extmetadata", {})
            license_name = str(metadata.get("LicenseShortName", {}).get("value") or "")
            license_url = str(metadata.get("LicenseUrl", {}).get("value") or "").replace("http://", "https://", 1)
            public_domain = (license_name.casefold() == "public domain"
                             and metadata.get("Copyrighted", {}).get("value") == "False")
            if metadata.get("Restrictions", {}).get("value"):
                continue
            if not CREATIVE_COMMONS.fullmatch(license_url) and not public_domain:
                continue
            if not CREATIVE_COMMONS.fullmatch(license_url):
                license_url = ""
            raw_artist = str(metadata.get("Artist", {}).get("value") or "")
            artist = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", raw_artist)).split())
            if not artist and "/licenses/" in license_url:
                continue
            credit_text = f"Foto: {artist}" if artist else "Foto in pubblico dominio"
            source = "https://commons.wikimedia.org/wiki/" + quote(page["title"].replace(" ", "_"), safe=":")
            return image, CoverCredit(credit_text + " · versioni ridimensionate/ritagliate", source,
                                     license_name, license_url)
    return None


@lru_cache(maxsize=1)
def load_image_model():
    import torch
    from diffusers import DiffusionPipeline

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    return DiffusionPipeline.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, use_safetensors=True, torch_dtype=torch.float32,
    )


def generate_ai_cover(draft: dict) -> bytes:
    """Generate one new image on the runner without using a paid API."""
    title = str(draft.get("title") or "").strip()
    scene = str(draft.get("cover_prompt") or "").strip()[:300]
    if not scene:
        scene = "Photographic editorial interpretation of " + title[:160]
    prompt = f"{EDITORIAL_LIGHT}. {scene}, clear focal subject, realistic texture, landscape, no text, no logos"
    seed = int.from_bytes(hashlib.sha256(title.encode()).digest()[:4], "big")
    try:
        import torch

        with MODEL_LOCK, torch.inference_mode():
            result = load_image_model()(prompt, width=640, height=384, num_inference_steps=6, guidance_scale=6.0,
                           generator=torch.Generator().manual_seed(seed))
        if any(result.nsfw_content_detected or []):
            raise CoverUnavailable("Il generatore ha respinto questa copertina.")
        image = ImageOps.fit(result.images[0].convert("RGB"), (1200, 675), Image.Resampling.LANCZOS)
        if max(high - low for low, high in image.getextrema()) < 24:
            raise CoverUnavailable("Il generatore ha restituito un'immagine vuota.")
        image = grade_ai_cover(image)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue()
    except (ImportError, OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        if isinstance(exc, CoverUnavailable):
            raise
        raise CoverUnavailable(f"Generazione copertina IA fallita ({type(exc).__name__}: {exc}).") from exc


def grade_ai_cover(image: Image.Image) -> Image.Image:
    """Lift deep midtones without brightening highlights or altering external photos."""
    luma = ImageStat.Stat(image.convert("L")).median[0]
    if luma < 115:
        gamma = max(0.72, min(1.0, luma / 115))
        curve = [round(255 * (level / 255) ** gamma) for level in range(256)]
        image = image.point(curve * 3)
    return ImageEnhance.Color(image).enhance(1.16)


def is_striped_cover(image: Image.Image) -> bool:
    """Match the retired covers by pixels, including resized JPEG versions."""
    width, height = image.size
    if width < 300 or abs(width / height - 16 / 9) > .02:
        return False
    pixels = image.convert("RGB").load()
    samples = []
    for y in range(45, 650, 49):
        for x in range(40, 1180, 57):
            if min((x + y) % 90, 90 - (x + y) % 90, x % 160, 160 - x % 160,
                   abs(y - 90), abs(y - 585)) < 14:
                continue
            red, green, blue = pixels[round(x * width / 1200), round(y * height / 675)]
            diagonal = ((x + y) // 90) % 2 == 0
            band = (x // 160) % 3 == 0 and 90 < y < 585
            samples.append((red - 22 * diagonal, green - 14 * diagonal, blue - 28 * band))
    base = tuple(median(channel) for channel in zip(*samples))
    if not all(low - 3 <= value <= high + 3 for value, (low, high) in
               zip(base, ((24, 58), (36, 70), (64, 118)))):
        return False
    matches = sum(max(abs(value - center) for value, center in zip(pixel, base)) <= 8
                  for pixel in samples)
    return matches >= .97 * len(samples)


RETIRED_CARD_COLORS = {
    ImageColor.getrgb(background): ImageColor.getrgb(accent)
    for background, accent in (
        ("#251933", "#f6af66"), ("#132e32", "#7ee4bf"), ("#352232", "#f8a8b6"),
        ("#351c25", "#ff9d85"), ("#1e2b39", "#f7d17f"), ("#292544", "#d3a8ff"),
        ("#293426", "#c7e895"), ("#193044", "#8ee0f3"), ("#343127", "#f4d48b"),
        ("#273044", "#b3c8fc"),
    )
}


def is_interim_card(image: Image.Image) -> bool:
    """Recognize the short-lived repeated graphic used as a placeholder."""
    width, height = image.size
    if width < 300 or abs(width / height - 16 / 9) > .02:
        return False
    pixels = image.convert("RGB").load()

    def sample(x, y):
        return pixels[round(x * width / 1200), round(y * height / 675)]

    background = sample(25, 25)
    accent = RETIRED_CARD_COLORS.get(background)
    return bool(accent and sample(1180, 655) == background and sample(95, 138) == background
                and sample(95, 152) == accent and sample(121, 152) == accent)


def is_retired_cover(image: Image.Image) -> bool:
    return is_interim_card(image) or is_striped_cover(image)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) != 2:
        raise SystemExit("Uso: python scripts/cover_media.py percorso-di-prova.jpg")
    Path(sys.argv[1]).write_bytes(generate_ai_cover({
        "title": "Come scegliere le cuffie wireless",
        "cover_prompt": "Charcoal over-ear headphones on a walnut desk in afternoon window light, studio still life",
    }))
