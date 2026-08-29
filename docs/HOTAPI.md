# HotAPI image generation

HotAPI is an optional hosted text-to-image backend. The product UI stays PrivateCanvas. Users never call HotAPI from the browser.

Fields below come from the HotAPI docs MCP (`search_docs`, `get_openapi_operation`) for `POST /v1/z-image-spicy` and `GET /v1/tasks/{id}`.

## What we call

- Server: `https://api.hotapi.ai`
- Auth: `Authorization: Bearer $HOTAPI_KEY` (server-side only)
- Submit: `POST /v1/z-image-spicy` with `prompt`, `width` (256–1536), `height` (256–1536), optional `seed`, optional `Idempotency-Key`
- High quality: `POST /v1/seedream-5.0-lite-spicy/text-to-image` with `prompt`, `size=2K`, `aspect_ratio`
- Poll: `GET /v1/tasks/{id}` until `succeeded` | `failed` | `cancelled`
- Copy `output.assets[].url` into PrivateCanvas storage before the CDN expiry

Do not implement face-swap, image-edit, or video. Those operations exist on HotAPI and are out of product scope.

## Local enable

```bash
export GENERATION_BACKEND=hotapi
export HOTAPI_KEY=hk_live_...
export JOB_EXECUTION=inline
```

Then generate from `/generate` or `POST /v1/generate-image` (`prompt`, `size`, `quality`) as an authenticated adult account.

Default remains `GENERATION_BACKEND=mock`. Staging/production boot still requires mock until a vendor go/no-go.
