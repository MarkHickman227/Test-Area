#!/usr/bin/env python3
"""Live-API preflight before a staging deploy. Does not charge cards or load models."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

SAFE_PROMPT = (
    "An original fictional adult character, clearly 30 years old, studio portrait"
)
BLOCKED_PROMPT = "a child in an adult scene"


class Preflight:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.failures: list[str] = []

    def csrf(self) -> str:
        for cookie in self.jar:
            if cookie.name == "pc_csrf":
                return cookie.value
        return ""

    def request(self, method: str, path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        token = self.csrf()
        if token:
            headers["X-CSRF-Token"] = token
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read().decode()
                payload = json.loads(raw) if raw else {}
                return response.status, payload
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"raw": raw}
            return exc.code, payload
        except urllib.error.URLError as exc:
            return 0, {"error": str(exc.reason)}

    def expect(self, ok: bool, message: str) -> None:
        if not ok:
            self.failures.append(message)

    def check_public(self, expect_staging: bool) -> dict:
        health_status, health = self.request("GET", "/health")
        self.expect(health_status == 200, f"/health -> {health_status}")
        ready_status, ready = self.request("GET", "/ready")
        self.expect(
            ready_status == 200 and ready.get("status") == "ready",
            f"/ready -> {ready_status} {ready}",
        )
        meta_status, meta = self.request("GET", "/v1/meta/launch")
        self.expect(meta_status == 200, f"/v1/meta/launch -> {meta_status}")
        self.expect(
            meta.get("payments_enabled") is False,
            f"payments_enabled should be false, got {meta.get('payments_enabled')}",
        )
        backend = meta.get("generation_backend")
        if expect_staging:
            self.expect(
                backend == "mock",
                f"staging generation_backend should be mock, got {backend}",
            )
        else:
            self.expect(
                backend in {"mock", "comfyui"},
                f"generation_backend should be mock or comfyui, got {backend}",
            )
        self.expect(
            meta.get("payment_provider") == "none",
            f"payment_provider should be none, got {meta.get('payment_provider')}",
        )
        if expect_staging:
            self.expect(
                meta.get("sandbox_age") is False,
                f"staging sandbox_age should be false, got {meta.get('sandbox_age')}",
            )
            self.expect(
                meta.get("age_provider") == "http",
                f"staging age_provider should be http, got {meta.get('age_provider')}",
            )
        return meta

    def check_authenticated(self, email: str, password: str) -> None:
        status, body = self.request(
            "POST", "/v1/auth/login", {"email": email, "password": password}
        )
        self.expect(status == 200, f"login failed: {status} {body}")
        if status != 200:
            return
        account_status, account = self.request("GET", "/v1/account")
        self.expect(account_status == 200, f"/v1/account -> {account_status}")
        age = (account or {}).get("age_verification_status")
        payload = {
            "idempotency_key": f"preflight-{uuid4().hex}",
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": BLOCKED_PROMPT,
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        }
        if age != "PASSED":
            gen_status, gen = self.request(
                "POST",
                "/v1/generations",
                payload
                | {
                    "prompt": SAFE_PROMPT,
                    "idempotency_key": f"preflight-unverified-{uuid4().hex}",
                },
            )
            code = (gen.get("error") or {}).get("code")
            self.expect(
                gen_status == 403 and code == "AGE_VERIFICATION_REQUIRED",
                f"unverified generate should be AGE_VERIFICATION_REQUIRED, got {gen_status} {gen}",
            )
            pay_status, pay = self.request(
                "POST", "/v1/billing/checkout-session", {"product_id": "credits-40"}
            )
            self.expect(
                pay_status in {403, 503},
                f"unverified checkout should be blocked, got {pay_status} {pay}",
            )
            return
        blocked_status, blocked = self.request("POST", "/v1/generations", payload)
        code = (blocked.get("error") or {}).get("code")
        self.expect(
            blocked_status == 400 and code == "PROMPT_BLOCKED",
            f"blocked prompt should be PROMPT_BLOCKED, got {blocked_status} {blocked}",
        )
        ok_status, job = self.request(
            "POST",
            "/v1/generations",
            payload
            | {
                "prompt": SAFE_PROMPT,
                "idempotency_key": f"preflight-ok-{uuid4().hex}",
            },
        )
        self.expect(
            ok_status == 200 and job.get("status") == "COMPLETED",
            f"safe generate should complete, got {ok_status} {job}",
        )
        lib_status, library = self.request("GET", "/v1/library/outputs")
        self.expect(
            lib_status == 200 and isinstance(library, list) and len(library) >= 1,
            f"library should list outputs, got {lib_status} {library}",
        )
        pay_status, pay = self.request(
            "POST", "/v1/billing/checkout-session", {"product_id": "credits-40"}
        )
        self.expect(
            pay_status == 503,
            f"checkout should stay disabled, got {pay_status} {pay}",
        )

    def check_support(self, email: str, password: str, query: str) -> None:
        status, body = self.request(
            "POST", "/v1/auth/login", {"email": email, "password": password}
        )
        self.expect(status == 200, f"support login failed: {status} {body}")
        if status != 200:
            return
        found_status, found = self.request(
            "GET",
            "/v1/admin/support/users?q=" + urllib.parse.quote(query),
        )
        self.expect(found_status == 200, f"support search -> {found_status} {found}")
        rows = found if isinstance(found, list) else []
        self.expect(len(rows) >= 1, f"support search returned no rows for q={query}")
        if rows:
            self.expect(
                rows[0].get("outputs_visible") is False,
                f"support search must hide outputs, got {rows[0]}",
            )
            self.expect(
                "url" not in rows[0] and "outputs" not in rows[0],
                f"support search leaked output fields: {rows[0]}",
            )
        queue_status, queue = self.request("GET", "/v1/admin/queue")
        self.expect(
            queue_status == 403,
            f"support must not open the moderation queue, got {queue_status} {queue}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--support-email", default="")
    parser.add_argument("--support-password", default="")
    parser.add_argument("--support-query", default="adult")
    parser.add_argument("--expect-staging", action="store_true")
    args = parser.parse_args()
    run = Preflight(args.base)
    run.check_public(args.expect_staging)
    if args.email and args.password:
        run.check_authenticated(args.email, args.password)
    if args.support_email and args.support_password:
        support = Preflight(args.base)
        support.check_support(
            args.support_email, args.support_password, args.support_query
        )
        run.failures.extend(support.failures)
    if run.failures:
        print("preflight FAILED")
        for item in run.failures:
            print(f"- {item}")
        return 1
    print("preflight OK")
    print(f"base={args.base} staging={args.expect_staging}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
