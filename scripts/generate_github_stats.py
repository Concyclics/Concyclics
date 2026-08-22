#!/usr/bin/env python3
"""Generate self-hosted GitHub profile cards using only Python's stdlib."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

API = "https://api.github.com"
GRAPHQL = f"{API}/graphql"
USER_AGENT = "Concyclics-profile-stats/1.0"
COLORS = {
    "C": "#555555", "C#": "#178600", "C++": "#f34b7d", "CMake": "#DA3434",
    "CSS": "#663399", "CUDA": "#3A4E3A", "Go": "#00ADD8", "HTML": "#e34c26",
    "Java": "#b07219", "JavaScript": "#f1e05a", "Jupyter Notebook": "#DA5B0B",
    "Lua": "#000080", "MATLAB": "#e16737", "Python": "#3572A5", "R": "#198CE7",
    "Rust": "#dea584", "Shell": "#89e051", "Swift": "#F05138", "Tcl": "#e4cc98",
    "TeX": "#3D6117", "Terra": "#00004c", "TypeScript": "#3178c6",
}


class APIError(RuntimeError):
    pass


class Client:
    def __init__(self, token: str | None, timeout: float = 20.0) -> None:
        self.token = token.strip() if token else None
        self.timeout = timeout

    def request(self, url: str, *, payload: dict[str, Any] | None = None) -> Any:
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body:
            headers["Content-Type"] = "application/json"

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode(errors="replace")
                try:
                    message = json.loads(raw).get("message", raw)
                except json.JSONDecodeError:
                    message = raw
                error = APIError(f"GitHub API {exc.code}: {message} ({url})")
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise error from exc
                last_error = error
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
        raise APIError(f"GitHub API request failed after retries: {last_error}")

    def get(self, path: str, **params: Any) -> Any:
        url = f"{API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        return self.request(url)

    def pages(self, path: str, **params: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for page in range(1, 101):
            batch = self.get(path, **params, per_page=100, page=page)
            if not isinstance(batch, list):
                raise APIError(f"Expected list from {path}")
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise APIError(f"Pagination limit reached for {path}")

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        result = self.request(GRAPHQL, payload={"query": query, "variables": variables})
        if result.get("errors"):
            messages = "; ".join(str(e.get("message", e)) for e in result["errors"])
            raise APIError(f"GraphQL: {messages}")
        return result["data"]


def search_count(client: Client, query: str, endpoint: str = "/search/issues") -> int:
    return int(client.get(endpoint, q=query, per_page=1).get("total_count", 0))


def rest_contributions(client: Client, username: str) -> dict[str, Any]:
    commits = search_count(client, f"author:{username}", "/search/commits")
    prs = search_count(client, f"author:{username} type:pr")
    issues = search_count(client, f"author:{username} type:issue")
    return {
        "commits": commits, "pull_requests": prs, "issues": issues,
        "code_reviews": 0, "contributions": commits + prs + issues,
        "restricted_contributions": 0, "source": "rest-search",
    }


def graphql_contributions(client: Client, username: str, created_at: str) -> dict[str, Any] | None:
    if not client.token:
        return None
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions totalIssueContributions
          totalPullRequestContributions totalPullRequestReviewContributions
          restrictedContributionsCount contributionCalendar { totalContributions }
        }
      }
    }
    """
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        created = datetime(2008, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    total = {
        "commits": 0, "pull_requests": 0, "issues": 0, "code_reviews": 0,
        "contributions": 0, "restricted_contributions": 0,
        "source": "graphql-contributions",
    }
    try:
        for year in range(created.year, now.year + 1):
            start = max(created, datetime(year, 1, 1, tzinfo=timezone.utc))
            end = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
            if start >= end:
                continue
            data = client.graphql(query, {
                "login": username,
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": end.isoformat().replace("+00:00", "Z"),
            })
            collection = (data.get("user") or {}).get("contributionsCollection")
            if not collection:
                return None
            total["commits"] += int(collection.get("totalCommitContributions", 0))
            total["issues"] += int(collection.get("totalIssueContributions", 0))
            total["pull_requests"] += int(collection.get("totalPullRequestContributions", 0))
            total["code_reviews"] += int(collection.get("totalPullRequestReviewContributions", 0))
            total["contributions"] += int(collection.get("contributionCalendar", {}).get("totalContributions", 0))
            total["restricted_contributions"] += int(collection.get("restrictedContributionsCount", 0))
        return total
    except APIError as exc:
        # GITHUB_TOKEN is an installation token and may be blocked from user-level
        # GraphQL fields. This is an expected fallback, not a card-generation failure.
        print(f"GraphQL unavailable; falling back to public REST statistics: {exc}")
        return None


def collect_repos_and_languages(
    client: Client, username: str, excluded: set[str], notebook_weight: float
) -> tuple[list[dict[str, Any]], dict[str, float], list[str]]:
    # Always use the public endpoint, even with a PAT, to avoid leaking private repo
    # names or private language composition into the committed JSON/SVG files.
    repos = client.pages(f"/users/{urllib.parse.quote(username)}/repos", type="owner", sort="updated")
    repos = [r for r in repos if r.get("owner", {}).get("login", "").casefold() == username.casefold()]
    languages: dict[str, float] = defaultdict(float)
    language_repos: list[str] = []
    for repo in repos:
        name = str(repo.get("name", ""))
        if not name or name.casefold() in excluded or repo.get("fork") or repo.get("archived") or repo.get("disabled"):
            continue
        full_name = str(repo["full_name"])
        owner, repo_name = full_name.split("/", 1)
        data = client.get(f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo_name)}/languages")
        if not data:
            continue
        language_repos.append(full_name)
        for language, byte_count in data.items():
            weight = notebook_weight if language == "Jupyter Notebook" else 1.0
            languages[str(language)] += float(byte_count) * weight
    return repos, dict(languages), language_repos


def short_number(value: int) -> str:
    if value < 1_000:
        return str(value)
    if value < 1_000_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "m"


def stats_svg(username: str, stats: dict[str, Any]) -> str:
    metrics = [
        ("Total Stars", stats["total_stars"]), ("Commits", stats["commits"]),
        ("Pull Requests", stats["pull_requests"]), ("Issues", stats["issues"]),
        (("Code Reviews" if stats["code_reviews"] else "Total Forks"),
         (stats["code_reviews"] if stats["code_reviews"] else stats["total_forks"])),
        ("Repositories", stats["repositories"]),
    ]
    body = []
    for i, (label, value) in enumerate(metrics):
        x, y = 28 + (i % 2) * 225, 83 + (i // 2) * 38
        body.append(
            f'<text x="{x}" y="{y}" class="label">{escape(label)}</text>'
            f'<text x="{x + 185}" y="{y}" text-anchor="end" class="value">{short_number(int(value))}</text>'
        )
    source = "GitHub GraphQL + REST" if stats["source"] == "graphql-contributions" else "GitHub REST"
    return f'''<svg width="465" height="195" viewBox="0 0 465 195" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">{escape(username)}'s GitHub statistics</title>
  <desc id="desc">Self-generated GitHub profile statistics using {escape(source)}</desc>
  <style>
    .header {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #006AFF; }}
    .label {{ font: 600 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #417E87; }}
    .value {{ font: 700 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #417E87; }}
    .meta {{ font: 400 10px 'Segoe UI', Ubuntu, Sans-Serif; fill: #858585; }}
  </style>
  <rect x="0.5" y="0.5" width="464" height="194" rx="4.5" fill="#ffffff00" stroke="#e4e2e2"/>
  <text x="28" y="38" class="header">{escape(username)}'s GitHub Stats</text>
  {''.join(body)}
  <text x="437" y="179" text-anchor="end" class="meta">self-generated · {escape(source)}</text>
</svg>
'''


def languages_svg(language_bytes: dict[str, float], count: int) -> str:
    ranked = sorted(language_bytes.items(), key=lambda x: x[1], reverse=True)
    total = sum(v for _, v in ranked)
    if total <= 0:
        raise RuntimeError("GitHub returned no language data")
    shown = ranked[:count]
    shown_total = sum(v for _, v in shown)
    rects, labels, cursor = [], [], 25.0
    for i, (name, value) in enumerate(shown):
        width = 280.0 * value / shown_total
        if i == len(shown) - 1:
            width = 305.0 - cursor
        color = COLORS.get(name, "#8b949e")
        rects.append(f'<rect x="{cursor:.2f}" y="58" width="{width:.2f}" height="8" fill="{color}"/>')
        cursor += width
        col, row = (0 if i < 4 else 1), (i if i < 4 else i - 4)
        x, y = 25 + col * 155, 91 + row * 24
        text = f"{name} {value / total * 100:.1f}%"
        if len(text) > 24:
            text = text[:23] + "…"
        labels.append(
            f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{color}"/>'
            f'<text x="{x + 15}" y="{y}" class="lang">{escape(text)}</text>'
        )
    return f'''<svg width="330" height="195" viewBox="0 0 330 195" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Most Used Languages</title>
  <desc id="desc">Self-generated language statistics from public owned non-fork repositories</desc>
  <style>
    .header {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #006AFF; }}
    .lang {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #417E87; }}
  </style>
  <rect x="0.5" y="0.5" width="329" height="194" rx="4.5" fill="#ffffff00" stroke="#e4e2e2"/>
  <text x="25" y="36" class="header">Most Used Languages</text>
  <clipPath id="bar-clip"><rect x="25" y="58" width="280" height="8" rx="4"/></clipPath>
  <g clip-path="url(#bar-clip)">{''.join(rects)}</g>
  {''.join(labels)}
</svg>
'''


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def validate_svg(name: str, text: str) -> None:
    low = text.casefold()
    forbidden = ("something went wrong", "resource not accessible", "rate limit exceeded", "api error")
    if "<svg" not in low or "</svg>" not in low or any(x in low for x in forbidden):
        raise RuntimeError(f"Refusing to publish invalid {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=os.getenv("GITHUB_USER", "Concyclics"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--langs-count", type=int, default=8, choices=range(1, 9))
    parser.add_argument("--exclude-repo", action="append", default=[])
    parser.add_argument("--notebook-weight", type=float, default=1.0)
    args = parser.parse_args()
    if args.notebook_weight <= 0:
        raise SystemExit("--notebook-weight must be positive")

    client = Client(os.getenv("GH_STATS_TOKEN") or os.getenv("GITHUB_TOKEN"))
    username = args.username
    user = client.get(f"/users/{urllib.parse.quote(username)}")
    repos, language_bytes, language_repos = collect_repos_and_languages(
        client, username, {x.casefold() for x in args.exclude_repo}, args.notebook_weight
    )
    owned_nonfork = [r for r in repos if not r.get("fork")]
    contribution_stats = graphql_contributions(client, username, str(user.get("created_at", "")))
    if contribution_stats is None:
        contribution_stats = rest_contributions(client, username)

    stats: dict[str, Any] = {
        "schema_version": 1,
        "username": username,
        **contribution_stats,
        "total_stars": sum(int(r.get("stargazers_count", 0)) for r in owned_nonfork),
        "total_forks": sum(int(r.get("forks_count", 0)) for r in owned_nonfork),
        "repositories": len(owned_nonfork),
        "public_repositories": int(user.get("public_repos", 0)),
        "followers": int(user.get("followers", 0)),
        "languages": dict(sorted(language_bytes.items(), key=lambda x: x[1], reverse=True)),
        "language_repository_count": len(language_repos),
        "language_repositories": language_repos,
        "settings": {
            "langs_count": args.langs_count,
            "excluded_repositories": sorted(args.exclude_repo),
            "notebook_weight": args.notebook_weight,
        },
    }
    left, right = stats_svg(username, stats), languages_svg(language_bytes, args.langs_count)
    validate_svg("stats.svg", left)
    validate_svg("top-langs.svg", right)
    atomic_write(args.output_dir / "stats.svg", left)
    atomic_write(args.output_dir / "top-langs.svg", right)
    atomic_write(args.output_dir / "stats.json", json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(f"Generated {username}: {len(owned_nonfork)} repos, {stats['total_stars']} stars, {len(language_bytes)} languages ({stats['source']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
