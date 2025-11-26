#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

API_URL = "https://api.github.com/graphql"
MAX_PINNED = 6


def _load_config(path: Path) -> Tuple[str, List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    user: str | None = None
    entries: List[str] = []
    in_list = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("user:"):
            user = line.split(":", 1)[1].strip().strip('"').strip("'")
            continue

        if line.lower().startswith("pinned:"):
            in_list = True
            continue

        if in_list and line.startswith("-"):
            value = line[1:].strip().strip('"').strip("'")
            if value:
                entries.append(value)

    if not user:
        raise ValueError("`user` entry missing from pinned.yml")

    if not entries:
        raise ValueError("No repositories listed under `pinned` in pinned.yml")

    return user, entries[:MAX_PINNED]


def _graphql(token: str, query: str, variables: Dict) -> Dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "svg153-pin-sync-action",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:  # pragma: no cover - network error surface
        raise RuntimeError(f"GitHub API error: {err.read().decode('utf-8')}") from err

    if "errors" in body:
        raise RuntimeError(body["errors"])

    return body["data"]


def _clear_pins(token: str, user: str) -> None:
    query = """
    query($login: String!) {
      user(login: $login) {
        pinnedItems(first: 6, types: [REPOSITORY]) {
          nodes {
            ... on Repository {
              id
              name
              owner { login }
            }
          }
        }
      }
    }
    """
    data = _graphql(token, query, {"login": user})
    nodes = data["user"]["pinnedItems"]["nodes"]

    mutation = """
    mutation($repoId: ID!) {
      unpinRepository(input: {repositoryId: $repoId}) {
        clientMutationId
      }
    }
    """
    for node in nodes:
        _graphql(token, mutation, {"repoId": node["id"]})
        print(f"Unpinned {node['owner']['login']}/{node['name']}")


def _repo_id(token: str, slug: str) -> str:
    try:
        owner, name = slug.split("/", 1)
    except ValueError as exc:
        raise ValueError(f"Invalid repo slug '{slug}'. Use owner/name format.") from exc

    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
      }
    }
    """
    data = _graphql(token, query, {"owner": owner, "name": name})
    repo = data.get("repository")
    if not repo:
        raise ValueError(f"Repository not found: {slug}")
    return repo["id"]


def _pin(token: str, slug: str) -> None:
    repo_id = _repo_id(token, slug)
    mutation = """
    mutation($repoId: ID!) {
      pinRepository(input: {repositoryId: $repoId}) {
        clientMutationId
      }
    }
    """
    _graphql(token, mutation, {"repoId": repo_id})
    print(f"Pinned {slug}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronize the pinned repositories defined in pinned.yml")
    parser.add_argument(
        "--config",
        "-c",
        default="pinned.yml",
        help="Path to pinned.yml (defaults to ./pinned.yml)",
    )
    parser.add_argument(
        "--token",
        "-t",
        help="GitHub token with public_repo/read:user (falls back to PIN_REPO_TOKEN env)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    token = args.token or os.environ.get("PIN_REPO_TOKEN")
    if not token:
        raise ValueError("GitHub token missing. Provide --token or set PIN_REPO_TOKEN env variable.")

    config_path = Path(args.config).resolve()
    user, desired = _load_config(config_path)
    print(f"Syncing pinned repositories for {user} from {config_path} ...")

    _clear_pins(token, user)

    for slug in reversed(desired):
        _pin(token, slug)

    print("Pinned repositories updated successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
