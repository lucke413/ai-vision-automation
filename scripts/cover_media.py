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
from typing import Iterator
from urllib.parse import quote, unquote, urlsplit

import requests
from PIL import Image, ImageColor, ImageEnhance, ImageOps


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_HEADERS = {"User-Agent": "AI-Vision-Cover/2.0 (https://aivision.altervista.org/)"}
MODEL_ID = "SG161222/Realistic_Vision_V5.1_noVAE"
MODEL_REVISION = "1e9f017a7b1eaefb63a1900ea6c5953d2739fd21"
SAFETY_MODEL_ID = "CompVis/stable-diffusion-safety-checker"
SAFETY_MODEL_REVISION = "cb41f3a270d63d454d385fc2e4f571c487c253c5"
CREATIVE_COMMONS = re.compile(r"^https://creativecommons\.org/(?:licenses/by(?:-sa)?/(?:2\.0|2\.5|3\.0|4\.0)|publicdomain/(?:zero|mark)/1\.0)/?$")
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")
MODEL_LOCK = Lock()
COVER_SIZE = (1280, 720)
EDITORIAL_LIGHT = "High detail editorial photograph, bright soft daylight, light midtones, neutral shadows, true colors"
NEGATIVE_PROMPT = "illustration, painting, 3d render, CGI, neon, dim subject, silhouette, text, logo, watermark, blur, duplicates"
AI_CREDIT = "Illustrazione generata con IA"


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


def commons_photos(image_url: str, subject: str, title: str, session: requests.Session) -> Iterator[tuple[str, CoverCredit]]:
    """Offer verified candidates in search order so a broken thumbnail can be skipped."""
    file_title = commons_file_title(image_url)
    terms = normalized(subject)
    if not file_title and (len(terms.split()) < 2 or f" {terms} " not in f" {normalized(title)} "):
        return
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
        return

    for page in sorted(pages, key=lambda row: row.get("index", 0)):
        filename = page.get("title", "").removeprefix("File:")
        if not filename.casefold().endswith(PHOTO_EXTENSIONS):
            continue
        if not file_title and f" {terms} " not in f" {normalized(filename)} ":
            continue
        for photo in page.get("imageinfo", []):
            width, height = photo.get("width", 0), photo.get("height", 0)
            if width < 1080 or height < 608 or width < height:
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
            yield image, CoverCredit(credit_text + " · immagine ridimensionata e ritagliata", source,
                                     license_name, license_url)


@lru_cache(maxsize=1)
def load_image_model():
    import torch
    from diffusers import DPMSolverMultistepScheduler, StableDiffusionPipeline
    from diffusers.pipelines.stable_diffusion.safety_checker import StableDiffusionSafetyChecker
    from transformers import CLIPImageProcessor

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    safety_checker = StableDiffusionSafetyChecker.from_pretrained(
        SAFETY_MODEL_ID, revision=SAFETY_MODEL_REVISION, weights_only=True,
    )
    processor = CLIPImageProcessor.from_pretrained(SAFETY_MODEL_ID, revision=SAFETY_MODEL_REVISION)
    model = StableDiffusionPipeline.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, use_safetensors=True, torch_dtype=torch.float32,
        safety_checker=safety_checker, feature_extractor=processor,
    )
    model.scheduler = DPMSolverMultistepScheduler.from_config(
        model.scheduler.config, algorithm_type="dpmsolver++", solver_type="midpoint",
        solver_order=2, final_sigmas_type="zero", use_karras_sigmas=True,
    )
    return model


def generate_ai_cover(draft: dict) -> bytes:
    """Generate a daylight photograph with one alternate take if the first fails inspection."""
    title = str(draft.get("title") or "").strip()
    scene = str(draft.get("cover_prompt") or "").strip()[:300]
    if not scene:
        scene = "A practical real-world scene illustrating " + title[:140]
    seed = int.from_bytes(hashlib.sha256(title.encode()).digest()[:4], "big")
    try:
        import torch

        for index, lighting in enumerate((EDITORIAL_LIGHT, "Clear daylight product photograph, soft front fill illumination")):
            prompt = f"{scene}. {lighting}. Single prominent subject filling the center, natural materials, editorial photograph."
            with MODEL_LOCK, torch.inference_mode():
                result = load_image_model()(
                    prompt, negative_prompt=NEGATIVE_PROMPT, width=896, height=512,
                    num_inference_steps=12, guidance_scale=5.0,
                    generator=torch.Generator().manual_seed(seed + index),
                )
            if any(result.nsfw_content_detected or []):
                continue
            frame = ImageOps.fit(result.images[0].convert("RGB"), COVER_SIZE, Image.Resampling.LANCZOS)
            if not cover_exposure(frame).has_detail:
                continue
            image = grade_ai_cover(frame)
            center = image.crop((224, 135, 1056, 655))
            if cover_exposure(image).usable and cover_exposure(center).median >= 82:
                return encode_cover_jpeg(image)
        raise CoverUnavailable("Il generatore non ha restituito una copertina sufficientemente nitida e luminosa.")
    except (ImportError, OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        if isinstance(exc, CoverUnavailable):
            raise
        raise CoverUnavailable(f"Generazione copertina IA fallita ({type(exc).__name__}: {exc}).") from exc


@dataclass(frozen=True)
class CoverExposure:
    median: int
    high: int
    spread: int
    shadow_fraction: float

    @property
    def dark(self) -> bool:
        return (self.median < 91 and self.high < 146) or self.shadow_fraction > 0.57

    @property
    def has_detail(self) -> bool:
        return self.spread >= 35

    @property
    def usable(self) -> bool:
        return not self.dark and self.has_detail and self.median < 244


def cover_exposure(image: Image.Image) -> CoverExposure:
    thumbnail = ImageOps.fit(image.convert("L"), (160, 90), Image.Resampling.BILINEAR)
    values = sorted(thumbnail.getdata())
    return CoverExposure(values[7200], values[12240], values[13680] - values[1440],
                         sum(value < 54 for value in values) / len(values))


def grade_ai_cover(image: Image.Image) -> Image.Image:
    """Open the midtones while preserving the peak brightness and deepest blacks."""
    rgb = image.convert("RGB")
    exposure = cover_exposure(rgb)
    if exposure.dark:
        gamma = max(0.47, min(0.83, exposure.median / 115))
        curve = [round(255 * (level / 255) ** gamma) for level in range(256)]
        rgb = rgb.point(curve * 3)
    return ImageEnhance.Color(rgb).enhance(1.08)


def encode_cover_jpeg(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=91, optimize=True)
    return output.getvalue()


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
        "cover_prompt": "Close-up of one black wireless headphone set resting on a pale oak table against a light blue wall, light from the front",
    }))
