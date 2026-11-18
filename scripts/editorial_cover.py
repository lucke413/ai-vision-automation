"""Original editorial covers and recognition of the retired striped artwork."""

import hashlib
import io
import re
from statistics import median

from PIL import Image, ImageDraw, ImageFont


COVER_SIZE = (1200, 675)

# Each illustration has its own subject and palette. Titles break ties between
# the broad categories used by the RSS pipeline.
TOPICS = (
    ("gaming", r"\b(?:gaming|gta|xbox|playstation|steam|nintendo|videogioc\w*|console)\b", "#251933", "#f6af66"),
    ("phone", r"\b(?:smartphone|xiaomi|iphone|pixel|galaxy|android|esim)\b", "#132e32", "#7ee4bf"),
    ("audio", r"\b(?:cuffie|auricolari|audio|headphones|earbuds|speaker)\b", "#352232", "#f8a8b6"),
    ("screen", r"\b(?:netflix|streaming|cinema|pattinson|james bond|007|tv|oled|film|serie tv)\b", "#351c25", "#ff9d85"),
    ("camera", r"\b(?:insta360|videocamer\w*|fotocamer\w*|gopro|obiettiv\w*)\b", "#1e2b39", "#f7d17f"),
    ("security", r"\b(?:sicurezza|phishing|privacy|malware|truff\w*|password|ransomware)\b", "#292544", "#d3a8ff"),
    ("home", r"\b(?:casa smart|domotica|aspirapolvere|roborock|dreame|narwal|termostat\w*)\b", "#293426", "#c7e895"),
    ("chip", r"\b(?:ai|intelligenza artificiale|chatgpt|gemini|copilot|claude|processore|gpu|hardware)\b", "#193044", "#8ee0f3"),
    ("document", r"\b(?:guide?|tutorial|come|confronti|confronto|offerte|prezzi)\b", "#343127", "#f4d48b"),
)


def draw_subject(pen, topic, bg, accent):
    """Draw the subject on a square canvas that can be rotated as a unit."""
    if topic == "gaming":
        pen.rounded_rectangle((30, 92, 410, 341), radius=95, fill=accent)
        pen.rounded_rectangle((164, 276, 277, 362), radius=34, fill=bg)
        pen.rounded_rectangle((80, 197, 193, 226), radius=9, fill=bg)
        pen.rounded_rectangle((122, 154, 151, 268), radius=9, fill=bg)
        for x, y in ((295, 169), (338, 210), (295, 253), (253, 210)):
            pen.ellipse((x - 16, y - 16, x + 16, y + 16), fill=bg)
    elif topic == "phone":
        pen.rounded_rectangle((121, 25, 319, 414), radius=28, fill=accent)
        pen.rounded_rectangle((132, 36, 308, 403), radius=22, fill=bg)
        pen.arc((90, 115, 404, 365), 45, 138, fill=accent, width=54)
        pen.rounded_rectangle((187, 52, 253, 66), radius=7, fill=accent)
        pen.rounded_rectangle((181, 377, 259, 384), radius=3, fill=accent)
    elif topic == "audio":
        pen.arc((66, 53, 374, 360), 180, 360, fill=accent, width=28)
        for x in (54, 295):
            pen.rounded_rectangle((x, 195, x + 91, 335), radius=36, fill=accent)
            pen.rounded_rectangle((x + 31, 216, x + 60, 314), radius=13, fill=bg)
    elif topic == "screen":
        pen.rounded_rectangle((20, 76, 420, 351), radius=25, outline=accent, width=14)
        pen.polygon(((177, 141), (177, 287), (294, 214)), fill=accent)
        pen.rounded_rectangle((137, 370, 303, 385), radius=8, fill=accent)
    elif topic == "camera":
        pen.rounded_rectangle((36, 105, 404, 349), radius=35, fill=accent)
        pen.rounded_rectangle((92, 76, 198, 120), radius=12, fill=accent)
        for radius, color in ((104, bg), (76, accent), (57, bg)):
            pen.ellipse((230 - radius, 227 - radius, 230 + radius, 227 + radius), fill=color)
        pen.ellipse((201, 185, 235, 218), fill=accent)
        pen.ellipse((340, 132, 368, 160), fill=bg)
    elif topic == "security":
        pen.polygon(((220, 37), (375, 93), (363, 256), (312, 335), (220, 405),
                     (128, 335), (77, 256), (65, 93)), fill=accent)
        pen.arc((172, 130, 268, 235), 180, 360, fill=bg, width=16)
        pen.rounded_rectangle((150, 185, 290, 289), radius=16, fill=bg)
        pen.ellipse((207, 215, 233, 241), fill=accent)
        pen.rectangle((216, 230, 224, 260), fill=accent)
    elif topic == "home":
        pen.line(((37, 205), (220, 57), (403, 205)), fill=accent, width=25, joint="curve")
        pen.rounded_rectangle((81, 195, 359, 390), radius=21, outline=accent, width=17)
        for y, radius in ((278, 90), (301, 63), (324, 35)):
            pen.arc((220 - radius, y - 35, 220 + radius, y + 35), 210, 330, fill=accent, width=13)
        pen.ellipse((210, 326, 230, 346), fill=accent)
    elif topic == "document":
        pen.rounded_rectangle((94, 44, 347, 395), radius=22, fill=accent)
        for y, length in ((127, 128), (181, 160), (235, 101), (289, 150)):
            pen.rounded_rectangle((139, y, 139 + length, y + 14), radius=7, fill=bg)
    else:
        for offset in (151, 197, 243, 289):
            pen.line((offset, 65, offset, 375), fill=accent, width=13)
            pen.line((65, offset, 375, offset), fill=accent, width=13)
        pen.rounded_rectangle((105, 105, 335, 335), radius=27, fill=accent)
        pen.rounded_rectangle((143, 143, 297, 297), radius=15, fill=bg)
        pen.polygon(((233, 162), (180, 225), (215, 225), (208, 280), (260, 210), (226, 210)), fill=accent)


def editorial_cover(title: str, category: str) -> bytes:
    """Illustrate an article locally, without relying on an image provider."""
    default = ("chip", "#273044", "#b3c8fc")
    match = None
    for value in (title, category):
        match = next(((topic, bg, accent) for topic, pattern, bg, accent in TOPICS
                      if re.search(pattern, value, re.IGNORECASE)), None)
        if match:
            break
    topic, bg, accent = match or default
    variation = hashlib.sha256(title.encode()).digest()[0]
    image = Image.new("RGB", COVER_SIZE, bg)
    pen = ImageDraw.Draw(image)
    for radius, color in ((255, "#ffffff"), (226, accent), (196, accent)):
        ring = Image.blend(Image.new("RGB", (1, 1), bg), Image.new("RGB", (1, 1), color), .18).getpixel((0, 0))
        pen.ellipse((887 - radius, 338 - radius, 887 + radius, 338 + radius), outline=ring, width=2)
    subject = Image.new("RGBA", (440, 440))
    draw_subject(ImageDraw.Draw(subject), topic, bg, accent)
    subject = subject.rotate(variation % 21 - 10, resample=Image.Resampling.BICUBIC)
    image.paste(subject, (667, 118), subject)
    pen.rounded_rectangle((72, 148, 136, 156), radius=4, fill=accent)
    pen.text((72, 183), (category or "AI Vision").upper()[:35], font=cover_font(23), fill=accent)

    for size in (54, 50, 46, 42):
        font = cover_font(size, bold=True)
        lines = [""]
        for word in title.split():
            candidate = " ".join(filter(None, (lines[-1], word)))
            if lines[-1] and pen.textlength(candidate, font=font) > 565:
                lines.append(word)
            else:
                lines[-1] = candidate
        if len(lines) <= 5:
            break
    if len(lines) > 5:
        lines = lines[:5]
        lines[-1] += "…"
    for index, line in enumerate(lines):
        if pen.textlength(line, font=font) > 565:
            line = line.removesuffix("…")
            while pen.textlength(line + "…", font=font) > 565:
                line = line[:-1]
            line += "…"
        pen.text((72, 234 + index * (size + 9)), line, font=font, fill="#fff8ee")
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def cover_font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default(size=size)


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
