"""What the Sentry SDK may collect (sentry-sdk 3).

``data_collection`` collects no more than ``send_default_pii=False`` did: no
user (id, e-mail, IP), no cookies, no request or response bodies, no task
arguments, no SQL parameters. Headers, query strings and local variables go
through the SDK's sensitive-key denylist, plus the proxy/IP header terms the
SDK itself used when it mapped ``send_default_pii=False``.

sentry-sdk 3 removed its built-in ``EventScrubber``: ``django_myical.sentry_scrub``
re-applies its denylist from ``before_send`` (extra, breadcrumbs, frame
variables) and ``before_send_span`` (span name and attributes).
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import DisallowedHost
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from django_myical.sentry_scrub import scrub_event as _scrub_event
from django_myical.sentry_scrub import scrub_span

_PII_TERMS = ["forwarded", "-ip", "remote-", "via", "-user"]

DATA_COLLECTION: dict[str, Any] = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {
        "request": {"mode": "denylist", "terms": _PII_TERMS},
        # Ignored by sentry-sdk 3.0 (it collects no response headers and only
        # reads "request"); kept so a future SDK that adds it starts "off".
        # `contexts.response.headers` is also scrubbed in before_send.
        "response": {"mode": "off"},
    },
    "http_bodies": [],
    "url_query_params": {"mode": "denylist", "terms": _PII_TERMS},
    "graphql": {"document": False, "variables": False},
    "gen_ai": {"inputs": False, "outputs": False},
    "mcp": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "queues": False,
    "stack_frame_variables": {"mode": "denylist"},
    "frame_context_lines": 5,
}


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """The 2.x EventScrubber denylist, re-applied (first step of ``before_send``)."""
    return _scrub_event(event)


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    scrub_event(event, hint)
    # Internet scanners hit the raw EC2 IP; ical is nginx's implicit default vhost,
    # so Django rejects them as DisallowedHost (400). That rejection is the correct,
    # intended behaviour — not an error worth paging on. Drop it instead of letting
    # bot traffic flood Sentry (~500/day). Do NOT "fix" this by adding the IP to
    # ALLOWED_HOSTS — that would make Django serve Host-spoofed requests.
    exc = (hint or {}).get("exc_info")
    if exc and isinstance(exc[1], DisallowedHost):
        return None
    return event


def before_send_span(span: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Same denylist on span names and attributes (spans can't be dropped here)."""
    return scrub_span(span)


def sentry_options() -> dict[str, Any]:
    """``sentry_sdk.init`` options shared by the settings and the tests."""
    return {
        "integrations": [
            # sentry-sdk 3 turns cache spans on by default; 2.x had them off.
            DjangoIntegration(cache_spans=False),
            # sentry-sdk 3 no longer enables the logging integration by default,
            # and without event_level a logger.error() creates no event.
            # level=None: no Sentry Logs (2.x never sent them).
            LoggingIntegration(level=None, event_level=logging.ERROR,
                               breadcrumb_level=logging.INFO),
        ],
        # 3.0 default is True; keep plain messages without a stack, as before.
        "attach_stacktrace": False,
        "data_collection": DATA_COLLECTION,
        "before_send": before_send,
        "before_send_span": before_send_span,
    }
