"""API routing package (V4/P1).

Endpoints are grouped by resource into ``APIRouter`` modules so ``main.py``
only assembles the app (middleware, instrumentation, router registration)
instead of defining every route inline:

- :mod:`api.health`  — liveness + storage state
- :mod:`api.chat`    — POST /api/chat and the session CRUD that drives the UI
- :mod:`api.profile` — L2 profile and L3 recall
- :mod:`api.plan`    — plan lifecycle, SSE stream, history, feedback

Shared cross-cutting pieces live in :mod:`api.rate_limit` (the single slowapi
``Limiter`` instance) and :mod:`api.errors` (uniform error responses).
"""
