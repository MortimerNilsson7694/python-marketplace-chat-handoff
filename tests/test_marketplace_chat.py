from src.marketplace_chat import Handoff, MarketplaceChat


def test_handoff_publishes_ready_state_and_returns_client_token():
    calls = []

    def fake(path, payload, key, method="POST"):
        calls.append((path, payload, method))
        if path.endswith("token/issue"):
            return {"token": "client-token"}
        return {"members": ["buyer_9"]} if method == "GET" else {}

    result = MarketplaceChat("test-key", fake).handoff(Handoff("ord_42", "asset_17", "buyer_9", "Packed"))
    assert result["handoff"]["state"] == "ready_for_handoff"
    assert result["client_token"]["token"] == "client-token"
    assert calls[0][1] == {"channel": "order-ord_42"}
    assert calls[2][1]["event"] == "order.handoff"
    assert calls[3][0] == "/v1/realtime/presence/get/order-ord_42"
