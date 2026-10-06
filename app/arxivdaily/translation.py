"""Title/abstract translation using the shared LLM or official MT endpoints."""
from __future__ import annotations

import os
import time

import httpx

from .llm import _quiet_http_debug
from .models import Paper, ProcessingError, Translation


class TranslationClient:
    def __init__(self, config, analysis, client=None, *, sleep=time.sleep):
        self.settings = config["translation"]
        self.analysis = analysis
        self.client = client
        self.sleep = sleep

    def translate(self, paper: Paper, *, title_only=False) -> Translation:
        # Fixture runs must remain offline regardless of the selected backend.
        if self.settings["provider"] == "llm" or hasattr(self.analysis, "fixture"):
            return self.analysis.translate(paper, title_only=title_only)
        self.analysis._begin_stage("translation")
        _quiet_http_debug()
        cfg = self.settings
        texts = [paper.title] if title_only else [paper.title, paper.abstract]
        key = os.environ.get(cfg["api_key_env"], "")
        if cfg["provider"] == "deepl" and not key:
            raise ProcessingError("translation_key_missing")
        for attempt in range(cfg["attempts"]):
            self.analysis._guard()
            timeout = self.analysis._remaining_seconds(cfg["timeout"])
            if timeout <= 0.1:
                raise ProcessingError("translation_run_time_guard")
            try:
                client = self.client or self.analysis.client
                if cfg["provider"] == "deepl":
                    response = client.post(cfg["base_url"].rstrip("/") + "/v2/translate",
                                           json={"text": texts, "source_lang": "EN", "target_lang": "ZH"},
                                           headers={"Authorization": "DeepL-Auth-Key " + key}, timeout=timeout)
                    response.raise_for_status()
                    values = [item["text"] for item in response.json()["translations"]]
                else:
                    payload = {"q": texts, "source": "en", "target": "zh", "format": "text"}
                    if key:
                        payload["api_key"] = key
                    response = client.post(cfg["base_url"].rstrip("/") + "/translate", json=payload, timeout=timeout)
                    response.raise_for_status()
                    values = response.json()["translatedText"]
                if not isinstance(values, list) or len(values) != len(texts) or any(not isinstance(v, str) or not v.strip() for v in values):
                    raise ProcessingError("translation_response_invalid")
                return Translation(values[0], "" if title_only else values[1])
            except (httpx.HTTPError, ValueError, KeyError, TypeError, ProcessingError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                    raise ProcessingError("translation_http_nonretryable") from None
                if attempt == cfg["attempts"] - 1:
                    raise ProcessingError("translation_request_failed") from None
                delay = min(cfg["retry_delay_seconds"] * 2**attempt, 8)
                self.sleep(min(delay, self.analysis._remaining_seconds(delay)))
        raise ProcessingError("translation_request_failed")
