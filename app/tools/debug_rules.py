"""Notebook helpers: category metadata cache and repeatable local rule experiments.

No pipeline, state store, model client, translation or delivery is imported.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import csv
from datetime import date, datetime, time, timedelta, timezone
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from arxivdaily.collection import Collector
from arxivdaily.models import Paper, fingerprint, iso, normalize_id, parse_time
from arxivdaily.rules import _contains, _normal, match_rules


def date_window(days: int = 14, end_date: str | date | None = None, *, timezone_name="Asia/Shanghai", now: datetime | None = None) -> dict:
    """Previous complete local calendar days, converted to the collector's UTC window."""
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("days must be an integer from 1 to 365")
    zone = ZoneInfo(timezone_name)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must have a timezone")
    last = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    last = last or current.astimezone(zone).date() - timedelta(days=1)
    first = last - timedelta(days=days - 1)
    start = datetime.combine(first, time.min, zone)
    end = datetime.combine(last + timedelta(days=1), time.min, zone) - timedelta(microseconds=1)
    return {"start": iso(start), "end": iso(end), "manual": True,
            "local_start_date": first.isoformat(), "local_end_date": last.isoformat(),
            "timezone": timezone_name}


def metadata_snapshot(config: dict, window: dict, *, max_papers: int = 10000, client=None) -> dict:
    """Fetch all category metadata before keywords, with an explicit debug-only cap."""
    if type(max_papers) is not int or not 1 <= max_papers <= 10000:
        raise ValueError("max_papers must be an integer from 1 to 10000")
    scan_config = deepcopy(config)
    scan_config["collection"]["max_candidates"] = max_papers
    result = Collector(scan_config, client=client).collect(window, apply_rules=False)
    return {"schema_version": 1, "fetched_at": iso(datetime.now(timezone.utc)),
            "window": window, "categories": sorted(set(config["rules"]["categories"])),
            "max_papers": max_papers, "complete": result.complete,
            "errors": result.errors, "shards": result.shards,
            "papers": [paper.to_dict() for paper in result.papers]}


def load_or_fetch(config: dict, window: dict, cache_dir: str | Path, *, refresh=False, max_papers=10000, client=None) -> tuple[dict, Path, bool]:
    """Changing keywords reuses raw metadata; dates/categories/cap select a new cache."""
    categories = sorted(set(config["rules"]["categories"]))
    key = fingerprint({"schema": 1, "window": window, "categories": categories, "max_papers": max_papers})[:24]
    path = Path(cache_dir) / (key + ".json")
    reused = path.is_file() and not refresh
    if reused:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot.get("schema_version") != 1 or snapshot.get("window") != window or snapshot.get("categories") != categories or snapshot.get("max_papers") != max_papers:
            raise ValueError("metadata cache does not match this experiment; fetch with refresh=True")
        return snapshot, path, True
    snapshot = metadata_snapshot(config, window, max_papers=max_papers, client=client)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".atomic.json")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return snapshot, path, False


def check_coverage(snapshot: dict, config: dict, window: dict | None = None) -> None:
    cached = set(snapshot["categories"])
    wanted = set(config["rules"]["categories"])
    if cached and (not wanted or not wanted.issubset(cached)):
        raise ValueError("分类范围扩大了：请重跑抓取单元，不能只用旧缓存推断新增分类的结果。")
    if window is not None and (snapshot["window"]["start"], snapshot["window"]["end"]) != (window["start"], window["end"]):
        raise ValueError("日期范围改变了：请重跑抓取单元。")


def explain_paper(paper: Paper, config: dict) -> dict:
    """Expose the actual matching phrases and gates, using the production matcher."""
    rules = config["rules"]
    categories = set(rules["categories"])
    text = _normal(paper.abstract)
    if rules["title_enabled"]:
        text += " " + _normal(paper.title)
    return {"category_pass": not categories or bool(categories.intersection(paper.categories)),
            "excluded_by": [phrase for phrase in rules["exclude"] if _contains(text, phrase)],
            "matched_groups": {group: [phrase for phrase in phrases if _contains(text, phrase)] for group, phrases in rules["groups"].items() if any(_contains(text, phrase) for phrase in phrases)},
            "routes": match_rules(paper, config)}


def screen_snapshot(snapshot: dict, config: dict, *, window: dict | None = None) -> list[dict]:
    check_coverage(snapshot, config, window)
    zone = ZoneInfo(snapshot["window"].get("timezone", "Asia/Shanghai"))
    matches = []
    for data in snapshot["papers"]:
        paper = Paper.from_dict(data)
        explanation = explain_paper(paper, config)
        if not explanation["routes"]:
            continue
        matches.append({"base_id": paper.base_id, "version_id": paper.version_id,
                        "title": paper.title, "link": paper.url,
                        "published": paper.published,
                        "published_local": parse_time(paper.published).astimezone(zone).strftime("%Y-%m-%d %H:%M"),
                        "categories": paper.categories, "routes": explanation["routes"],
                        "matched_groups": explanation["matched_groups"], "abstract": paper.abstract})
    return sorted(matches, key=lambda row: (row["published"], row["base_id"]), reverse=True)


def route_counts(matches: list[dict]) -> dict:
    return dict(Counter(route for row in matches for route in row["routes"]).most_common())


def compare_matches(before: list[dict], after: list[dict]) -> dict:
    old = {row["base_id"]: row for row in before}
    new = {row["base_id"]: row for row in after}
    return {"added": [new[key] for key in sorted(new.keys() - old.keys())],
            "removed": [old[key] for key in sorted(old.keys() - new.keys())],
            "changed_routes": [new[key] for key in sorted(old.keys() & new.keys()) if set(old[key]["routes"]) != set(new[key]["routes"])]}


def inspect_paper(snapshot: dict, config: dict, identifier: str) -> dict:
    check_coverage(snapshot, config)
    base, _ = normalize_id(identifier)
    for data in snapshot["papers"]:
        paper = Paper.from_dict(data)
        if paper.base_id == base:
            return {"paper": paper.to_dict(), **explain_paper(paper, config)}
    raise ValueError("这篇论文不在当前元数据缓存中；请先检查分类/日期范围或重新抓取。")


def table_html(matches: list[dict], limit: int = 100) -> str:
    columns = [("published_local", "首次提交时间"), ("title", "标题"),
               ("categories", "分类"), ("routes", "命中路线")]
    parts = [f"<p>显示前 {min(limit, len(matches))} / {len(matches)} 篇；完整结果保存在 matches。</p>",
             '<table style="border-collapse:collapse"><thead><tr>']
    parts.extend(f"<th style='padding:8px;text-align:left'>{label}</th>" for _, label in columns)
    parts.append("</tr></thead><tbody>")
    for row in matches[:limit]:
        parts.append("<tr>")
        for key, _ in columns:
            value = ", ".join(row[key]) if isinstance(row[key], list) else str(row[key])
            cell = escape(value)
            if key == "title":
                cell = f'<a href="{escape(row["link"], quote=True)}" target="_blank">{cell}</a>'
            parts.append(f"<td style='padding:8px;border-top:1px solid #ddd'>{cell}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def export_matches(matches: list[dict], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["base_id", "version_id", "published_local", "title", "link", "categories", "routes", "matched_groups", "abstract"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in matches:
            writer.writerow({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], (list, dict)) else row[key] for key in columns})
    return path
