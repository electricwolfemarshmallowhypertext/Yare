from __future__ import annotations

import os
import secrets
from starlette.types import ASGIApp, Scope, Receive, Send

class CSPNonceMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        nonce = secrets.token_urlsafe(16)
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                csp = f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:"
                headers.append((b"content-security-policy", csp.encode()))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"referrer-policy", b"no-referrer"))
            await send(message)

        scope["csp_nonce"] = nonce
        await self.app(scope, receive, send_wrapper)