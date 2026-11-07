# Vercel Services

Deploy this repository as **one Vercel project**, with the repository root as
the project's Root Directory. The root `vercel.json` defines two independently
built services:

| Service | Root | Entrypoint / output | Public paths |
| --- | --- | --- | --- |
| `backend` | `backend` | FastAPI `app.main:app`, Python 3.14 | `/api`, `/api/*` |
| `frontend` | `frontend` | Vite build in `dist`, Node.js 24 | All remaining paths |

Top-level rewrites preserve the original request path. FastAPI already uses
`/api`, so do not strip that prefix or add another `/api`. API documentation
is at `/api/docs`, ReDoc at `/api/redoc`, and the schema at
`/api/openapi.json`. An API 404 stays an API 404.

The frontend's service-level rewrite serves `index.html` for extensionless
SPA deep links:
`/login`, `/register`, `/courses`, `/tutoring`, `/learning`, etc.
Asset/file paths and Vite development paths (`/@*`, `/src/*`,
`/node_modules/*`) are excluded, keeping JS, CSS, and icons intact in both
development and deployment. The fallback is inside the frontend service and
cannot swallow API requests.

## Calls and bindings

The React application runs in the **browser** and calls the same-origin
`/api`. Vercel routes those public requests into FastAPI. This is not a
server-to-server call, so the manifest declares **no service bindings**.

There is currently no internal-only application service. PostgreSQL, VNPAY,
and Google Drive are external dependencies, not services declared in this
project. A Vercel binding cannot replace their URLs or credentials.

If a server function is added later and calls another service, declare the
binding on that calling service and read its injected URL in the function
at runtime. Do not set the binding variable manually or expose it through
`VITE_*`: bindings do not resolve at build time or in browser JavaScript.

## Environment variables

Set values in the Vercel project's environment settings for each desired
environment. The ignored local `.env`, `.env.local`, and `.env.seed` files
are not deployment configuration and are excluded by `.vercelignore`.

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Hosted PostgreSQL connection URL, with percent-encoded password |
| `JWT_SECRET_KEY` | Your backend signing key, at least 32 bytes |
| `VNPAY_TMN_CODE`, `VNPAY_HASH_SECRET` | Optional sandbox merchant credentials |
| `VNPAY_PAYMENT_URL` | `https://sandbox.vnpayment.vn/paymentv2/vpcpay.html` |
| `VNPAY_RETURN_URL` | `https://YOUR-DOMAIN/payment/vnpay-return` |
| `VNPAY_QUERY_IP` | Optional known server IP for QueryDR; blank uses the ASGI listener address, not the customer's IP or public NAT discovery |
| `VITE_API_BASE_URL` | Leave unset or empty; requests must remain on the same origin |
| `CORS_ORIGINS` | Optional explicit origins if a separate client calls the API |

Vercel supplies `VERCEL`; do not define it yourself. No binding URL variables
are needed for the current architecture. Backend secrets must never use a
`VITE_` prefix.

For Supabase, copy the **transaction pooler** URL from Connect, using port
`6543`, and change its scheme to `postgresql+psycopg`. Include
`sslmode=require`. Do not use a local PostgreSQL URL on Vercel:

Hướng dẫn backend, thứ tự ưu tiên `.env.local` và lệnh kiểm tra đúng
Supabase: [Supabase PostgreSQL](supabase.md).

```text
postgresql+psycopg://USER:ENCODED_PASSWORD@POOLER_HOST:6543/postgres?sslmode=require
```

The engine limits each Vercel instance to one connection, disables Psycopg's
automatic prepared statements, and sets UTC inside each transaction when
using port 6543. It does not send session startup options to that pooler.
Outside Vercel, ordinary direct connections keep their existing defaults.

Run Alembic migrations against the deployment database separately, using a
direct or session-pooler connection. Run from the repository root with the
intended `DATABASE_URL` set in that terminal:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Migrations and demo seeds do not run automatically during a deployment or
function startup. Local seeded rows are not uploaded with the code. After
migrating Supabase, run the [Supabase seed workflow](seed-data.md#seed-trên-supabase-sau-khi-deploy)
once against the same database configured in Vercel, reusing the local
`.env.seed` credentials. Accounts are stored in `public.users`, rather than
Supabase Authentication. The backend function includes migration scripts so its
`/api/ready` check can compare database and application schema versions
without relying on the root `alembic.ini` being in the function bundle.

## Local verification

With Node.js 24, Python 3.14, frontend dependencies, backend dependencies,
and a configured database, run from the repository root:

```powershell
npx vercel@latest dev --local --listen 127.0.0.1:3000
```

`--local` runs `vercel dev` without linking to a cloud project or downloading
cloud environment variables. It does not publish the repository. For linked
project environment variables, use `npx vercel@latest dev` instead.

Check these URLs through the shared Vercel gateway:

- `http://127.0.0.1:3000/` and `/login`: frontend HTML, including after reload.
- `http://127.0.0.1:3000/api/health`: FastAPI JSON.
- `http://127.0.0.1:3000/api/ready`: database/schema readiness.
- `http://127.0.0.1:3000/api/docs`: Swagger UI using `/api/openapi.json`.
- `http://127.0.0.1:3000/api/missing-route`: API JSON 404, not frontend HTML.

Vercel service development handles `/api` at the gateway. The Vite proxy to
`127.0.0.1:8000` is used only for standalone `npm run dev` with a separate
local Uvicorn process; it is disabled when Vercel supplies `VERCEL=1`.

On Windows, Vercel CLI dependency installation can require symbolic-link
privileges. If `vercel dev` stops with an `EPERM ... symlink` error, it has
not started the gateway; run the integration check in an environment that
already supports those links, such as Linux/WSL or CI. No OS security
settings are changed by this repository.

The local gateway checks for this change were also run successfully through
the same CLI version's installed JavaScript entrypoint
(`@vercel/cli-support/dist/vc.js dev --local`), in a retained terminal.
They covered SPA deep links, Vite JS modules, the favicon, API health/docs,
API JSON 404s, and database readiness. No cloud deployment was created.

## VNPAY and attachment storage

Register the final public HTTPS IPN address with VNPAY:

```text
https://YOUR-DOMAIN/api/payments/vnpay/ipn
```

The endpoint must be reachable by VNPAY without an interactive Vercel login.
Preview Deployment Protection may prevent external IPN delivery; verify the
chosen deployment's access policy before testing sandbox payments.

**Attachments still require an external storage implementation before use on
Vercel.** The existing tutor chat upload/download code writes private files
to `uploads/tutoring` on the local filesystem. A Vercel function's local
filesystem is not durable attachment storage; moving it to `/tmp` would
still lose files between instances. Supabase Storage is a possible follow-up,
while keeping the existing booking/dispute authorization checks.

The current attachment limit is 5 MiB, above Vercel Functions' 4.5 MB request
limit. Before enabling uploads, either reduce both frontend/backend limits
or implement authorized direct-to-storage uploads. Existing local uploads
are excluded from deployment and are not migrated by this configuration.

## References

- [Vercel Services](https://vercel.com/docs/services)
- [Service routing](https://vercel.com/docs/services/routing)
- [Service bindings](https://vercel.com/docs/services/bindings)
- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vite SPA routing](https://vercel.com/docs/frameworks/frontend/vite)
- [Supabase PostgreSQL connections](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Vercel Function limits](https://vercel.com/docs/functions/limitations)
