"""ServerChan Turbo transport. Quota reservation belongs to the persistent pipeline."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any

import httpx

from .models import DeliveryResult


class _TransportLogFilter(logging.Filter):
    """Scrub credential-bearing transport log records before any handler sees them."""

    def __init__(self):
        super().__init__()
        self._secrets: set[str] = set()
        self._lock = threading.Lock()

    def add_secret(self, value: str) -> None:
        if value:
            with self._lock:
                self._secrets.add(value)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = "transport_log_redacted"
        message = re.sub(r"(?i)https://sctapi\.ftqq\.com/[^\s/?]+\.send",
                         "https://sctapi.ftqq.com/[REDACTED].send", message)
        message = re.sub(r"(?i)([?&]readkey=)[^\s&#\"']+", r"\1[REDACTED]", message)
        with self._lock:
            for secret in self._secrets:
                message = message.replace(secret, "[REDACTED]")
        record.msg = message
        record.args = ()
        # Transport tracebacks may contain the original credential URL.
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


_TRANSPORT_FILTER = _TransportLogFilter()


def _protect_transport_logs() -> None:
    # HTTPX emits its HTTP Request INFO line on "httpx" in the locked version.
    # Logger filters are not inherited by children, so attach to existing
    # HTTPX children too. New httpcore children inherit CRITICAL.
    names = {"httpx", "httpx._client"}
    names.update(name for name in logging.Logger.manager.loggerDict if name.startswith("httpx."))
    for name in names:
        logger = logging.getLogger(name)
        if _TRANSPORT_FILTER not in logger.filters:
            logger.addFilter(_TRANSPORT_FILTER)
    logging.getLogger("httpcore").setLevel(logging.CRITICAL)
    for name in list(logging.Logger.manager.loggerDict):
        if name.startswith("httpcore."):
            logging.getLogger(name).setLevel(logging.CRITICAL)


def _wxstatus(value: Any) -> str:
    """Classify only unambiguous WeChat API results; unknown shapes stay unknown."""
    if value is None or value == "" or value == {}:
        return "queued"
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return "unknown"
    if not isinstance(value, dict):
        return "unknown"
    # WeChat's documented interface uses errcode=0 for success; it does not
    # prove the human received or read the notification.
    code = value.get("errcode")
    if type(code) is int:
        return "confirmed" if code == 0 else "failed"
    return "unknown"


def _payload(response: httpx.Response) -> dict | None:
    try:
        value = response.json()
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


class ServerChan:
    """One POST, then a finite number of in-memory status lookups.

    A POST timeout or ambiguous 5xx is never retried here. The caller has
    already saved attempt_started and reserved one of the shared daily sends.
    """

    def __init__(self, config: dict, client: httpx.Client | None = None, *, sleep=time.sleep):
        _protect_transport_logs()
        self.settings = config.get("delivery", config)
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)
        self.sleep = sleep

    def send(self, title: str, body: str) -> DeliveryResult:
        if not isinstance(title, str) or not title or "\n" in title or "\r" in title or len(title) > 32:
            raise ValueError("ServerChan title must be one line of at most 32 characters")
        cap = min(int(self.settings.get("body_bytes", 30000)), 32768)
        if len(body.encode("utf-8")) > cap:
            raise ValueError("ServerChan message exceeds configured UTF-8 byte cap")
        env_name = self.settings.get("sendkey_env", "SERVERCHAN_SENDKEY")
        sendkey = os.environ.get(env_name, "")
        if not sendkey:
            return DeliveryResult("failed", detail="sendkey_missing")
        if not sendkey.startswith("SCT") or not sendkey.isalnum():
            return DeliveryResult("failed", detail="invalid_turbo_sendkey")
        _TRANSPORT_FILTER.add_secret(sendkey)
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        try:
            # httpx has no retry transport by default. Never include response
            # or exception text in public state: URLs can contain the secret.
            response = self.client.post(url, data={"title": title, "desp": body})
        except httpx.RequestError:
            return DeliveryResult("unknown", detail="post_transport_uncertain")
        if response.status_code >= 500:
            return DeliveryResult("unknown", detail="post_server_uncertain")
        if response.status_code >= 400:
            return DeliveryResult("failed", detail="post_http_rejected")
        if not 200 <= response.status_code < 300:
            return DeliveryResult("unknown", detail="post_http_unrecognized")
        result = _payload(response)
        if result is None:
            return DeliveryResult("unknown", detail="post_response_invalid")
        if type(result.get("code")) is not int:
            return DeliveryResult("unknown", detail="post_business_code_missing")
        if result["code"] != 0:
            return DeliveryResult("failed", detail="post_business_rejected")
        data = result.get("data")
        if not isinstance(data, dict):
            return DeliveryResult("unknown", detail="post_receipt_missing")
        raw_pushid = data.get("pushid")
        if type(raw_pushid) not in {str,int}:
            return DeliveryResult("unknown",detail="post_pushid_invalid")
        pushid = str(raw_pushid)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}",pushid):
            return DeliveryResult("unknown",detail="post_pushid_invalid")
        raw_readkey = data.get("readkey")
        if raw_readkey is not None and not isinstance(raw_readkey,str):
            return DeliveryResult("unknown",pushid=pushid,detail="readkey_invalid")
        readkey = raw_readkey or ""
        if pushid == sendkey or (readkey and pushid == readkey):
            return DeliveryResult("unknown",detail="post_receipt_invalid")
        if not pushid:
            return DeliveryResult("unknown", detail="post_pushid_missing")
        # readkey is never assigned to a result or log. It lives only here.
        if not readkey:
            return DeliveryResult("unknown", pushid=pushid, detail="readkey_unavailable")
        _TRANSPORT_FILTER.add_secret(readkey)
        limit = max(0, min(int(self.settings.get("poll_limit", 3)), 3))
        for attempt in range(limit):
            if attempt:
                self.sleep(min(2 ** (attempt - 1), 8))
            try:
                status_response = self.client.get(
                    "https://sctapi.ftqq.com/push",
                    params={"id": pushid, "readkey": readkey},
                )
            except httpx.RequestError:
                return DeliveryResult("unknown", pushid=pushid, detail="poll_transport_uncertain", polls=attempt + 1)
            if status_response.status_code != 200:
                return DeliveryResult("unknown", pushid=pushid, detail="poll_http_uncertain", polls=attempt + 1)
            status_payload = _payload(status_response)
            if status_payload is None or type(status_payload.get("code")) is not int or status_payload["code"] != 0:
                return DeliveryResult("unknown", pushid=pushid, detail="poll_response_uncertain", polls=attempt + 1)
            status_data = status_payload.get("data")
            if not isinstance(status_data, dict):
                return DeliveryResult("unknown", pushid=pushid, detail="poll_data_missing", polls=attempt + 1)
            status = _wxstatus(status_data.get("wxstatus"))
            if status in {"confirmed", "failed", "unknown"}:
                return DeliveryResult(status, pushid=pushid, detail="wechat_status", polls=attempt + 1)
        return DeliveryResult("unknown" if limit else "queued", pushid=pushid,
                              detail="poll_limit_reached" if limit else "post_queued",
                              polls=limit)


class MockDelivery:
    def __init__(self, status: str = "confirmed"):
        self.status = status
        self.sent: list[tuple[str, str]] = []

    def send(self, title: str, body: str) -> DeliveryResult:
        self.sent.append((title, body))
        return DeliveryResult(self.status, detail="mock")
