#!/usr/bin/env python3
"""Pubblica automaticamente su Instagram i nuovi articoli WordPress di AI Vision.

Usa Instagram API with Instagram Login e mantiene un registro persistente sul
ramo instagram-state per evitare doppioni. Al primo avvio registra gli articoli
gia esistenti senza pubblicarli.
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser

STATE_BRANCH = "instagram-state"
STATE_PATH = "data/instagram_state.json"
DEFAULT_API_VERSION = "v26.0"
USER_AGENT = "AI-Vision-Instagram/1.0"
CAPTION_LIMIT = 2200


class APIError(RuntimeError):
    def __init__(self, service, code, description="", subcode=None):
        self.code = code
        self.description = (description or "").strip()
        self.subcode = subcode
        detail = f" - {self.description}" if self.description else ""
        if subcode not in (None, ""):
            detail += f" (subcode {subcode})"
        super().__init__(f"{service}: errore HTTP/API {code}{detail}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request_json(url, service, method="GET", payload=None, bearer=None, github_token=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        headers["Accept"] = "application/vnd.github+json"

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=45) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        description = ""
        api_code = exc.code
        subcode = None
        try:
            error_data = json.loads(exc.read().decode("utf-8", errors="replace"))
            error = error_data.get("error") if isinstance(error_data, dict) else None
            if isinstance(error, dict):
                description = str(error.get("message") or "")
                api_code = error.get("code", exc.code)
                subcode = error.get("error_subcode")
            elif isinstance(error_data, dict):
                description = str(
                    error_data.get("message") or error_data.get("error_description") or ""
                )
        except Exception:
            pass
        raise APIError(service, api_code, description, subcode) from None
    except Exception:
        raise RuntimeError(f"{service}: risposta non disponibile o non valida") from None


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in ("p", "br", "div", "li"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ("p", "div", "li"):
            self.parts.append(" ")

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def plain(value):
    parser = TextParser()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", html.unescape("".join(parser.parts))).strip()


def shorten(text, limit):
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def caption(post):
    title = shorten(plain(post.get("title", {}).get("rendered", "")), 300)
    excerpt = shorten(plain(post.get("excerpt", {}).get("rendered", "")), 650)
    blocks = [title]
    if excerpt:
        blocks.append(excerpt)
    blocks.append("🔗 Articolo completo su AI Vision — link in bio")
    blocks.append("#AIVision #Tecnologia #IntelligenzaArtificiale #TechNews")
    return shorten("\n\n".join(blocks), CAPTION_LIMIT)


def featured_image(post):
    media = post.get("_embedded", {}).get("wp:featuredmedia", [])
    if not media or not isinstance(media[0], dict):
        return ""
    item = media[0]
    source = str(item.get("source_url") or "").strip()
    if source.startswith("https://"):
        return source
    sizes = item.get("media_details", {}).get("sizes", {})
    if isinstance(sizes, dict):
        for name in ("large", "medium_large", "medium", "thumbnail"):
            candidate = sizes.get(name)
            if isinstance(candidate, dict):
                url = str(candidate.get("source_url") or "").strip()
                if url.startswith("https://"):
                    return url
    return ""


def public_ready(post, base):
    url = urllib.parse.urlsplit(post.get("link", ""))
    expected = urllib.parse.urlsplit(base)
    if post.get("status") != "publish" or url.scheme != "https" or url.netloc != expected.netloc:
        return False
    try:
        req = urllib.request.Request(post["link"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200 or urllib.parse.urlsplit(response.url).netloc != expected.netloc:
                return False
            page = response.read(3_000_000).decode("utf-8", errors="replace")
        title = plain(post.get("title", {}).get("rendered", ""))
        return title.casefold() in plain(page).casefold()
    except Exception:
        return False


class State:
    def __init__(self, repository, token):
        self.root = f"https://api.github.com/repos/{repository}"
        self.token = token
        self.sha = None

    def api(self, path, method="GET", payload=None):
        return request_json(
            self.root + path,
            "GitHub",
            method,
            payload,
            github_token=self.token,
        )

    def load(self):
        try:
            self.api(f"/git/ref/heads/{STATE_BRANCH}")
        except APIError as exc:
            if exc.code != 404:
                raise
            repo = self.api("")
            default = urllib.parse.quote(repo["default_branch"], safe="")
            ref = self.api(f"/git/ref/heads/{default}")
            self.api(
                "/git/refs",
                "POST",
                {"ref": f"refs/heads/{STATE_BRANCH}", "sha": ref["object"]["sha"]},
            )

        try:
            result = self.api(f"/contents/{STATE_PATH}?ref={STATE_BRANCH}")
        except APIError as exc:
            if exc.code == 404:
                return None
            raise

        self.sha = result["sha"]
        data = json.loads(base64.b64decode(result["content"]))
        if data.get("version") != 1 or not isinstance(data.get("posts"), dict):
            raise RuntimeError("Registro Instagram non valido: pubblicazione interrotta.")
        return data

    def save(self, data):
        payload = {
            "message": "Aggiorna registro Instagram [skip ci]",
            "branch": STATE_BRANCH,
            "content": base64.b64encode(
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("ascii"),
        }
        if self.sha:
            payload["sha"] = self.sha
        result = self.api(f"/contents/{STATE_PATH}", "PUT", payload)
        self.sha = result["content"]["sha"]


def wordpress_posts(base):
    result = []
    refresh = uuid.uuid4().hex
    for page in range(1, 101):
        query = urllib.parse.urlencode(
            {
                "status": "publish",
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "asc",
                "_embed": "wp:featuredmedia",
                "_aivision_refresh": refresh,
            }
        )
        try:
            batch = request_json(f"{base}/wp-json/wp/v2/posts?{query}", "WordPress")
        except APIError as exc:
            if exc.code == 400 and page > 1 and result:
                return result
            raise
        if not isinstance(batch, list):
            raise RuntimeError("Elenco WordPress non valido")
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise RuntimeError("Troppi articoli: ampliare la paginazione prima di pubblicare.")


class InstagramClient:
    def __init__(self, token, version):
        self.token = token
        self.version = version if version.startswith("v") else f"v{version}"
        self.root = f"https://graph.instagram.com/{self.version}"
        self.user_id = None
        self.username = None

    def api(self, path, method="GET", payload=None):
        return request_json(
            f"{self.root}/{path.lstrip('/')}",
            "Instagram",
            method,
            payload,
            bearer=self.token,
        )

    def resolve_account(self):
        try:
            profile = self.api("me?fields=user_id,username")
        except APIError:
            profile = self.api("me?fields=id,username")
        if not isinstance(profile, dict):
            raise RuntimeError("Profilo Instagram non valido")
        user_id = str(profile.get("user_id") or profile.get("id") or "").strip()
        username = str(profile.get("username") or "").strip()
        if not user_id:
            raise RuntimeError("Instagram non ha restituito l'ID dell'account professionale")
        self.user_id = user_id
        self.username = username
        return user_id, username

    def create_image_container(self, image_url, text):
        result = self.api(
            f"{self.user_id}/media",
            "POST",
            {"image_url": image_url, "caption": text},
        )
        container_id = str(result.get("id") if isinstance(result, dict) else "").strip()
        if not container_id:
            raise RuntimeError("Instagram non ha restituito l'ID del contenitore")
        return container_id

    def wait_container(self, container_id):
        for _ in range(20):
            result = self.api(f"{container_id}?fields=status_code")
            if not isinstance(result, dict):
                raise RuntimeError("Stato contenitore Instagram non valido")
            status = str(result.get("status_code") or "").upper()
            if status in {"FINISHED", "PUBLISHED"}:
                return
            if status in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Contenitore Instagram non pubblicabile: {status}")
            time.sleep(3)
        raise RuntimeError("Timeout durante la preparazione dell'immagine Instagram")

    def publish_container(self, container_id):
        result = self.api(
            f"{self.user_id}/media_publish",
            "POST",
            {"creation_id": container_id},
        )
        media_id = str(result.get("id") if isinstance(result, dict) else "").strip()
        if not media_id:
            raise RuntimeError("Instagram non ha restituito l'ID del post pubblicato")
        return media_id


def sync(store, published, base, instagram):
    user_id, username = instagram.resolve_account()
    label = f"@{username}" if username else user_id
    print(f"Instagram: account collegato {label}.")

    data = store.load()
    if data is None:
        data = {
            "version": 1,
            "site": base,
            "instagram_user_id": user_id,
            "instagram_username": username,
            "posts": {
                str(post["id"]): {"status": "baseline"}
                for post in published
                if post.get("status") == "publish"
            },
        }
        store.save(data)
        print(
            f"Inizializzazione OK: {len(data['posts'])} articoli esistenti esclusi. "
            "Nessun post Instagram pubblicato."
        )
        return

    if data.get("site") != base:
        raise RuntimeError("Sito diverso dal registro Instagram: verificare configurazione.")

    expected_username = os.environ.get("INSTAGRAM_EXPECTED_USERNAME", "").strip().lstrip("@")
    if expected_username and username.casefold() != expected_username.casefold():
        raise RuntimeError(
            f"Account Instagram inatteso: collegato @{username}, atteso @{expected_username}."
        )

    stored_username = str(data.get("instagram_username") or "").strip().lstrip("@")
    stored_user_id = str(data.get("instagram_user_id") or "").strip()

    if stored_username and username and stored_username.casefold() != username.casefold():
        raise RuntimeError("Account Instagram diverso dal registro: verificare il token configurato.")

    # Con Instagram Login l'ID restituito dal token può cambiare dopo una nuova
    # autorizzazione/token. Lo username è invece univoco e identifica l'account
    # che vogliamo pubblicare. Se lo username coincide, aggiorniamo l'ID salvato
    # invece di bloccare l'automazione con un falso positivo.
    if stored_user_id != user_id:
        if not username:
            raise RuntimeError("ID Instagram cambiato e username non disponibile: controllo interrotto.")
        print("AVVISO: ID Instagram aggiornato per lo stesso account; sincronizzo il registro.")
        data["instagram_user_id"] = user_id
        data["instagram_username"] = username
        store.save(data)
    elif not stored_username and username:
        data["instagram_username"] = username
        store.save(data)

    print(
        f"WordPress: {len(published)} articoli pubblicati. "
        f"Registro Instagram: {len(data['posts'])} articoli."
    )
    sent = 0
    for post in published:
        key = str(post["id"])
        record = data["posts"].get(key)
        if record:
            if record.get("status") == "pending":
                print(
                    f"::warning::Post {key}: pubblicazione incerta. "
                    "Non reinviato per evitare doppioni."
                )
            continue

        if not public_ready(post, base):
            print(f"Post {key}: pagina non ancora pronta, riprovo al prossimo controllo.")
            continue

        image_url = featured_image(post)
        if not image_url:
            print(
                f"::warning::Post {key}: immagine in evidenza pubblica non disponibile. "
                "Riprovo piu tardi."
            )
            continue

        data["posts"][key] = {
            "status": "pending",
            "at": datetime.now(timezone.utc).isoformat(),
            "image_url": image_url,
        }
        store.save(data)

        try:
            container_id = instagram.create_image_container(image_url, caption(post))
            data["posts"][key]["container_id"] = container_id
            store.save(data)
            instagram.wait_container(container_id)
            media_id = instagram.publish_container(container_id)
        except APIError:
            del data["posts"][key]
            store.save(data)
            raise
        except RuntimeError as exc:
            if data["posts"].get(key, {}).get("container_id"):
                data["posts"][key]["status"] = "pending"
                data["posts"][key]["error"] = str(exc)
                store.save(data)
            else:
                del data["posts"][key]
                store.save(data)
            raise

        data["posts"][key].update(
            {
                "status": "sent",
                "media_id": media_id,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        store.save(data)
        sent += 1
        print(f"OK: articolo {key} pubblicato su Instagram, media {media_id}.")

    print(f"Controllo Instagram completato. Nuovi post pubblicati: {sent}.")


def main():
    names = (
        "WP_BASE_URL",
        "GITHUB_REPOSITORY",
        "GITHUB_TOKEN",
        "INSTAGRAM_ACCESS_TOKEN",
    )
    env = {name: os.environ.get(name, "").strip() for name in names}
    if not all(env.values()):
        raise RuntimeError("Configurare tutti i secret e le variabili richiesti.")

    base = env["WP_BASE_URL"].rstrip("/")
    if urllib.parse.urlsplit(base).scheme != "https":
        raise RuntimeError("WP_BASE_URL deve usare HTTPS.")

    version = (
        os.environ.get("INSTAGRAM_API_VERSION", DEFAULT_API_VERSION).strip()
        or DEFAULT_API_VERSION
    )
    store = State(env["GITHUB_REPOSITORY"], env["GITHUB_TOKEN"])
    instagram = InstagramClient(env["INSTAGRAM_ACCESS_TOKEN"], version)
    sync(store, wordpress_posts(base), base, instagram)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        sys.exit(1)
