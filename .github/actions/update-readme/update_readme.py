#!/usr/bin/env python3
"""Auto-update README sections with recent YouTube videos and repo activity."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - handled at runtime
    yaml = None



def _resolve_repo_root() -> Path:
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        return Path(workspace).resolve()

    current = Path(__file__).resolve()
    for ancestor in [current] + list(current.parents):
        if (ancestor / ".git").exists():
            return ancestor
    return current.parent


REPO_ROOT = _resolve_repo_root()
README_PATH = REPO_ROOT / "README.md"
CONFIG_PATH = REPO_ROOT / "auto_content.yml"
YOUTUBE_SECTION_START = "<!-- YOUTUBE_SECTION_START -->"
YOUTUBE_SECTION_END = "<!-- YOUTUBE_SECTION_END -->"
REPO_SECTION_START = "<!-- REPO_SECTION_START -->"
REPO_SECTION_END = "<!-- REPO_SECTION_END -->"
SPANISH_MONTHS = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
]


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    if yaml is None:
        raise RuntimeError(
            "PyYAML es necesario para leer auto_content.yml. Ejecuta `pip install pyyaml`."
        )

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("auto_content.yml debe contener un objeto YAML de nivel superior.")
    return data


def _http_get(url: str, headers: Dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as err:  # noqa: BLE001
        details = err.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP error {err.code} for {url}: {details}") from err


def _fetch_youtube_videos(channel_id: str, max_items: int) -> List[Dict[str, str]]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    data = _http_get(url, headers={"User-Agent": "svg153-readme-bot"})
    root = ET.fromstring(data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    videos: List[Dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", default="", namespaces=ns)
        link = entry.find("atom:link", ns)
        href = link.attrib.get("href", "") if link is not None else ""
        published = entry.findtext("atom:published", default="", namespaces=ns)
        videos.append({"title": title.strip(), "url": href.strip(), "published": published})
        if len(videos) >= max_items:
            break
    return videos


def _github_headers(token: str) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "svg153-readme-bot",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_repos(token: str, owner: str, sort: str) -> List[Dict]:
    url = f"https://api.github.com/users/{owner}/repos?per_page=100&type=owner&sort={sort}&direction=desc"
    payload = _http_get(url, headers=_github_headers(token))
    return json.loads(payload)


def _parse_date(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_date(value: str) -> str:
    date = _parse_date(value)
    month = SPANISH_MONTHS[date.month - 1]
    return f"{date.day:02d} {month} {date.year}"


def _sanitize_md(text: str | None) -> str:
    if not text:
        return "_Sin descripción_"
    return text.replace("|", "\\|")


def _build_channel_url(channel_id: str, label: str | None = None) -> str:
    label = (label or "").strip()
    if label.startswith("@"):
        return f"https://www.youtube.com/{label}"
    return f"https://www.youtube.com/channel/{channel_id}"


def _format_video_lines(videos: List[Dict[str, str]]) -> List[str]:
    if not videos:
        return ["_No se pudieron obtener videos._"]
    lines: List[str] = []
    for video in videos:
        title = video["title"] or "(Sin título)"
        url = video["url"] or "https://www.youtube.com"
        published = video["published"]
        date_txt = f" ({_format_date(published)})" if published else ""
        lines.append(f"- **[{title}]({url})**{date_txt}")
    return lines


def _build_youtube_md(sections: List[Dict[str, Any]]) -> str:
    if not sections:
        return "_No se pudieron obtener videos._"
    blocks: List[str] = []
    for idx, section in enumerate(sections):
        header = section.get("header", "").strip()
        if header:
            blocks.append(header)
        blocks.extend(_format_video_lines(section.get("videos", [])))
        if idx < len(sections) - 1:
            blocks.append("")
    return "\n".join(blocks).strip()


def _select_active_repos(repos: List[Dict], limit: int, days: int) -> List[Dict]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    filtered = [repo for repo in repos if _parse_date(repo["pushed_at"]) >= cutoff]
    if len(filtered) < limit:
        filtered = repos[:limit]
    return filtered[:limit]


def _build_repo_table(rows: List[Tuple[str, str, str]], header: Tuple[str, str, str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    if not rows:
        lines.append("| _Sin datos_ |  |  |")
        return "\n".join(lines)
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _build_repo_md(new_repos: List[Dict], active_repos: List[Dict]) -> str:
    new_rows = [
        (
            f"[{repo['name']}]({repo['html_url']})",
            _sanitize_md(repo.get("description")),
            _format_date(repo["created_at"]),
        )
        for repo in new_repos
    ]
    new_table = _build_repo_table(new_rows, ("Repositorio", "Descripción", "Creado"))

    active_rows = [
        (
            f"[{repo['name']}]({repo['html_url']})",
            _sanitize_md(repo.get("description")),
            _format_date(repo["pushed_at"]),
        )
        for repo in active_repos
    ]
    active_table = _build_repo_table(active_rows, ("Repositorio", "Descripción", "Última actividad"))

    return "\n".join([
        "**Repositorios nuevos**",
        "",
        new_table,
        "",
        "**Repositorios más activos**",
        "",
        active_table,
    ])


def _normalize_ignore_entries(raw: Any) -> Set[str]:
    if raw is None:
        return set()
    entries: List[str] = []
    if isinstance(raw, str):
        entries = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        for item in raw:
            if isinstance(item, str):
                entries.append(item.strip())
    return {entry.lower() for entry in entries if entry}


def _is_ignored(repo: Dict[str, Any], ignored: Set[str]) -> bool:
    if not ignored:
        return False
    name = str(repo.get("name") or "").lower()
    full_name = str(repo.get("full_name") or "").lower()
    owner = str(repo.get("owner", {}).get("login") or "").lower()
    candidates = [value for value in (name, full_name) if value]
    if owner and name:
        candidates.append(f"{owner}/{name}")
    return any(candidate in ignored for candidate in candidates)


def _resolve_channel_configs(cfg: Dict[str, Any], default_max: int) -> List[Dict[str, Any]]:
    configs: List[Dict[str, Any]] = []
    channels_cfg = cfg.get("channels")
    if isinstance(channels_cfg, list):
        for entry in channels_cfg:
            if not isinstance(entry, dict):
                continue
            channel_id = str(entry.get("id") or entry.get("channel_id") or "").strip()
            if not channel_id:
                continue
            label = str(entry.get("label") or entry.get("name") or channel_id).strip()
            url = str(entry.get("url") or "").strip()
            if not url:
                url = _build_channel_url(channel_id, label)
            max_items = _to_int(entry.get("max_items"), default_max)
            heading = str(entry.get("heading") or "").strip()
            if not heading:
                heading = f"### [{label}]({url})"
            configs.append({
                "id": channel_id,
                "label": label,
                "url": url,
                "heading": heading,
                "max_items": max_items,
            })
        if configs:
            return configs

    channel_id = str(cfg.get("channel_id") or "").strip()
    if not channel_id:
        return configs

    label = str(cfg.get("channel_label") or "@svg153").strip()
    url = str(cfg.get("channel_url") or "").strip()
    if not url:
        url = _build_channel_url(channel_id, label)
    heading = str(
        cfg.get("channel_heading")
        or f"### 👤 Canal principal: [{label}]({url})"
    ).strip()
    configs.append({
        "id": channel_id,
        "label": label,
        "url": url,
        "heading": heading,
        "max_items": default_max,
    })

    community_id = str(cfg.get("community_channel_id") or "").strip()
    if community_id:
        community_label = str(cfg.get("community_channel_label") or "@GitHubCommunitySpain").strip()
        community_url = str(cfg.get("community_channel_url") or "").strip()
        if not community_url:
            community_url = _build_channel_url(community_id, community_label)
        community_heading = str(
            cfg.get("community_heading")
            or f"### 🇪🇸 Comunidad GitHub Spain: [{community_label}]({community_url})"
        ).strip()
        community_max = _to_int(cfg.get("community_max_items"), default_max)
        configs.append({
            "id": community_id,
            "label": community_label,
            "url": community_url,
            "heading": community_heading,
            "max_items": community_max,
        })

    return configs


def _replace_section(content: str, start_marker: str, end_marker: str, body: str) -> str:
    if start_marker not in content or end_marker not in content:
        raise ValueError("Markers not found in README")
    start_idx = content.index(start_marker) + len(start_marker)
    end_idx = content.index(end_marker)
    updated = content[:start_idx].rstrip() + "\n\n" + body.strip() + "\n\n" + content[end_idx:]
    return updated


def main() -> None:
    config = _load_config(CONFIG_PATH)
    youtube_cfg = config.get("youtube", {})
    repos_cfg = config.get("repos", {})

    ignored_repos = _normalize_ignore_entries(repos_cfg.get("ignore"))

    default_channel_max = _to_int(youtube_cfg.get("max_items"), 3)
    channel_configs = _resolve_channel_configs(youtube_cfg, default_channel_max)
    if not channel_configs:
        raise ValueError("Define al menos un canal en la sección youtube de auto_content.yml")

    owner = repos_cfg.get("owner") or "svg153"
    top_new = int(repos_cfg.get("top_new", 5))
    top_active = int(repos_cfg.get("top_active", 5))
    active_days = int(repos_cfg.get("active_days", 30))

    github_token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("INPUT_TOKEN")
        or ""
    )
    if not github_token:
        print(
            "WARNING: GITHUB_TOKEN not set; proceeding unauthenticated (rate limits may apply).",
            file=sys.stderr,
        )

    sections: List[Dict[str, Any]] = []
    for channel in channel_configs:
        videos = _fetch_youtube_videos(channel["id"], channel["max_items"])
        sections.append({"header": channel["heading"], "videos": videos})

    repos_sorted_created = _fetch_repos(github_token, owner, sort="created")
    repos_sorted_pushed = _fetch_repos(github_token, owner, sort="pushed")

    if ignored_repos:
        repos_sorted_created = [repo for repo in repos_sorted_created if not _is_ignored(repo, ignored_repos)]
        repos_sorted_pushed = [repo for repo in repos_sorted_pushed if not _is_ignored(repo, ignored_repos)]

    readme = README_PATH.read_text(encoding="utf-8")

    youtube_md = _build_youtube_md(sections)
    repo_md = _build_repo_md(
        repos_sorted_created[:top_new],
        _select_active_repos(repos_sorted_pushed, top_active, active_days),
    )

    updated = _replace_section(readme, YOUTUBE_SECTION_START, YOUTUBE_SECTION_END, youtube_md)
    updated = _replace_section(updated, REPO_SECTION_START, REPO_SECTION_END, repo_md)

    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
        print("README updated.")
    else:
        print("README already up to date.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
