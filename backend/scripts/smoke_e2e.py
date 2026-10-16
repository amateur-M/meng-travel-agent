"""End-to-end smoke check against a *running* server.

The pytest suite drives the ASGI app in-process; this drives the real HTTP API,
so it covers what those tests cannot: the startup lifespan, real uvicorn, and a
real PostgreSQL over the wire. It also walks the recovery checklist from
memory/DEPLOY.md section 5 that cannot be automated from a browser.

Start the server with OFFLINE_MODE=true so no external request is made:
deterministic, offline, and costs nothing. PostgreSQL stays pointed at the real
database, which is the point of this check.

    # terminal 1 (PowerShell)
    cd backend
    $env:OFFLINE_MODE='true'
    .\\.venv\\Scripts\\python.exe -m uvicorn main:app --port 8011

    # terminal 2
    .\\.venv\\Scripts\\python.exe scripts/smoke_e2e.py

Do NOT try to disable the integrations by blanking the key variables
(``$env:OPENAI_API_KEY=''``): an environment variable must be non-empty to
override ``.env``, so the empty value is ignored and the real keys stay active.
That mistake is why OFFLINE_MODE exists - see config/settings.py.

Assertions are deliberately tolerant of both modes (real model vs rule-based
mock): this script verifies the plumbing - persistence, ordering, idempotency,
session/plan linkage - while extraction quality is covered by unit tests.

Exits non-zero if any check fails. It cleans up the conversation, plan and
profile it created.
"""

import argparse
import json
import sys
import uuid

import httpx

PASS = "  ok   "
FAIL = "  FAIL "


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8011")
    args = parser.parse_args()

    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(PASS + label)
        else:
            print(FAIL + label + (f"  <- {detail}" if detail else ""))
            failures.append(label)

    client_id = f"smoke-{uuid.uuid4().hex[:8]}"
    session_id = None
    plan_id = None

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120.0) as client:
        print("\n[1] storage is really connected")
        health = client.get("/health").json()
        check("GET /health status == ok", health.get("status") == "ok", json.dumps(health.get("storage")))
        check(
            "postgres (plans) connected",
            health["storage"]["postgres"]["connected"],
            str(health["storage"]["postgres"].get("error")),
        )
        check(
            "postgres (chat) connected",
            health["storage"]["chat"]["connected"],
            str(health["storage"]["chat"].get("error")),
        )

        print("\n[2] two turns, persisted and readable in order")
        first = client.post(
            "/api/chat",
            json={
                "message": "我们从上海出发，想去大理玩三天，预算五千",
                "client_id": client_id,
                "message_id": f"t1-{uuid.uuid4().hex[:8]}",
            },
        ).json()
        session_id = first["session_id"]
        check("turn 1 returned a session_id", bool(session_id))
        check("turn 1 returned a reply", bool(first.get("reply")))
        # Tolerant of both modes: the real model returns a clean city name, while
        # the rule-based mock can swallow the following words ("大理玩三天").
        check(
            "turn 1 extracted the destination",
            "大理" in (first["slots"].get("destination") or ""),
            str(first["slots"]),
        )
        check("turn 1 extracted the origin", first["slots"].get("origin") == "上海", str(first["slots"]))

        client.post(
            "/api/chat",
            json={
                "message": "再帮我看看住宿",
                "session_id": session_id,
                "client_id": client_id,
                "message_id": f"t2-{uuid.uuid4().hex[:8]}",
            },
        )

        transcript = client.get(f"/api/chat/sessions/{session_id}/messages").json()
        roles = [m["role"] for m in transcript["items"]]
        check("transcript has both turns in order", roles == ["user", "assistant", "user", "assistant"], str(roles))
        check("transcript total is 4", transcript["total"] == 4, str(transcript["total"]))

        print("\n[3] refresh recovery: the state survives a new connection")
        detail = client.get(f"/api/chat/sessions/{session_id}").json()
        check(
            "session detail carries the slots forward",
            "大理" in (detail["slots"].get("destination") or ""),
            str(detail["slots"]),
        )
        check("session got an automatic title", bool(detail.get("title")), str(detail.get("title")))

        sessions = client.get(f"/api/chat/sessions?client_id={client_id}").json()["items"]
        check("conversation appears in the list", [s["session_id"] for s in sessions] == [session_id], str(sessions))
        check("list reports the message count", sessions[0]["message_count"] == 4, str(sessions[0]))

        print("\n[4] idempotency: replaying a turn id does not duplicate it")
        replay_id = f"replay-{uuid.uuid4().hex[:8]}"
        body = {"message": "重复一次", "session_id": session_id, "client_id": client_id, "message_id": replay_id}
        client.post("/api/chat", json=body)
        client.post("/api/chat", json=body)
        after = client.get(f"/api/chat/sessions/{session_id}/messages").json()
        user_hits = [m for m in after["items"] if m["content"] == "重复一次"]
        check("the replayed user turn exists exactly once", len(user_hits) == 1, f"found {len(user_hits)}")

        print("\n[5] cross-session profile (L2)")
        profile = client.get(f"/api/profile?client_id={client_id}").json()["profile"]
        check("profile learned the origin", profile.get("origin") == "上海", str(profile))

        patched = client.patch(
            "/api/profile",
            json={"client_id": client_id, "patch": {"origin": "北京", "avoid": ["辣"]}},
        ).json()["profile"]
        check("manual correction applied", patched.get("origin") == "北京", str(patched))
        check(
            "manual correction kept the previous value",
            (patched.get("conflicts") or {}).get("origin") == ["上海"],
            str(patched.get("conflicts")),
        )

        print("\n[6] plan pipeline over SSE, linked back to the conversation")
        created = client.post(
            "/api/plan",
            json={
                "origin": "北京",
                "destination": "大理",
                "start_date": "2026-09-01",
                "end_date": "2026-09-03",
                "budget": 5000,
                "preferences": ["浪漫", "美食"],
                "pace": "轻松",
                "session_id": session_id,
            },
        ).json()
        plan_id = created["plan_id"]
        check("POST /api/plan returned a plan_id", bool(plan_id))

        completed = False
        with client.stream("GET", f"/api/plan/{plan_id}/stream") as stream:
            event_name = None
            for line in stream.iter_lines():
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and event_name == "complete":
                    completed = True
                    break
        check("SSE stream emitted complete", completed)

        record = client.get(f"/api/plan/{plan_id}").json()
        check("plan readable from PostgreSQL", record.get("status") == "completed", str(record.get("status")))
        check("plan carries the generated itinerary", bool(record.get("response")), "response is empty")

        linked = client.get(f"/api/chat/sessions/{session_id}").json()
        check("conversation remembers its plan", linked.get("last_plan_id") == plan_id, str(linked.get("last_plan_id")))

        print("\n[7] delete cascades and forget-me")
        check("DELETE session ok", client.delete(f"/api/chat/sessions/{session_id}").status_code == 200)
        check("session is gone", client.get(f"/api/chat/sessions/{session_id}").status_code == 404)
        check("its messages are gone", client.get(f"/api/chat/sessions/{session_id}/messages").status_code == 404)
        session_id = None

        check(
            "DELETE profile ok",
            client.delete(f"/api/profile?client_id={client_id}").status_code == 200,
        )
        check(
            "profile is gone",
            client.get(f"/api/profile?client_id={client_id}").json()["profile"] == {},
        )

    if plan_id:
        with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30.0) as client:
            client.delete(f"/api/plan/{plan_id}")

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("PASS: all end-to-end checks passed against the running server")
    return 0


if __name__ == "__main__":
    sys.exit(main())
