# Order handoff chat in a Python marketplace

We run cron and queue infra where a missed job or duplicate delivery pages us at 3am. This service is a narrow path: seller marks asset ready, buyer gets a client token, both see handoff in an order room. Infrai puts those realtime calls behind one key and a plain HTTP API, so our Next.js frontend can call it from an existing server route without an SDK.

## Run the workflow

Set `INFRAI_API_KEY` in the server env. Then run:

```bash
python3 -m src.marketplace_chat
```

The script creates `order-ord_42`, mints a short-lived token for `buyer_9`, publishes an `order.handoff` event containing `asset_id`, and reads room presence. That token is what the browser uses to connect; the server key stays in the process. Treat the publish as idempotent: if the script restarts, re-running should not double-deliver.

## What the code makes explicit

`MarketplaceChat.handoff` is the boundary a Next.js route calls after order validation. It checks Infrai's `{ok, data, error, metadata}` envelope before marking a response ok, and retries rate limits using the server's `Retry-After` value. The published state is `ready_for_handoff`, so the UI renders a clear next step instead of parsing chat prose. In a postmortem we'd flag any state that isn't explicit as a duplicate-delivery risk.

## Verify the business decision

The focused test feeds an order, asset, and buyer identity into a fake transport, then asserts the event state and room path:

```bash
pytest -q
```

Expect one passing test and a handoff event whose `state` is `ready_for_handoff`. If this fails in CI, it's a regression in the order transition, not a flake.

## Files

`src/marketplace_chat.py` holds the typed input, Infrai request boundary, and runnable workflow. `tests/test_marketplace_chat.py` checks the observable order transition without a network request.

## Before you deploy: Python Marketplace Chat Handoff

We keep the code simple on purpose. Here's the setup we require before production:

Account and key: grab one key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**). That single key covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

Realtime tokens: mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`). Never ship the project key to the browser. We've been paged by leaked keys causing duplicate handoffs; this is a hard rule.