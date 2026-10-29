#!/usr/bin/env python3
"""Pubblica o pianifica gli articoli generati su WordPress.

Il modulo è volutamente separato dalla pipeline RSS/Gemini. In assenza di
``WP_DRY_RUN=false`` lavora in sola simulazione e non invia post a WordPress.

Gestisce:
- categorie macro di AI Vision;
- creazione/riuso dei tag;
- immagine dalla fonte o da OpenGraph;
- copertina grafica locale di riserva quando non c'è un'immagine scaricabile;
- sei orari giornalieri distribuiti in Europe/Rome;
- report JSON anche in caso di errori su singoli articoli.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import struct
import time
import random
import unicodedata
import zlib
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from requests.auth import HTTPBasicAuth


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "article_drafts.json"
OUTPUT_FILE = BASE_DIR / "data" / "wp_publish_report.json"

VERSION = "2.4"
REQUEST_TIMEOUT = 30
MAX_IMAGE_BYTES = 10 * 1024 * 1024
USER_AGENT = "AI-Vision-WordPress-Publisher/1.0"

DEFAULT_TIMEZONE = "Europe/Rome"
DEFAULT_SLOT_TIMES = "08:00,10:30,14:00,16:30,18:30,20:30"

MACRO_CATEGORIES = (
    "News",
    "AI pratica",
    "Tool e Servizi",
    "Tecnologia e prodotti",
    "Gaming e console",
    "Casa smart",
    "Accessori e postazioni",
    "Sicurezza",
    "Guide",
    "Confronti",
    "Offerte",
)

SOURCE_CATEGORY_MAP = {
    "AI": "AI pratica",
    "Software & App": "Tool e Servizi",
    "Sicurezza": "Sicurezza",
    "Offerte & Prezzi": "Offerte",
    "Smartphone & Mobile": "Tecnologia e prodotti",
    "PC & Hardware": "Tecnologia e prodotti",
    "Gaming": "Gaming e console",
    "Casa smart": "Casa smart",
    "Accessori e postazioni": "Accessori e postazioni",
    "Gadget & Consumer Tech": "Tecnologia e prodotti",
    "Streaming & Entertainment": "Tecnologia e prodotti",
    "Tecnologia": "Tecnologia e prodotti",
}

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MIN_PUBLISH_WORDS = 500
PUBLIC_FORBIDDEN_PATTERNS = (
    re.compile(r"\bprima della pubblicazione\b", re.IGNORECASE),
    re.compile(r"\b(?:da|dati? da) verificare\b", re.IGNORECASE),
    re.compile(r"\b(?:secondo|stando a|come riportato da) (?:la )?fonte\b", re.IGNORECASE),
    re.compile(r"\bla fonte (?:riporta|segnala|fornita|indica)\b", re.IGNORECASE),
    re.compile(r"\b(?:questa bozza (?:editoriale|generata)|bozza interna|fact[_ -]?check|istruzioni (?:interne|editoriali))\b", re.IGNORECASE),
)


class PublisherError(RuntimeError):
    """Errore che riguarda un singolo articolo o la configurazione."""


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:180] or "ai-vision-articolo"


def normalize_tag(value: Any) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:50]


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise PublisherError(f"File non trovato: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PublisherError(f"JSON non valido: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PublisherError(f"Formato JSON non valido: {path}")
    return data


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def get_timezone() -> ZoneInfo:
    name = os.environ.get("WP_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise PublisherError(f"Fuso orario non valido: {name}") from exc


def parse_slot_times() -> list[dt_time]:
    raw = os.environ.get("WP_SLOT_TIMES", DEFAULT_SLOT_TIMES)
    result: list[dt_time] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            hour, minute = (int(part) for part in token.split(":", 1))
            value = dt_time(hour=hour, minute=minute)
        except (TypeError, ValueError) as exc:
            raise PublisherError(f"Orario WP non valido: {token}") from exc
        result.append(value)
    if not result:
        raise PublisherError("WP_SLOT_TIMES non contiene orari validi.")
    return sorted(set(result))


def next_publication_times(count: int, now: datetime | None = None) -> list[datetime]:
    if count <= 0:
        return []
    tz = get_timezone()
    current = (now or datetime.now(timezone.utc)).astimezone(tz)
    slots = parse_slot_times()
    result: list[datetime] = []
    day_offset = 0
    while len(result) < count and day_offset < 14:
        current_date = current.date() + timedelta(days=day_offset)
        for slot in slots:
            candidate = datetime.combine(current_date, slot, tzinfo=tz)
            if candidate <= current + timedelta(minutes=2):
                continue
            result.append(candidate)
            if len(result) == count:
                break
        day_offset += 1
    if len(result) != count:
        raise PublisherError("Impossibile costruire gli orari di pubblicazione.")
    return result


def category_for(draft: dict) -> str:
    category = str(draft.get("category") or "Tecnologia")
    story_type = str(draft.get("story_type") or "NEWS")
    title = str(draft.get("title") or "").lower()

    if story_type == "OFFERTA" or category == "Offerte & Prezzi":
        return "Offerte"
    if story_type == "GUIDA":
        return "Guide"
    if story_type == "SICUREZZA" or category == "Sicurezza":
        return "Sicurezza"
    if category == "AI":
        return "AI pratica"
    if story_type == "ANALISI" and re.search(r"\b(vs|contro|confronto|quale scegliere)\b", title):
        return "Confronti"
    if category in SOURCE_CATEGORY_MAP:
        return SOURCE_CATEGORY_MAP[category]
    if story_type == "NEWS":
        return "News"
    return "Tecnologia e prodotti"


def markdown_to_html(markdown_text: str) -> str:
    """Conversione minima sicura per i paragrafi prodotti dal generatore."""
    text = str(markdown_text or "").replace("\r\n", "\n").strip()
    if not text:
        return ""

    blocks = re.split(r"\n\s*\n", text)
    html_blocks: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        content = " ".join(lines)
        heading_match = re.match(r"^(#{2,3})\s+(.+)$", content)
        if heading_match:
            level = min(3, len(heading_match.group(1)))
            value = html.escape(heading_match.group(2).strip())
            html_blocks.append(f"<h{level}>{value}</h{level}>")
            continue
        numbered = [re.match(r"^\d+[.)]\s+(.+)$", line) for line in lines]
        if numbered and all(numbered):
            html_blocks.append("<ol>" + "".join(f"<li>{html.escape(m.group(1))}</li>" for m in numbered) + "</ol>")
            continue
        if all(line.startswith(("- ", "* ")) for line in lines):
            entries = "".join(
                f"<li>{html.escape(line[2:].strip())}</li>" for line in lines
            )
            html_blocks.append(f"<ul>{entries}</ul>")
            continue
        escaped = html.escape(content)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
        html_blocks.append(f"<p>{escaped}</p>")
    return "\n".join(html_blocks)



def guide_visual_kind(draft: dict) -> str:
    """Sceglie un mockup di risultato coerente con l'argomento della guida."""
    slug = str(draft.get("topic_slug") or draft.get("slug") or "").lower()
    title = str(draft.get("title") or "").lower()
    value = slug + " " + title
    if any(key in value for key in ("excel", "foglio", "dati", "servizi", "abbonament")):
        return "spreadsheet"
    if "presentazione" in value or "slide" in value:
        return "slides"
    if "locandina" in value:
        return "poster"
    if "thumbnail" in value or "copertina" in value:
        return "thumbnail"
    if "storyboard" in value:
        return "storyboard"
    if any(key in value for key in ("video", "animare", "clip")):
        return "video"
    if any(key in value for key in ("immagin", "ritoccare", "foto")):
        return "image"
    if any(key in value for key in ("settimana", "settimanale", "pianificare", "piano creato")):
        return "weekly_planner"
    if "email" in value:
        return "email"
    if any(key in value for key in ("riunione", "attività", "scadenze")):
        return "tasks"
    if any(key in value for key in ("curriculum", "cv")):
        return "resume"
    if any(key in value for key in ("quiz", "interrogazione", "studio", "ripasso")):
        return "quiz"
    if "spesa" in value:
        return "shopping"
    if any(key in value for key in ("viaggio", "itinerario")):
        return "itinerary"
    if "reclamo" in value:
        return "document"
    return "document"


def _guide_font(size: int, bold: bool = False):
    from PIL import ImageFont
    names = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _guide_base(title: str, variant: int = 0):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (1200, 675), "#eef4fa" if variant == 0 else "#f7f1eb")
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((34, 28, 1166, 647), radius=30, fill="#ffffff", outline="#bfd0df", width=2)
    pen.text((72, 58), "AI VISION", font=_guide_font(24, True), fill="#176087")
    pen.text((72, 96), "ESEMPIO DI RISULTATO" if variant == 0 else "VARIANTE DEL RISULTATO",
             font=_guide_font(19, True), fill="#6b7d8e")
    clean = " ".join(str(title or "Guida pratica").split())
    if len(clean) > 62:
        clean = clean[:59].rsplit(" ", 1)[0] + "…"
    pen.text((72, 132), clean, font=_guide_font(30, True), fill="#17324a")
    return image, pen


def _draw_spreadsheet(draft: dict, variant: int) -> bytes:
    import io
    image, pen = _guide_base(draft.get("title", ""), variant)
    x0, y0, x1, y1 = 82, 212, 1118, 594
    pen.rounded_rectangle((x0, y0, x1, y1), radius=18, fill="#f8fbfd", outline="#a9bdc9", width=2)
    pen.rectangle((x0, y0, x1, y0+56), fill="#1f7a5c")
    for i, label in enumerate(("Voce", "Gen", "Feb", "Var.%", "Stato")):
        pen.text((x0+20+i*190, y0+15), label, font=_guide_font(20, True), fill="white")
    rows = [
        ("Progetto A","120","145","+20,8%","OK"),
        ("Progetto B","88","92","+4,5%","OK"),
        ("Progetto C","64","51","-20,3%","Rivedi"),
    ]
    for r, row in enumerate(rows):
        y=y0+72+r*65
        if r % 2 == 1:
            pen.rectangle((x0+2,y-8,x1-2,y+47),fill="#edf5f2")
        for i,val in enumerate(row):
            pen.text((x0+20+i*190,y),val,font=_guide_font(20),fill="#20384d")
    if variant:
        pen.rounded_rectangle((710,425,1060,565),radius=12,fill="#eaf2f8")
        for b in ((755,520,800,548),(830,485,875,548),(905,450,950,548),(980,410,1025,548)):
            pen.rounded_rectangle(b,radius=5,fill="#397fa5")
        pen.text((730,438),"Andamento",font=_guide_font(18,True),fill="#244966")
    out=io.BytesIO(); image.save(out,format="PNG",optimize=True); return out.getvalue()


def _draw_slides(draft: dict, variant: int) -> bytes:
    import io
    image, pen = _guide_base(draft.get("title", ""), variant)
    slides=[(95,235,585,535),(615,255,1095,555)] if not variant else [(105,260,470,510),(495,225,850,475),(875,280,1110,475)]
    for idx,(x0,y0,x1,y1) in enumerate(slides):
        pen.rounded_rectangle((x0,y0,x1,y1),radius=18,fill="#172d4b" if idx%2==0 else "#f1d7a9",outline="#8ea7ba",width=2)
        if idx%2==0:
            pen.text((x0+30,y0+38),"PROGETTO",font=_guide_font(24,True),fill="#80e0cf")
            pen.text((x0+30,y0+82),"Una idea per slide",font=_guide_font(26,True),fill="white")
            pen.rectangle((x0+30,y0+150,x1-35,y0+158),fill="#6b8298")
            pen.rectangle((x0+30,y0+183,x1-100,y0+191),fill="#6b8298")
        else:
            pen.text((x0+28,y0+35),"RISULTATI",font=_guide_font(24,True),fill="#694a1e")
            for b,h in enumerate((70,120,160,95)):
                bx=x0+55+b*80
                pen.rounded_rectangle((bx,y1-55-h,bx+46,y1-55),radius=5,fill="#3f7397")
    out=io.BytesIO(); image.save(out,format="PNG",optimize=True); return out.getvalue()


def _draw_poster(draft: dict, variant: int) -> bytes:
    import io
    image, pen = _guide_base(draft.get("title", ""), variant)
    pen.rounded_rectangle((175,205,500,605),radius=24,fill="#102744")
    pen.ellipse((235,255,445,465),fill="#7be1d0")
    pen.ellipse((285,305,395,415),fill="#ffcf78")
    pen.text((215,485),"SCIENZA",font=_guide_font(35,True),fill="white")
    pen.text((215,535),"OPEN DAY",font=_guide_font(24,True),fill="#9fe9dd")
    pen.rounded_rectangle((555,245,1075,545),radius=26,fill="#f5efe5")
    pen.text((605,292),"Locandina pronta",font=_guide_font(34,True),fill="#17324a")
    pen.text((605,345),"• gerarchia chiara",font=_guide_font(23),fill="#355269")
    pen.text((605,390),"• spazio per titolo",font=_guide_font(23),fill="#355269")
    pen.text((605,435),"• contrasto leggibile",font=_guide_font(23),fill="#355269")
    out=io.BytesIO(); image.save(out,format="PNG",optimize=True); return out.getvalue()


def _draw_image_result(draft: dict, variant: int) -> bytes:
    import io
    image, pen = _guide_base(draft.get("title", ""), variant)
    pen.rounded_rectangle((110,220,1090,585),radius=28,fill="#142a42")
    pen.rectangle((175,300,1025,525),fill="#294b64")
    pen.rectangle((230,420,930,455),fill="#a8754e")
    pen.rectangle((255,455,285,535),fill="#805d44")
    pen.rectangle((900,455,930,535),fill="#805d44")
    pen.rounded_rectangle((450,330,690,415),radius=10,fill="#ecf4fb")
    pen.rectangle((470,350,670,395),fill="#7bdacb")
    pen.ellipse((755,315,830,390),fill="#ffd47e")
    pen.line((792,390,760,450),fill="#ffd47e",width=10)
    pen.ellipse((320,330,365,375),fill="#79bd80")
    pen.ellipse((345,345,395,400),fill="#6da772")
    pen.rectangle((340,390,375,430),fill="#c98959")
    if variant:
        pen.rounded_rectangle((500,470,820,535),radius=14,fill="#1d3852")
        pen.text((540,488),"variante raffinata",font=_guide_font(22,True),fill="#9fe9dd")
    out=io.BytesIO(); image.save(out,format="PNG",optimize=True); return out.getvalue()


def _draw_storyboard(draft: dict, variant: int, video: bool = False) -> bytes:
    import io
    image, pen = _guide_base(draft.get("title", ""), variant)
    for i,(x0,y0,x1,y1) in enumerate(((90,230,390,440),(450,230,750,440),(810,230,1110,440))):
        pen.rounded_rectangle((x0,y0,x1,y1),radius=16,fill=("#1c334d" if i!=1 else "#dfeaf2"),outline="#98adbd",width=2)
        pen.ellipse((x0+110,y0+55,x0+190,y0+135),fill="#78daca")
        pen.rectangle((x0+75,y0+150,x1-75,y0+166),fill="#7c91a4")
        if video:
            cx=(x0+x1)//2; cy=(y0+y1)//2
            pen.polygon([(cx-18,cy-25),(cx-18,cy+25),(cx+27,cy)],fill="#ffffff")
        pen.text((x0+18,y1+18),f"SCENA {i+1}",font=_guide_font(18,True),fill="#355269")
    out=io.BytesIO(); image.save(out,format="PNG",optimize=True); return out.getvalue()


def _draw_document(draft: dict, variant: int, mode: str) -> bytes:
    import io
    image, pen = _guide_base(draft.get("title", ""), variant)
    pen.rounded_rectangle((230,215,970,600),radius=16,fill="#ffffff",outline="#c1ced9",width=2)
    if mode == "email":
        pen.rectangle((230,215,970,275),fill="#e8f1f7")
        pen.text((265,232),"Oggetto: proposta chiara e sintetica",font=_guide_font(22,True),fill="#244966")
        y=315
        for width in (610,560,640,500,590):
            pen.rounded_rectangle((270,y,270+width,y+13),radius=5,fill="#cddbe5"); y+=42
    elif mode == "resume":
        pen.rectangle((230,215,425,600),fill="#173b59")
        pen.ellipse((285,260,370,345),fill="#8bdcca")
        pen.text((470,255),"ESPERIENZA",font=_guide_font(24,True),fill="#173b59")
        for y in (315,365,445,495): pen.rectangle((470,y,890,y+10),fill="#ccd8e1")
    elif mode == "tasks":
        for x,label in ((260,"DA FARE"),(500,"IN CORSO"),(740,"FATTO")):
            pen.text((x,250),label,font=_guide_font(18,True),fill="#244966")
            for j in range(2):
                pen.rounded_rectangle((x,295+j*115,x+190,385+j*115),radius=12,fill="#edf3f7",outline="#c5d2dd")
    elif mode == "quiz":
        pen.text((280,255),"DOMANDA 1",font=_guide_font(23,True),fill="#215b7b")
        pen.text((280,300),"Qual è l'idea principale?",font=_guide_font(28,True),fill="#17324a")
        for j,label in enumerate(("A","B","C")):
            y=370+j*60
            pen.ellipse((280,y,315,y+35),fill="#79daca")
            pen.text((292,y+5),label,font=_guide_font(17,True),fill="#17324a")
            pen.rectangle((335,y+12,795,y+22),fill="#d1dde6")
    elif mode == "shopping":
        pen.text((280,250),"LISTA DELLA SPESA",font=_guide_font(26,True),fill="#215b7b")
        for j,label in enumerate(("Ortofrutta","Dispensa","Freschi","Casa")):
            y=315+j*58
            pen.rounded_rectangle((280,y,310,y+30),radius=6,outline="#3b8a6f",width=3)
            pen.text((335,y),label,font=_guide_font(22),fill="#314d61")
    elif mode == "itinerary":
        pen.line((330,285,330,540),fill="#4b88a8",width=7)
        for j,(time,label) in enumerate((("09:00","Partenza"),("11:30","Tappa"),("14:00","Pausa"),("17:30","Rientro"))):
            y=295+j*75
            pen.ellipse((312,y-5,348,y+31),fill="#7bdacb")
            pen.text((390,y-4),time,font=_guide_font(20,True),fill="#215b7b")
            pen.text((500,y-4),label,font=_guide_font(20),fill="#314d61")
    else:
        pen.text((280,250),"DOCUMENTO PRONTO",font=_guide_font(25,True),fill="#215b7b")
        for y,w in ((320,560),(360,610),(400,520),(475,600),(515,450)):
            pen.rectangle((280,y,280+w,y+11),fill="#cedae4")
    out=io.BytesIO(); image.save(out,format="PNG",optimize=True); return out.getvalue()



def _result_canvas(background: str = "#e9eef5"):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (1200, 675), background)
    pen = ImageDraw.Draw(image)
    return image, pen


def _save_result_png(image) -> bytes:
    import io
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _draw_weekly_planner_v2(draft: dict, variant: int) -> bytes:
    image, pen = _result_canvas("#e7edf4" if variant == 0 else "#f0ebe5")
    # Applicazione/calendario: il risultato finale, non una spiegazione.
    pen.rounded_rectangle((42, 32, 1158, 640), radius=26, fill="#ffffff", outline="#c5d0da", width=2)
    pen.rounded_rectangle((42, 32, 1158, 106), radius=26, fill="#20364f")
    pen.rectangle((42, 82, 1158, 106), fill="#20364f")
    pen.text((78, 54), "Piano settimanale", font=_guide_font(27, True), fill="#ffffff")
    pen.text((890, 58), "LUN 19  →  VEN 23", font=_guide_font(18, True), fill="#b8d9e9")

    left=118; top=148; right=1120; bottom=602
    days=("LUN 19","MAR 20","MER 21","GIO 22","VEN 23")
    colw=(right-left)//5
    for i,day in enumerate(days):
        x=left+i*colw
        pen.text((x+18,118),day,font=_guide_font(18,True),fill="#314b61")
        pen.line((x,top,x,bottom),fill="#d7e0e7",width=1)
    pen.line((right,top,right,bottom),fill="#d7e0e7",width=1)

    times=("09:00","11:00","13:00","15:00","17:00")
    for r,t in enumerate(times):
        y=top+r*90
        pen.text((58,y-10),t,font=_guide_font(16),fill="#6b7d8c")
        pen.line((left,y,right,y),fill="#e4e9ee",width=1)
    pen.line((left,bottom,right,bottom),fill="#e4e9ee",width=1)

    events = [
        (0,0,2,"Focus progetto","#8fd9cf"),
        (0,3,1,"Email / follow-up","#f5c879"),
        (1,0,1,"Priorità 1","#8fb8e8"),
        (1,2,2,"Lavoro concentrato","#b7a3e3"),
        (2,1,1,"Riunione","#f19e9e"),
        (2,3,1,"Revisione","#8fd9cf"),
        (3,0,2,"Priorità 2","#f5c879"),
        (3,3,1,"Pausa + buffer","#b9d7a6"),
        (4,1,2,"Chiusura attività","#8fb8e8"),
    ]
    if variant:
        events = [
            (0,0,1,"Pianificazione","#8fb8e8"),
            (0,2,2,"Blocco focus","#8fd9cf"),
            (1,1,1,"Revisione","#f5c879"),
            (1,3,1,"Buffer","#b9d7a6"),
            (2,0,2,"Progetto A","#b7a3e3"),
            (3,1,2,"Progetto B","#8fd9cf"),
            (4,0,1,"Follow-up","#f19e9e"),
            (4,2,2,"Chiusura settimana","#8fb8e8"),
        ]
    for day,row,span,label,color in events:
        x=left+day*colw+8; y=top+row*90+8
        h=span*90-16
        pen.rounded_rectangle((x,y,x+colw-16,y+h),radius=10,fill=color)
        pen.text((x+12,y+12),label,font=_guide_font(15,True),fill="#17324a")
    return _save_result_png(image)


def _draw_spreadsheet_v2(draft: dict, variant: int) -> bytes:
    image, pen = _result_canvas("#e8ecef")
    pen.rounded_rectangle((35, 28, 1165, 646), radius=22, fill="#ffffff", outline="#c2ccd2", width=2)
    pen.rectangle((35,28,1165,82),fill="#217346")
    pen.text((62,43),"Budget_progetto.xlsx",font=_guide_font(21,True),fill="white")
    pen.rectangle((35,82,1165,126),fill="#f4f6f7")
    pen.text((64,93),"fx",font=_guide_font(18,True),fill="#68767f")
    formula='=SE(E6>0;"OK";"RIVEDI")' if not variant else '=SOMMA(C6:D6)'
    pen.rounded_rectangle((100,90,1115,119),radius=5,fill="#ffffff",outline="#cbd3d8")
    pen.text((118,95),formula,font=_guide_font(17),fill="#273944")
    x0,y0=82,158; rowh=52; colw=160
    headers=("Attività","Ore st.","Ore reali","Scarto","Stato","Costo")
    for i,h in enumerate(headers):
        x=x0+i*colw
        pen.rectangle((x,y0,x+colw,y0+rowh),fill="#dfeee6")
        pen.text((x+12,y0+15),h,font=_guide_font(17,True),fill="#234c37")
    rows=[
        ("Analisi","4","3,5","-0,5","OK","€ 140"),
        ("Bozza","6","7","+1","RIVEDI","€ 280"),
        ("Grafica","5","4","-1","OK","€ 160"),
        ("Revisione","3","2,5","-0,5","OK","€ 100"),
        ("Totale","18","17","-1","","€ 680"),
    ]
    for r,row in enumerate(rows):
        y=y0+(r+1)*rowh
        for i,val in enumerate(row):
            x=x0+i*colw
            pen.rectangle((x,y,x+colw,y+rowh),fill=("#f8fbf9" if r%2==0 else "#ffffff"),outline="#e2e7e9")
            pen.text((x+12,y+15),val,font=_guide_font(17, r==4),fill="#263b45")
    # Piccolo grafico dentro il foglio.
    gx,gy=760,475
    pen.rounded_rectangle((gx,gy,1115,620),radius=10,fill="#f7f9fa",outline="#d9e1e4")
    for i,h in enumerate((52,88,67,112)):
        bx=gx+48+i*68
        pen.rectangle((bx,598-h,bx+38,598),fill="#4c9a70")
    pen.text((gx+16,gy+12),"Ore per fase",font=_guide_font(16,True),fill="#39535f")
    return _save_result_png(image)


def _draw_slides_v2(draft: dict, variant: int) -> bytes:
    image, pen = _result_canvas("#e6e9ee")
    pen.rounded_rectangle((30,25,1170,650),radius=22,fill="#ffffff",outline="#c4cbd4",width=2)
    pen.rectangle((30,25,1170,80),fill="#c94b36")
    pen.text((60,42),"Presentazione progetto",font=_guide_font(21,True),fill="white")
    # miniature
    for i in range(4):
        y=112+i*120
        pen.rounded_rectangle((55,y,245,y+98),radius=8,fill="#f2f2f2",outline="#c7ccd1")
        if i==1:
            pen.rectangle((60,y+5,240,y+93),fill="#17324a")
            pen.text((78,y+29),"RISULTATI",font=_guide_font(17,True),fill="#8fe0d1")
        else:
            pen.rectangle((72,y+25,220,y+34),fill="#aeb7bf")
            pen.rectangle((72,y+47,195,y+55),fill="#d0d6db")
    # slide principale
    x0,y0,x1,y1=290,112,1125,590
    pen.rounded_rectangle((x0,y0,x1,y1),radius=12,fill=("#132a46" if not variant else "#f5efe5"),outline="#bdc6cd")
    fg="#ffffff" if not variant else "#2f3f4b"
    accent="#86e0cf" if not variant else "#bf6d44"
    pen.text((350,165),"RISULTATI DEL PROGETTO",font=_guide_font(30,True),fill=accent)
    pen.text((350,218),"Dati chiari, una storia per slide",font=_guide_font(26,True),fill=fg)
    # chart
    basey=485
    for i,h in enumerate((105,155,205,135)):
        bx=395+i*105
        pen.rounded_rectangle((bx,basey-h,bx+62,basey),radius=7,fill=accent)
    pen.text((820,345),"+28%",font=_guide_font(50,True),fill=accent)
    pen.text((820,405),"obiettivo raggiunto",font=_guide_font(20),fill=fg)
    return _save_result_png(image)


def _draw_poster_v2(draft: dict, variant: int) -> bytes:
    image, pen = _result_canvas("#dadfe6" if not variant else "#efe7db")
    # Ombra + poster finito.
    pen.rounded_rectangle((315,45,905,630),radius=18,fill="#b6bec7")
    pen.rounded_rectangle((300,32,890,617),radius=18,fill=("#10263f" if not variant else "#f6d08c"))
    if not variant:
        pen.ellipse((510,105,780,375),fill="#73d9c8")
        pen.ellipse((570,160,720,310),fill="#ffcb70")
        pen.text((355,90),"OPEN DAY",font=_guide_font(30,True),fill="#ffffff")
        pen.text((355,420),"FUTURO",font=_guide_font(64,True),fill="#ffffff")
        pen.text((355,492),"Tecnologia • Creatività • Idee",font=_guide_font(23),fill="#a8e8dc")
        pen.rounded_rectangle((355,545,565,585),radius=8,fill="#ffffff")
        pen.text((382,554),"18 NOVEMBRE",font=_guide_font(18,True),fill="#10263f")
    else:
        pen.rectangle((300,390,890,617),fill="#17324a")
        pen.text((355,90),"MOSTRA",font=_guide_font(30,True),fill="#6b4d2c")
        pen.text((355,145),"NUOVE",font=_guide_font(60,True),fill="#17324a")
        pen.text((355,212),"VISIONI",font=_guide_font(60,True),fill="#17324a")
        pen.ellipse((600,95,820,315),fill="#d8654f")
        pen.text((355,455),"SABATO 21 • ORE 17:00",font=_guide_font(22,True),fill="#ffffff")
        pen.text((355,510),"Ingresso libero",font=_guide_font(21),fill="#b7d7e9")
    return _save_result_png(image)


def _draw_image_result_v2(draft: dict, variant: int) -> bytes:
    # Illustrazione completa: niente intestazione, niente schema di passaggi.
    image, pen = _result_canvas("#12263b" if not variant else "#efe0cb")
    if not variant:
        pen.rectangle((0,430,1200,675),fill="#6e4b36")
        pen.rectangle((150,470,1050,520),fill="#aa7957")
        pen.rectangle((195,520,230,650),fill="#7c563e")
        pen.rectangle((970,520,1005,650),fill="#7c563e")
        pen.rounded_rectangle((430,300,750,455),radius=14,fill="#edf4fa")
        pen.rectangle((455,325,725,425),fill="#6dcfc0")
        pen.ellipse((875,220,970,315),fill="#ffd173")
        pen.line((920,310,865,465),fill="#e9b657",width=16)
        pen.ellipse((215,245,285,315),fill="#66a66e")
        pen.ellipse((260,265,330,345),fill="#7bb37a")
        pen.rectangle((250,340,295,420),fill="#c78555")
        pen.text((420,80),"CREATIVE WORKSPACE",font=_guide_font(38,True),fill="#9fe9dd")
    else:
        pen.rectangle((0,445,1200,675),fill="#8f6b50")
        pen.rounded_rectangle((350,195,850,520),radius=26,fill="#ffffff")
        pen.rectangle((390,240,810,440),fill="#d9a168")
        pen.ellipse((500,275,660,435),fill="#365f7a")
        pen.ellipse((555,315,625,385),fill="#f0c76b")
        pen.text((425,465),"poster editoriale",font=_guide_font(28,True),fill="#17324a")
    return _save_result_png(image)

def guide_result_image(draft: dict, variant: int = 0) -> bytes:
    kind = guide_visual_kind(draft)
    if kind == "weekly_planner": return _draw_weekly_planner_v2(draft, variant)
    if kind == "spreadsheet": return _draw_spreadsheet_v2(draft, variant)
    if kind == "slides": return _draw_slides_v2(draft, variant)
    if kind in {"poster", "thumbnail"}: return _draw_poster_v2(draft, variant)
    if kind == "image": return _draw_image_result_v2(draft, variant)
    if kind == "storyboard": return _draw_storyboard(draft, variant, False)
    if kind == "video": return _draw_storyboard(draft, variant, True)
    if kind in {"email","resume","tasks","quiz","shopping","itinerary"}:
        return _draw_document(draft, variant, kind)
    return _draw_document(draft, variant, "document")


def guide_infographic(draft: dict) -> bytes:
    """Copertina della guida: mostra il risultato ottenibile, non i passaggi."""
    return guide_result_image(draft, 0)

def guide_prompt_blocks(draft: dict) -> str:
    """Copy-ready example prompts shown only in practical guides."""
    if draft.get("editorial_kind") not in {"GUIDA", "TUTORIAL"}:
        return ""
    def block(title: str, raw: str) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""
        # The <pre> element preserves the newlines for easy copy/paste.
        return (
            '<section class="av-practical-prompt" style="padding:16px 20px;margin:22px 0;'
            'border:1px solid #c9d9e6;border-radius:12px;background:#f3f8fc;color:#162c42">'
            '<h2 style="font-size:1.16em;margin:0 0 12px">' + html.escape(title) + '</h2>'
            '<p>Seleziona e copia il testo qui sotto, poi sostituisci le parti tra parentesi quadre.</p>'
            '<pre style="white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;'
            'font:inherit;background:#fff;color:#182a3d;border:1px solid #d4e0e7;'
            'border-radius:8px;padding:14px">' + html.escape(value) + '</pre>'
            '</section>'
        )
    return (
        block("Prompt semplice da copiare", draft.get("example_prompt", "")) +
        block("Prompt avanzato: più dettagli per risultati migliori", draft.get("advanced_prompt", ""))
    )


def guide_inline_diagram(draft: dict, style: str) -> bytes:
    """Illustrazione del risultato finale; i passaggi restano nel testo della guida."""
    return guide_result_image(draft, 0 if style in {"result", "prompt", "primary"} else 1)


def guide_inline_figures(draft: dict, client, slug: str) -> list[str]:
    """Carica un solo esempio interno, diverso dalla copertina e senza didascalia."""
    if draft.get("editorial_kind") not in {"GUIDA", "TUTORIAL"}:
        return []
    picture = guide_inline_diagram(draft, "variant")
    if client.dry_run:
        return ['<!-- risultato visivo simulato -->']
    title = str(draft.get("title") or "Guida pratica")
    media = client.upload_media(
        picture, slug + "-risultato.png",
        "image/png", f"Esempio del risultato per {title}", ""
    )
    url = str(media.get("source_url") or "")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc or not media.get("id"):
        raise PublisherError("Immagine didattica non caricata correttamente.")
    print("    Risultato visuale caricato:", media.get("id"))
    return [
        '<figure class="av-guide-example" style="margin:24px auto;max-width:900px">'
        '<img src="' + html.escape(url, quote=True) +
        '" alt="' + html.escape(f"Esempio del risultato per {title}", quote=True) +
        '" loading="lazy" decoding="async" style="display:block;width:100%;'
        'max-width:900px;height:auto;border-radius:10px" />'
        '</figure>'
    ]


def guide_place_figures(body: str, figures: list[str]) -> str:
    """Place images *inside* the relevant explanation, rather than at the end."""
    if not figures:
        return body
    if len(figures) != 1:
        raise PublisherError("La guida richiede una illustrazione valida.")
    # Una sola immagine del risultato, collocata prima delle verifiche finali.
    heading = re.search(r"<h2>Verifica del risultato</h2>", body, flags=re.IGNORECASE)
    if heading:
        body = body[:heading.start()] + figures[0] + "\n" + body[heading.start():]
    elif "</ol>" in body:
        body = body.replace("</ol>", "</ol>\n" + figures[0], 1)
    else:
        body += "\n" + figures[0]
    return body


def guide_resources(draft: dict) -> str:
    if draft.get("editorial_kind") not in {"GUIDA", "TUTORIAL"}:
        return ""
    allowed = {"chatgpt.com", "www.canva.com", "www.microsoft.com", "help.openai.com", "support.microsoft.com"}
    links = []
    for entry in draft.get("official_links", [])[:3]:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "")
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in allowed:
            continue
        links.append('<li><a href="' + html.escape(url, quote=True) + '" rel="noopener noreferrer">' + html.escape(str(entry.get("label") or "Documentazione ufficiale")) + '</a></li>')
    return '<h2>Prova lo strumento</h2><p>Qui trovi il servizio con cui mettere in pratica i prompt. Aprilo e segui la guida, senza bisogno di leggere manuali tecnici.</p><ul>' + ''.join(links) + '</ul>' if links else ""


def image_url_from_draft(draft: dict) -> str:
    for key in ("source_image_url", "image", "image_url"):
        value = str(draft.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


def extract_og_image(source_url: str, session: requests.Session) -> str:
    if not source_url:
        return ""
    try:
        response = session.get(
            source_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""

    markup = response.text[:750_000]
    patterns = (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, markup, flags=re.IGNORECASE)
        if match:
            candidate = html.unescape(match.group(1).strip())
            resolved = urljoin(source_url, candidate)
            if resolved.startswith(("http://", "https://")):
                return resolved
    return ""


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def fallback_png(category: str) -> bytes:
    """Crea una copertina grafica neutra senza dipendenze esterne."""
    width, height = 1200, 675
    digest = hashlib.sha256(category.encode("utf-8")).digest()
    base = (24 + digest[0] % 35, 36 + digest[1] % 35, 64 + digest[2] % 55)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            diagonal = ((x + y) // 90) % 2 == 0
            band = (x // 160) % 3 == 0
            r, g, b = base
            if diagonal:
                r = min(255, r + 22)
                g = min(255, g + 14)
            if band and 90 < y < 585:
                b = min(255, b + 28)
            raw.extend((r, g, b))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(
        b"IDAT", zlib.compress(bytes(raw), level=6)
    ) + png_chunk(b"IEND", b"")


def download_image(url: str, session: requests.Session) -> tuple[bytes, str] | None:
    if not url:
        return None
    try:
        response = session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    content = response.content
    if not content or len(content) > MAX_IMAGE_BYTES:
        return None
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix not in VALID_IMAGE_EXTENSIONS:
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(content_type, ".jpg")
    if content_type and not content_type.startswith("image/") and suffix not in VALID_IMAGE_EXTENSIONS:
        return None
    return content, suffix


class WordPressClient:
    def __init__(self, base_url: str, username: str, app_password: str, dry_run: bool):
        self.dry_run = dry_run
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/wp-json"):
            self.api_root = f"{self.base_url}/wp/v2"
        else:
            self.api_root = f"{self.base_url}/wp-json/wp/v2"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        if username or app_password:
            self.session.auth = HTTPBasicAuth(username, app_password)
        self.category_cache: dict[str, dict] = {}
        self.tag_cache: dict[str, dict] = {}

    def _url(self, resource: str) -> str:
        return f"{self.api_root}/{resource.lstrip('/')}"

    def get_or_create_term(self, kind: str, name: str) -> dict:
        cache = self.category_cache if kind == "categories" else self.tag_cache
        key = name.casefold()
        if key in cache:
            return cache[key]
        if self.dry_run:
            result = {"id": None, "name": name, "slug": slugify(name), "dry_run": True}
            cache[key] = result
            return result

        response = self.session.get(
            self._url(kind),
            params={"search": name, "per_page": 100},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        matches = response.json()
        for match in matches:
            if str(match.get("name", "")).casefold() == key:
                cache[key] = match
                return match

        response = self.session.post(
            self._url(kind),
            json={"name": name, "slug": slugify(name)},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 400:
            # Race condition o termine già esistente: la rilettura restituisce
            # una LISTA, non un singolo termine. Normalizzala prima di restituire
            # il risultato, altrimenti category.get()/tag.get() può interrompere
            # la pubblicazione del singolo articolo.
            response = self.session.get(
                self._url(kind),
                params={"search": name, "per_page": 100},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            matches = response.json()
            if isinstance(matches, list):
                for match in matches:
                    if isinstance(match, dict) and str(match.get("name", "")).casefold() == key:
                        cache[key] = match
                        return match
                raise PublisherError(f"Termine WordPress già presente ma non recuperabile: {name}")
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise PublisherError(f"Risposta WordPress non valida per il termine: {name}")
        cache[key] = result
        return result

    def existing_post(self, slug: str) -> dict | None:
        if self.dry_run:
            return None
        response = self.session.get(
            self._url("posts"),
            params={"slug": slug, "per_page": 1, "context": "edit"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        values = response.json()
        return values[0] if values else None

    def upload_media(self, content: bytes, filename: str, mime_type: str, alt_text: str, caption: str) -> dict:
        if self.dry_run:
            return {"id": None, "source_url": "dry-run", "alt_text": alt_text}
        response = None
        # Altervista può restituire 502/503/504 temporanei sull'endpoint media.
        # Ritenta lo stesso upload con backoff senza duplicare il post.
        for attempt in range(1, 5):
            try:
                response = self.session.post(
                    self._url("media"),
                    data=content,
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Type": mime_type,
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                if response.status_code not in (429, 502, 503, 504):
                    response.raise_for_status()
                    break
                print(
                    f"    WordPress media HTTP {response.status_code}, "
                    f"tentativo {attempt}/4."
                )
            except requests.exceptions.RequestException:
                if attempt >= 4:
                    raise
                print(f"    Errore rete upload media, tentativo {attempt}/4.")
            if attempt < 4:
                time.sleep(min(20.0, (2 ** attempt) + random.uniform(0.2, 0.8)))
        if response is None:
            raise PublisherError("Upload media non completato.")
        response.raise_for_status()
        media = response.json()
        media_id = media.get("id")
        if media_id:
            update = self.session.post(
                self._url(f"media/{media_id}"),
                json={"alt_text": alt_text, "caption": caption},
                timeout=REQUEST_TIMEOUT,
            )
            update.raise_for_status()
            media = update.json()
        return media

    def related_link(self, draft: dict, category_id: int | None) -> str:
        """Un solo collegamento pubblicato, pertinente e sullo stesso sito."""
        if self.dry_run or not category_id:
            return ""
        try:
            response = self.session.get(
                self._url("posts"),
                params={"status": "publish", "categories": category_id,
                        "per_page": 30, "_fields": "id,title,link,slug"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            stop = {"della", "delle", "dello", "degli", "come", "sono", "anche",
                    "questo", "quello", "ecco", "nuovo", "nuova", "disponibile"}
            def words(value):
                return {w for w in re.findall(r"[a-zà-ù0-9]+", value.lower())
                        if (len(w) >= 4 or (w.isdigit() and len(w) >= 2)) and w not in stop}
            target = words(str(draft.get("title") or "") + " " +
                           str(draft.get("focus_keyphrase") or ""))
            candidates = []
            own_slug = slugify(str(draft.get("slug") or draft.get("title") or ""))
            for post in response.json():
                link = str(post.get("link") or "")
                label = html.unescape(re.sub(r"<[^>]+>", "", str(post.get("title", {}).get("rendered") or "")))
                if (urlsplit(link).netloc != urlsplit(self.base_url).netloc
                        or urlsplit(link).scheme != "https" or post.get("slug") == own_slug):
                    continue
                overlap = target & words(label)
                if len(overlap) >= 2:
                    candidates.append((len(overlap), label, link))
            if not candidates:
                return ""
            _, label, link = max(candidates, key=lambda row: row[0])
            return '<p>Leggi anche: <a href="' + html.escape(link, quote=True) + '">' + html.escape(label) + '</a>.</p>'
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            print("AVVISO SEO: ricerca link interni non disponibile; pubblicazione invariata.")
            return ""

    def save_seo(self, post_id: int | None, draft: dict) -> str:
        if self.dry_run:
            return "dry_run"
        fields = {key: str(draft.get(key) or "").strip()
                  for key in ("focus_keyphrase", "seo_title", "seo_description")}
        fields = {key: value for key, value in fields.items() if value}
        if not post_id or not fields:
            return "missing_data"
        try:
            response = self.session.post(
                self._url(f"posts/{post_id}"),
                json={"aivision_seo": fields}, params={"context": "edit"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            saved = payload.get("aivision_seo", {}) if isinstance(payload, dict) else {}
            # Alcune installazioni/plugin WordPress restituiscono il campo SEO
            # in una forma diversa (per esempio una lista). I metadati SEO sono
            # facoltativi: una risposta inattesa non deve far risultare fallita
            # la pubblicazione dell'articolo già creato.
            if isinstance(saved, dict) and all(
                saved.get(key) == value for key, value in fields.items()
            ):
                return "saved"
            print("AVVISO SEO: metadati non confermati dal bridge; articolo pubblicato o programmato comunque.")
            return "bridge_unavailable"
        except (requests.RequestException, ValueError, AttributeError):
            print("AVVISO SEO: metadati non confermati; articolo programmato regolarmente.")
            return "warning"

    def create_post(self, payload: dict) -> dict:
        if self.dry_run:
            return {"id": None, "link": "dry-run", "status": "planned", "payload": payload}
        response = self.session.post(
            self._url("posts"),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


def image_mime(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix.lower(), "image/png")


def draft_items(data: dict) -> list[dict]:
    values = data.get("daily_items")
    if not isinstance(values, list):
        values = [item for item in data.get("items", []) if item.get("publication_slot") == "today"]
    return [item for item in values if isinstance(item, dict)]


def publish_one(
    draft: dict,
    planned_time: datetime,
    client: WordPressClient,
    session: requests.Session,
) -> dict:
    title = str(draft.get("title") or "").strip()
    if not title:
        raise PublisherError("Titolo mancante.")
    raw_body = str(draft.get("body_markdown") or "").strip()
    body = markdown_to_html(raw_body)
    if draft.get("editorial_kind") in {"GUIDA", "TUTORIAL"}:
        if not draft.get("example_prompt") or not draft.get("advanced_prompt") or not guide_resources(draft):
            raise PublisherError("Quality gate: guida priva di prompt o link pratici ufficiali.")
    # Amazon Associates: predisposizione sicura. Nessun link personale viene
    # pubblicato automaticamente su Altervista senza autorizzazione esplicita.
    if draft.get("affiliate_candidate"):
        print("    AFFILIAZIONE: articolo candidato; link personale non inserito (verifica autorizzazione Altervista).")
    if not body:
        raise PublisherError("Corpo articolo vuoto.")
    word_count = len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’‒–—-][\wÀ-ÖØ-öø-ÿ]+)*\b", raw_body, flags=re.UNICODE))
    if word_count < MIN_PUBLISH_WORDS:
        raise PublisherError(
            f"Quality gate: articolo di {word_count} parole; minimo {MIN_PUBLISH_WORDS}."
        )
    for pattern in PUBLIC_FORBIDDEN_PATTERNS:
        if pattern.search(raw_body):
            raise PublisherError(
                "Quality gate: rilevata una frase interna/di attribuzione vietata nel testo pubblico."
            )
    # Gli avvisi editoriali sono informativi: il generatore ha già tentato
    # l'espansione. Il publisher blocca solo violazioni effettive del gate.
    if draft.get("quality_warnings"):
        print(f"    AVVISO qualità: {title} -> {draft.get('quality_warnings')}")

    slug = slugify(str(draft.get("slug") or title))
    existing = client.existing_post(slug)
    if existing:
        return {"article_id": draft.get("article_id"), "title": title,
                "status": "already_exists", "wp_status": existing.get("status"),
                "post_id": existing.get("id"), "link": existing.get("link")}

    if draft.get("editorial_kind") in {"GUIDA", "TUTORIAL"}:
        figures = guide_inline_figures(draft, client, slug)
        body = guide_place_figures(body, figures)
        body += guide_prompt_blocks(draft)
    body += guide_resources(draft)

    category_name = category_for(draft)
    category = client.get_or_create_term("categories", category_name)
    category_ids = [category["id"]] if category.get("id") else []
    # Guide, Confronti e Offerte restano primarie; aggiunge la sezione tematica.
    topic = SOURCE_CATEGORY_MAP.get(str(draft.get("category") or ""))
    if topic in {"Gaming e console", "Casa smart", "Accessori e postazioni"} and topic != category_name:
        topic_term = client.get_or_create_term("categories", topic)
        if topic_term.get("id") and topic_term["id"] not in category_ids:
            category_ids.append(topic_term["id"])
    related = client.related_link(draft, category.get("id"))
    if related:
        body += "\n" + related
    raw_tags = draft.get("tags") if isinstance(draft.get("tags"), list) else []
    tags = []
    seen_tags: set[str] = set()
    for raw_tag in raw_tags:
        tag = normalize_tag(raw_tag)
        if not tag or tag.casefold() in seen_tags:
            continue
        seen_tags.add(tag.casefold())
        tags.append(client.get_or_create_term("tags", tag))

    source_url = str(draft.get("source_url") or "").strip()

    image_url = "" if draft.get("editorial_kind") else image_url_from_draft(draft)
    if client.dry_run:
        # Il dry-run non deve fare richieste esterne né scaricare immagini:
        # usa una copertina simulata e registra se una fonte era disponibile.
        image_origin = "dry_run_guide" if draft.get("editorial_kind") else ("dry_run_source" if image_url else "dry_run_fallback")
        downloaded = (guide_infographic(draft), ".png") if draft.get("editorial_kind") else (fallback_png(category_name), ".png")
    else:
        image_origin = "original_guide_infographic" if draft.get("editorial_kind") else "rss_or_draft"
        downloaded = (guide_infographic(draft), ".png") if draft.get("editorial_kind") else (download_image(image_url, session) if image_url else None)
        if downloaded is None and source_url and not draft.get("editorial_kind"):
            image_url = extract_og_image(source_url, session)
            image_origin = "open_graph"
            downloaded = download_image(image_url, session) if image_url else None
        if downloaded is None:
            downloaded = (fallback_png(category_name), ".png")
            image_origin = "generated_fallback"
    image_bytes, suffix = downloaded
    filename = f"{slugify(title)}{suffix}"
    media = client.upload_media(
        image_bytes,
        filename,
        image_mime(suffix),
        alt_text=title,
        caption="",
    )

    local_date = planned_time.strftime("%Y-%m-%dT%H:%M:%S")
    utc_date = planned_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    payload = {
        "title": title,
        "content": body,
        "excerpt": str(draft.get("excerpt") or ""),
        "slug": slug,
        "status": "future",
        "date": local_date,
        "date_gmt": utc_date,
        "categories": category_ids,
        "tags": [tag["id"] for tag in tags if tag.get("id")],
        "featured_media": media.get("id") or 0,
    }
    created = client.create_post(payload)
    seo_status = client.save_seo(created.get("id"), draft)
    return {
        "seo_status": seo_status,
        "article_id": draft.get("article_id"),
        "title": title,
        "status": "planned" if client.dry_run else "scheduled",
        "wp_status": created.get("status", "future" if not client.dry_run else "dry_run"),
        "post_id": created.get("id"),
        "link": created.get("link"),
        "scheduled_local": local_date,
        "scheduled_utc": utc_date,
        "category": category_name,
        "tags": [tag.get("name") for tag in tags],
        "image_origin": image_origin,
        "image_source_url": image_url or None,
        "media_id": media.get("id"),
    }


def main() -> int:
    data = load_json(INPUT_FILE)
    drafts = draft_items(data)
    dry_run = env_bool("WP_DRY_RUN", True)
    base_url = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
    username = os.environ.get("WP_USERNAME", "").strip()
    app_password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not dry_run and (not base_url or not username or not app_password):
        raise PublisherError(
            "Per la pubblicazione reale servono WP_BASE_URL, WP_USERNAME e WP_APP_PASSWORD."
        )
    if not drafts:
        output = {
            "publisher_version": VERSION,
            "status": "empty",
            "dry_run": dry_run,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requested": 0,
            "completed": 0,
            "errors": [],
            "items": [],
        }
        save_json(OUTPUT_FILE, output)
        print("WP PUBLISHER: nessun articolo giornaliero da pubblicare.")
        return 0

    client = WordPressClient(base_url, username, app_password, dry_run)
    schedule = next_publication_times(len(drafts))
    results: list[dict] = []
    errors: list[dict] = []
    used_slugs: set[str] = set()
    for draft, planned_time in zip(drafts, schedule):
        try:
            slug = slugify(str(draft.get("slug") or draft.get("title") or ""))
            if slug in used_slugs:
                raise PublisherError("Slug duplicato nello stesso lotto.")
            used_slugs.add(slug)
            results.append(publish_one(draft, planned_time, client, client.session))
            print(f"OK: {draft.get('title', '')} -> {planned_time.isoformat()}")
        except Exception as exc:
            error = {
                "article_id": draft.get("article_id"),
                "title": draft.get("title"),
                "error": f"{type(exc).__name__}: {exc}",
            }
            errors.append(error)
            print(f"AVVISO: articolo non pubblicato: {error['title']} — {error['error']}")

    output = {
        "publisher_version": VERSION,
        "status": "dry_run" if dry_run and not errors else ("ok" if not errors else "ok_with_warnings"),
        "dry_run": dry_run,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": os.environ.get("WP_TIMEZONE", DEFAULT_TIMEZONE),
        "slot_times": [value.strftime("%H:%M") for value in parse_slot_times()],
        "requested": len(drafts),
        "completed": len(results),
        "scheduled": sum(x.get("status") == "scheduled" for x in results),
        "already_existing": sum(x.get("status") == "already_exists" for x in results),
        "actually_online_verified": 0,
        "errors": errors,
        "items": results,
    }
    save_json(OUTPUT_FILE, output)
    print(f"WP PUBLISHER: {len(results)}/{len(drafts)} articoli elaborati.")
    print(f"Report: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PublisherError as exc:
        print(f"ERRORE: {exc}")
        raise SystemExit(1)