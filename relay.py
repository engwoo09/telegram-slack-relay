#!/usr/bin/env python3
"""Relay new posts from public Telegram channels (t.me/s preview) to one Slack Incoming Webhook.

Logs only counts: in a public GitHub repo the Actions logs are world-readable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

PREVIEW_URL = "https://t.me/s/{channel}"
USER_AGENT = "Mozilla/5.0 (compatible; telegram-slack-relay/1.0)"
MAX_TEXT = 3000
MAX_BACKFILL_PAGES = 5
SLACK_INTERVAL_SEC = 1.1


@dataclass
class Post:
    channel: str
    post_id: int
    text: str
    has_media: bool
    datetime: str

    @property
    def url(self) -> str:
        return f"https://t.me/{self.channel}/{self.post_id}"


def normalize_channel(raw: str) -> str:
    name = raw.strip()
    name = re.sub(r"^(https?://)?(t\.me|telegram\.me)/(s/)?", "", name)
    name = name.lstrip("@").split("/")[0].split("?")[0]
    return name.lower()


def parse_channels(raw: str) -> list[str]:
    seen: list[str] = []
    for part in re.split(r"[,\s]+", raw or ""):
        name = normalize_channel(part)
        if name and name not in seen:
            seen.append(name)
    return seen


def slack_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(inner: str, mark: str) -> str:
    core = inner.strip()
    if not core:
        return inner
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()) :]
    return f"{lead}{mark}{core}{mark}{trail}"


def render_slack(node) -> str:
    if isinstance(node, NavigableString):
        return slack_escape(str(node))
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"
    if "emoji" in (node.get("class") or []):
        return slack_escape(node.get_text())
    inner = "".join(render_slack(child) for child in node.children)
    if node.name in ("b", "strong"):
        return wrap(inner, "*")
    if node.name in ("i", "em"):
        return wrap(inner, "_")
    if node.name in ("s", "del"):
        return wrap(inner, "~")
    if node.name == "code":
        return f"`{inner}`"
    if node.name == "pre":
        return f"```{inner}```"
    if node.name == "a":
        href = node.get("href", "")
        if href.startswith("http"):
            label = inner.strip()
            if not label or label == slack_escape(href):
                return f"<{href}>"
            return f"<{href}|{label}>"
    return inner


def fetch_page(session: requests.Session, channel: str, before: int | None = None) -> tuple[str, list[Post]]:
    params = {"before": before} if before else None
    url = PREVIEW_URL.format(channel=channel)
    try:
        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        time.sleep(3)
        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.select_one(".tgme_channel_info_header_title")
    title = title_el.get_text(strip=True) if title_el else channel

    posts: list[Post] = []
    for msg in soup.select("div.tgme_widget_message[data-post]"):
        data_post = msg.get("data-post", "")
        post_channel, _, raw_id = data_post.rpartition("/")
        if not raw_id.isdigit() or post_channel.lower() != channel:
            continue
        text_el = msg.select_one(".tgme_widget_message_text")
        text = render_slack(text_el).strip() if text_el else ""
        has_media = bool(
            msg.select_one(
                ".tgme_widget_message_photo_wrap, .tgme_widget_message_video_player, "
                ".tgme_widget_message_document, .tgme_widget_message_voice, "
                ".tgme_widget_message_roundvideo, .tgme_widget_message_sticker, "
                ".tgme_widget_message_poll, .media_supported_cont"
            )
        )
        time_el = msg.select_one(".tgme_widget_message_date time[datetime]")
        posts.append(
            Post(
                channel=post_channel,
                post_id=int(raw_id),
                text=text,
                has_media=has_media,
                datetime=time_el["datetime"] if time_el else "",
            )
        )
    if not posts and not soup.select_one(".tgme_channel_info"):
        raise RuntimeError("preview page unavailable")
    posts.sort(key=lambda p: p.post_id)
    return title, posts


def fetch_new_posts(session: requests.Session, channel: str, last_id: int) -> tuple[str, list[Post]]:
    """Return posts with id > last_id, following ?before= pages if the gap is wider than one page."""
    title, page = fetch_page(session, channel)
    collected = {p.post_id: p for p in page if p.post_id > last_id}
    for _ in range(MAX_BACKFILL_PAGES):
        if not page or page[0].post_id <= last_id + 1:
            break
        page = fetch_page(session, channel, before=page[0].post_id)[1]
        collected.update({p.post_id: p for p in page if p.post_id > last_id})
    return title, [collected[k] for k in sorted(collected)]


def format_message(title: str, post: Post) -> str:
    body = post.text
    if len(body) > MAX_TEXT:
        body = body[:MAX_TEXT].rstrip() + "…"
    if not body:
        body = "_(미디어)_" if post.has_media else "_(본문 없음)_"
    elif post.has_media:
        body += "\n_(미디어 포함)_"
    return f"*[{slack_escape(title)}]*\n{body}\n<{post.url}|원문 보기>"


def post_to_slack(session: requests.Session, webhook: str, text: str) -> None:
    payload = {"text": text, "unfurl_links": False, "unfurl_media": False}
    for attempt in range(3):
        resp = session.post(webhook, json=payload, timeout=20)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", "5")))
            continue
        if resp.status_code >= 500 and attempt < 2:
            time.sleep(3)
            continue
        if resp.status_code != 200:
            code = re.sub(r"[^a-z_]", "", resp.text.strip().lower())[:40]
            raise RuntimeError(f"slack webhook HTTP {resp.status_code} {code}")
        return
    raise RuntimeError("slack webhook rate-limited")


def load_state(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return {str(k): int(v) for k, v in data.items() if str(v).isdigit()}


def save_state(path: Path, state: dict[str, int]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channels", help="쉼표로 구분한 채널 목록 (기본: 환경변수 TG_CHANNELS)")
    parser.add_argument("--state", default="state.json", help="상태 파일 경로 (기본: state.json)")
    parser.add_argument("--dry-run", action="store_true", help="슬랙 전송·상태 저장 없이 보낼 내용을 출력")
    parser.add_argument("--show", type=int, default=3, help="dry-run에서 상태 없는 채널의 최근 글 미리보기 개수")
    parser.add_argument("--rewind", type=int, default=0, help="시험용: 기록된 채널의 마지막 글 번호를 N만큼 되돌려 다시 전송")
    args = parser.parse_args()

    if args.dry_run and os.environ.get("GITHUB_ACTIONS") == "true":
        print("dry-run은 공개 로그에 본문이 남으므로 GitHub Actions에서 실행하지 않습니다.", file=sys.stderr)
        return 2

    channels = parse_channels(args.channels or os.environ.get("TG_CHANNELS", ""))
    if not channels:
        print("채널 목록이 비어 있습니다 (TG_CHANNELS 또는 --channels).", file=sys.stderr)
        return 2

    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not args.dry_run and not webhook:
        print("SLACK_WEBHOOK_URL이 없습니다.", file=sys.stderr)
        return 2

    state_path = Path(args.state)
    state = load_state(state_path)
    if args.rewind > 0:
        state = {k: max(v - args.rewind, 0) for k, v in state.items()}
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    initialized = sent = fetch_failed = send_failed = 0
    for channel in channels:
        last_id = state.get(channel)
        try:
            if last_id is None:
                title, posts = fetch_page(session, channel)
                if posts:
                    state[channel] = posts[-1].post_id
                    initialized += 1
                if args.dry_run:
                    for post in posts[-args.show:]:
                        print(f"--- [미리보기] {post.datetime}\n{format_message(title, post)}\n")
                continue
            title, posts = fetch_new_posts(session, channel, last_id)
        except Exception:
            fetch_failed += 1
            continue

        for post in posts:
            message = format_message(title, post)
            if args.dry_run:
                print(f"--- [전송 예정] {post.datetime}\n{message}\n")
                continue
            try:
                post_to_slack(session, webhook, message)
            except Exception as error:
                send_failed += 1
                # requests exceptions can embed the webhook URL; only our own RuntimeError text is safe to log.
                detail = f": {error}" if isinstance(error, RuntimeError) else ""
                print(f"전송 실패: {type(error).__name__}{detail}")
                break
            state[channel] = post.post_id
            sent += 1
            time.sleep(SLACK_INTERVAL_SEC)

    if not args.dry_run:
        state = {k: v for k, v in state.items() if k in channels}
        save_state(state_path, state)

    print(
        f"채널 {len(channels)}개 · 초기화 {initialized} · 전송 {sent} · "
        f"읽기 실패 {fetch_failed} · 전송 실패 {send_failed}"
    )
    return 1 if (send_failed or fetch_failed == len(channels)) else 0


if __name__ == "__main__":
    sys.exit(main())
