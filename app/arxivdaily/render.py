"""Render immutable public digests and size-bounded ServerChan messages."""
from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from .models import DigestItem


def _day(value: date | str) -> str:
    result = value.isoformat() if isinstance(value, date) else str(value)
    date.fromisoformat(result)
    return result


def _title(item: DigestItem) -> str:
    # A title is untrusted text; keep it on one Markdown line.
    return " ".join(item.paper.title.split()).replace("[", "\\[").replace("]", "\\]")


def _url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("archive URL must be a public HTTPS URL")
    return url


def _full(item: DigestItem) -> str:
    if item.tier != "full" or item.summary is None:
        raise ValueError("full digest item requires a validated summary")
    s = item.summary
    lines = [f"### {_title(item)}", item.paper.url, "", f"**背景：** {s.background}",
             f"**贡献：** {s.contribution}", f"**方法：** {s.method}",
             f"**实验：** {s.experiments}", f"**结论：** {s.conclusion}"]
    return "\n".join(lines)


def _light(item: DigestItem) -> str:
    if item.tier != "light":
        raise ValueError("light digest item expected")
    return f"- [{_title(item)}]({item.paper.url})"


def render_archive(date: date | str, items: list[DigestItem], notes=None) -> str:
    """Return the complete, public Markdown snapshot. Caller persists it immutably."""
    day = _day(date)
    full = [item for item in items if item.tier == "full" and not item.recovery_of]
    light = [item for item in items if item.tier == "light" and not item.recovery_of]
    recovery_full = [item for item in items if item.tier == "full" and item.recovery_of]
    recovery_light = [item for item in items if item.tier == "light" and item.recovery_of]
    if len(full) + len(light) + len(recovery_full) + len(recovery_light) != len(items):
        raise ValueError("unknown digest tier")
    parts = [f"# arXiv 每日简报 · {day}"]
    if full:
        parts.extend(["## 完整档", "\n\n".join(_full(item) for item in full)])
    if light:
        parts.extend(["## 轻量档", "\n".join(_light(item) for item in light)])
    if recovery_full:
        parts.extend(["## 补发完整档", "上一轮投递未确认，以下条目本次可能重复送达。",
                      "\n\n".join(_full(item) for item in recovery_full)])
    if recovery_light:
        parts.extend(["## 补发轻量档", "上一轮投递未确认，以下条目本次可能重复送达。",
                      "\n".join(_light(item) for item in recovery_light)])
    if notes:
        if isinstance(notes, str):
            notes = [notes]
        parts.extend(["## 运行备注", "\n".join(f"- {str(note)}" for note in notes)])
    return "\n\n".join(parts).rstrip() + "\n"


def server_title(date: date | str) -> str:
    return f"arXiv 每日简报 {_day(date)}"


def render_notification(
    date: date | str,
    items: list[DigestItem],
    archive_url: str,
    max_bytes: int = 30000,
) -> tuple[str, dict[str, str]]:
    """Fit one message without cutting a full paper's summary in half.

    The caller must have already published and verified ``archive_url``. The
    mapping records presentation only; it never changes the business tier.
    """
    day, archive_url = _day(date), _url(archive_url)
    if not 0 < max_bytes <= 32768:
        raise ValueError("message byte cap must be within ServerChan's 32 KiB limit")
    ids = [item.paper.base_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate base arXiv ID in digest")
    full = [item for item in items if item.tier == "full"]
    light = [item for item in items if item.tier == "light"]
    if len(full) + len(light) != len(items):
        raise ValueError("unknown digest tier")
    full_inline = set(item.paper.base_id for item in full)
    light_inline = set(item.paper.base_id for item in light)
    short_full_labels: set[str] = set()

    def compose() -> tuple[str, dict[str, str]]:
        modes: dict[str, str] = {}
        lines = [f"# arXiv 每日简报 · {day}"]
        if any(item.recovery_of for item in items):
            lines.append("**补发：上一轮投递未确认，本次可能重复。**")
        for heading, group in (("## 完整档", [i for i in full if not i.recovery_of]),
                               ("## 补发完整档", [i for i in full if i.recovery_of])):
            if group:
                lines.append(heading)
            for item in group:
                key = item.paper.base_id
                if key in full_inline:
                    lines.append(_full(item))
                    modes[key] = "rendered_inline_full"
                else:
                    label = f"arXiv {key}" if key in short_full_labels else _title(item)
                    lines.append(f"- [{label}]({item.paper.url})：完整总结见[公开存档]({archive_url})。")
                    modes[key] = "archive_link_only"
        for heading, group in (("## 轻量档", [i for i in light if not i.recovery_of]),
                               ("## 补发轻量档", [i for i in light if i.recovery_of])):
            if group:
                lines.append(heading)
            for item in group:
                key = item.paper.base_id
                if key in light_inline:
                    lines.append(_light(item))
                    modes[key] = "light_title_link"
                else:
                    modes[key] = "light_archive_only"
            omitted = sum(item.paper.base_id not in light_inline for item in group)
            if omitted:
                lines.append(f"另有 {omitted} 篇轻量档仅列于公开存档。")
        lines.append(f"[完整日报与长期存档]({archive_url})")
        return "\n\n".join(lines).rstrip() + "\n", modes

    body, modes = compose()
    while len(body.encode("utf-8")) > max_bytes and light_inline:
        light_inline.remove(next(item.paper.base_id for item in reversed(light) if item.paper.base_id in light_inline))
        body, modes = compose()
    while len(body.encode("utf-8")) > max_bytes and full_inline:
        full_inline.remove(next(item.paper.base_id for item in reversed(full) if item.paper.base_id in full_inline))
        body, modes = compose()
    while len(body.encode("utf-8")) > max_bytes and len(short_full_labels) < len(full):
        short_full_labels.add(next(item.paper.base_id for item in reversed(full) if item.paper.base_id not in short_full_labels))
        body, modes = compose()
    if len(body.encode("utf-8")) > max_bytes:
        raise ValueError("message metadata alone exceeds byte cap")
    return body, modes
