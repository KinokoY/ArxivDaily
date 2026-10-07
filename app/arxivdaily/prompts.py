"""Load the six user-editable task prompts once, before any provider call."""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from .models import fingerprint


TASKS = ("selection", "review", "summary", "section_notes", "translation", "title_translation")


def default_prompt_directory() -> Path:
    source = Path(__file__).resolve().parents[1] / "prompts"
    return source if source.is_dir() else Path(str(files("arxivdaily.prompt_files")))


def load_prompts(config: dict) -> dict[str, str]:
    directory = Path(config.get("prompts", {}).get("directory") or default_prompt_directory())
    result = {}
    for task in TASKS:
        path = directory / f"{task}.md"
        try:
            content = path.read_text(encoding="utf-8-sig").strip()
        except (OSError, UnicodeError):
            raise ValueError(f"cannot read task prompt: {task}.md") from None
        if not content:
            raise ValueError(f"task prompt must not be empty: {task}.md")
        result[task] = content
    return result


def prompt_fingerprint(prompts: dict[str, str], task: str) -> str:
    # Review and summary can depend on section evidence extraction.
    dependencies = ("selection", task, "section_notes") if task == "review" else (task, "section_notes") if task == "summary" else (task,)
    return fingerprint({name: prompts[name] for name in dependencies})
