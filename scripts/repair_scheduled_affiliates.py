"""Backfill supported Amazon links on scheduled WordPress articles."""
from __future__ import annotations

import argparse
import os

from bs4 import BeautifulSoup

from amazon_affiliate import MARKER, affiliate_section, configured_tag, has_affiliate_link, tracking_tag
from wp_publisher import REQUEST_TIMEOUT, WordPressClient


def plan_link(post: dict, tag: str) -> tuple[str, str, list[dict]]:
    body = post["content"]["raw"]
    if has_affiliate_link(body):
        return "", "already_present", []
    title = BeautifulSoup(post["title"]["raw"], "html.parser").get_text(" ", strip=True)
    text = BeautifulSoup(body, "html.parser").get_text("\n", strip=True)
    excerpt = BeautifulSoup(post.get("excerpt", {}).get("raw", ""), "html.parser").get_text(" ", strip=True)
    return affiliate_section({"title": title, "body_markdown": text, "excerpt": excerpt}, body, tag)


def scheduled_posts(client: WordPressClient) -> list[dict]:
    posts = []
    page = 1
    while True:
        response = client.session.get(client._url("posts"), timeout=REQUEST_TIMEOUT,
                                      params={"context": "edit", "status": "future", "page": page,
                                              "per_page": 50, "_fields": "id,title,status,slug,date_gmt,content,excerpt"})
        response.raise_for_status()
        posts.extend(response.json())
        if page >= int(response.headers.get("X-WP-TotalPages", "1")):
            return posts
        page += 1


def repair(client: WordPressClient, tag: str, apply: bool) -> list[dict]:
    report = []
    for post in scheduled_posts(client):
        block, status, links = plan_link(post, tag)
        entry = {"id": post["id"], "title": post["title"]["raw"], "status": status, "links": links}
        report.append(entry)
        if not block or not apply:
            continue
        endpoint = client._url(f"posts/{post['id']}")
        response = client.session.get(endpoint, params={"context": "edit"}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        current = response.json()
        if (current["status"] != "future" or current["date_gmt"] != post["date_gmt"]
                or current["slug"] != post["slug"] or current["content"]["raw"] != post["content"]["raw"]
                or current["title"]["raw"] != post["title"]["raw"]
                or current["excerpt"]["raw"] != post["excerpt"]["raw"]):
            entry["status"] = "changed_since_scan"
            continue
        content = current["content"]["raw"] + "\n" + block
        response = client.session.post(endpoint, json={"content": content}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response = client.session.get(endpoint, params={"context": "edit"}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        saved = response.json()
        rendered = BeautifulSoup(saved["content"]["rendered"], "html.parser")
        tags = [tracking_tag(a["href"]) for a in rendered.select(f".{MARKER} a[href]")]
        if saved["date_gmt"] != post["date_gmt"] or saved["slug"] != post["slug"] or tags != [tag] * len(links):
            raise RuntimeError(f"Verifica affiliazione WordPress fallita per il post {post['id']}")
        entry["status"] = "updated"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    credentials = [os.environ.get(key, "") for key in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD")]
    tag = configured_tag()
    if not all(credentials) or not tag:
        raise RuntimeError("Credenziali WordPress o Tracking ID Amazon Italia mancanti")
    client = WordPressClient(*credentials, dry_run=not args.apply)
    with client.session:
        for item in repair(client, tag, args.apply):
            print(f"{item['id']}: {item['status']} ({len(item['links'])} link) · {item['title']}")


if __name__ == "__main__":
    main()
