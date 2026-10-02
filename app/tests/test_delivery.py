import httpx
import logging

from arxivdaily.delivery import MockDelivery, ServerChan


def test_post_acceptance_is_queued_then_confirmed(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCTtest123")
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"code": 0, "data": {"pushid": "12", "readkey": "secret-canary"}})
        assert "secret-canary" in str(request.url)
        return httpx.Response(200, json={"code": 0, "data": {"wxstatus": {"errcode": 0, "errmsg": "ok"}}})

    delivery = ServerChan({}, httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)
    result = delivery.send("Digest", "body")
    assert result.status == "confirmed" and result.polls == 1
    assert "secret-canary" not in str(result.to_dict())
    assert len([call for call in calls if call.method == "POST"]) == 1


def test_empty_wxstatus_exhausts_finite_polls(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCTtest123")
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"code": 0, "data": {"pushid": 9, "readkey": "secret-canary"}})
        return httpx.Response(200, json={"code": 0, "data": {"wxstatus": ""}})

    result = ServerChan({"delivery": {"poll_limit": 2}}, httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None).send("Digest", "body")
    assert result.status == "unknown" and result.polls == 2
    assert len(requests) == 3
    assert "secret-canary" not in repr(result)


def test_ambiguous_post_is_not_retried(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCTtest123")
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("secret-canary")

    result = ServerChan({}, httpx.Client(transport=httpx.MockTransport(handler))).send("Digest", "body")
    assert result.status == "unknown" and count == 1
    assert "secret-canary" not in repr(result)


def test_business_failure_and_unrecognized_wxstatus(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCTtest123")
    failed = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"code": 40001, "message": "secret-canary"})))
    assert ServerChan({}, failed).send("Digest", "body").status == "failed"

    def unknown(request):
        if request.method == "POST":
            return httpx.Response(200, json={"code": 0, "data": {"pushid": 1, "readkey": "r"}})
        return httpx.Response(200, json={"code": 0, "data": {"wxstatus": "some novel shape"}})

    result = ServerChan({}, httpx.Client(transport=httpx.MockTransport(unknown))).send("Digest", "body")
    assert result.status == "unknown"
    assert MockDelivery().send("x", "y").status == "confirmed"


def test_httpx_request_logs_redact_sendkey_and_readkey(monkeypatch, caplog):
    sendkey = "SCTsecretcanary123"
    readkey = "readkey-canary-456"
    monkeypatch.setenv("SERVERCHAN_SENDKEY", sendkey)

    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"code": 0, "data": {"pushid": "19", "readkey": readkey}})
        return httpx.Response(200, json={"code": 0, "data": {"wxstatus": {"errcode": 0}}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    delivery = ServerChan({}, client)
    with caplog.at_level(logging.INFO, logger="httpx"):
        result = delivery.send("Digest", "body")
    assert result.status == "confirmed"
    assert "HTTP Request" in caplog.text
    assert "[REDACTED]" in caplog.text
    assert sendkey not in caplog.text and readkey not in caplog.text
    assert sendkey not in repr(result) and readkey not in repr(result)


def test_malformed_receipt_cannot_flatten_readkey_into_public_pushid(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY","SCTtest123")
    secret = "nonce-readkey-1234"
    for pushid in ({"readkey":secret},secret):
        client = httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={"code":0,"data":{"pushid":pushid,"readkey":secret}})))
        result = ServerChan({},client).send("Digest","body")
        assert result.status == "unknown" and secret not in repr(result.to_dict())


def test_boolean_poll_code_cannot_confirm_wechat_delivery(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY","SCTtest123")
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200,json={"code":0,"data":{"pushid":12,"readkey":"private-nonce"}})
        return httpx.Response(200,json={"code":False,"data":{"wxstatus":{"errcode":0}}})
    result = ServerChan({},httpx.Client(transport=httpx.MockTransport(handler))).send("Digest","body")
    assert result.status == "unknown"
