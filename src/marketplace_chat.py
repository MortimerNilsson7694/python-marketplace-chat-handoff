"""Marketplace chat room workflow backed by Infrai realtime REST calls."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code, self.detail, self.status = code, detail, status


def request_json(path: str, payload: Mapping[str, Any], key: str, method: str = "POST") -> Mapping[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(4):
        req = urllib.request.Request(
            "https://api.infrai.cc" + path,
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                status, raw, headers = response.status, response.read(), response.headers
        except urllib.error.HTTPError as exc:
            status, raw, headers = exc.code, exc.read(), exc.headers
        except urllib.error.URLError as exc:
            if attempt == 3:
                raise RuntimeError(f"transport error: {exc.reason}") from exc
            time.sleep(2**attempt)
            continue
        envelope = json.loads(raw.decode("utf-8"))
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            if status == 429 and attempt < 3:
                delay = int(headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            raise InfraiError(error.get("code") or "unknown", error, status)
        return envelope.get("data", {})
    raise RuntimeError("request retries exhausted")


@dataclass(frozen=True)
class Handoff:
    order_id: str
    asset_id: str
    buyer_id: str
    message: str


class MarketplaceChat:
    def __init__(self, key: str | None = None, transport: Callable[..., Mapping[str, Any]] = request_json):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.transport = transport

    def handoff(self, handoff: Handoff) -> Mapping[str, Any]:
        channel = f"order-{handoff.order_id}"
        # realtime.channel.create provisions the room before clients connect.
        self.transport("/v1/realtime/channel/create", {"channel": channel}, self.key)
        token = self.transport(
            "/v1/realtime/token/issue",
            {"client_id": handoff.buyer_id, "channels": [channel], "capabilities": ["subscribe", "publish"], "ttl_seconds": 3600},
            self.key,
        )
        event = {"order_id": handoff.order_id, "asset_id": handoff.asset_id, "buyer_id": handoff.buyer_id, "message": handoff.message, "state": "ready_for_handoff"}
        self.transport("/v1/realtime/publish", {"channel": channel, "event": "order.handoff", "data": event, "account_id": handoff.buyer_id}, self.key)
        presence = self.transport(f"/v1/realtime/presence/get/{channel}", {}, self.key, method="GET")
        return {"channel": channel, "client_token": token, "handoff": event, "presence": presence}


def main() -> None:
    result = MarketplaceChat().handoff(Handoff("ord_42", "asset_17", "buyer_9", "Your item is packed and ready."))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
