"""Sentry configuration (django_myical/sentry.py, sentry-sdk 3).

Unit tests on the callbacks, then a real sentry-sdk client with the production
options and a capturing transport, reading what would have been sent.
"""

import json
import logging
import warnings

import pytest
import sentry_sdk
from django.core.exceptions import DisallowedHost
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from django_myical.sentry import before_send, before_send_span, sentry_options
from django_myical.sentry_scrub import FILTERED

SECRETS = ("hunter2", "abc123", "k3y", "Bearer xyz", "203.0.113.9")


def leaked(data, *secrets):
    text = json.dumps(data, default=str)
    return [s for s in secrets if s in text]


def test_init_raises_no_warning_and_collects_no_more():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = sentry_sdk.Client(dsn=None, default_integrations=False, **sentry_options())
    assert [str(w.message) for w in caught] == []
    dc = client.options["data_collection"]
    assert dc["user_info"] is False
    assert dc["cookies"] == {"mode": "off"}
    assert dc["http_bodies"] == []
    assert dc["queues"] is False
    assert dc["database_query_data"] is False
    assert dc["mcp"] == {"inputs": False, "outputs": False}
    assert dc["stack_frame_variables"] == {"mode": "denylist"}
    assert client.options["attach_stacktrace"] is False


def test_integrations():
    options = sentry_options()
    assert options["data_collection"]["http_headers"]["response"] == {"mode": "off"}
    django, logs = options["integrations"]
    assert isinstance(django, DjangoIntegration) and django.cache_spans is False
    assert isinstance(logs, LoggingIntegration)
    assert logs._logs_handler is None  # no Sentry Logs
    assert logs._event_handler.level == logging.ERROR


def test_before_send_masks_request_data_extra_and_local_vars():
    event = before_send({
        "request": {"data": {"password": "hunter2", "title": "ok"},
                    "headers": {"Authorization": "Bearer xyz", "Accept": "*/*"}},
        "extra": {"token": "abc123", "page": 3},
        "user": {"id": "7", "ip_address": "203.0.113.9"},
        "breadcrumbs": {"values": [{"data": {"api_key": "k3y", "n": 1}}]},
        "exception": {"values": [{"stacktrace": {"frames": [
            {"vars": {"password": "hunter2", "i": 2}}]}}]},
    }, {})
    assert leaked(event, *SECRETS) == []
    assert event["request"]["data"]["title"] == "ok"
    assert event["request"]["headers"]["Accept"] == "*/*"
    assert event["extra"]["page"] == 3
    assert event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]["i"] == 2


def test_before_send_drops_disallowed_host():
    assert before_send({}, {"exc_info": (DisallowedHost, DisallowedHost("x"), None)}) is None


def test_before_send_span_masks_name_and_attributes():
    span = before_send_span({"name": "GET /feed/?token=abc123", "attributes": {
        "http.request.header.authorization": ["Bearer xyz"],
        "db.query.text": "SELECT 1 -- password=hunter2",
        "client.address": "203.0.113.9",
        "sentry.op": "http.server"}}, {})
    assert leaked(span, *SECRETS) == []
    assert span["name"] == "GET /feed/?token=" + FILTERED
    assert span["attributes"]["sentry.op"] == "http.server"


def test_before_send_span_never_sends_the_raw_span():
    class Trap(dict):
        def items(self):
            raise RuntimeError("boom")

    assert before_send_span({"name": "x", "attributes": Trap(password="hunter2")}, {}) == {
        "name": FILTERED, "attributes": {}}


class CapturingTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.sent = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.sent.append(item.payload.json)
            elif item.type == "span":
                self.sent.extend(dict(s, type="span") for s in item.payload.json["items"])


@pytest.fixture
def transport():
    transport = CapturingTransport()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sentry_sdk.init(dsn="https://key@sentry.invalid/1", transport=transport,
                        default_integrations=False, traces_sample_rate=1.0, **sentry_options())
    assert [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)] == []
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)


def test_logger_error_creates_an_event(transport):
    logging.getLogger("mycalendar.probe").error("Probe %s", "value")
    sentry_sdk.flush()
    events = [e for e in transport.sent if e.get("type", "event") == "event"]
    assert len(events) == 1
    assert events[0]["logentry"]["message"] == "Probe %s"


def test_local_password_variable_is_scrubbed(transport):
    # Built at run time: the source context (code) must not quote it.
    password = "probe-pw-" + str(6 * 7)
    try:
        raise ValueError("boom")
    except ValueError:
        sentry_sdk.capture_exception()
    sentry_sdk.flush()
    assert len(transport.sent) == 1
    assert leaked(transport.sent, password) == []


def test_sent_span_is_masked(transport):
    with sentry_sdk.start_span(name="GET /feed/?token=abc123",
                               attributes={"password": "hunter2", "note": "api_key=k3y"}):
        pass
    sentry_sdk.flush()
    spans = [e for e in transport.sent if e.get("type") == "span"]
    assert spans
    assert leaked(spans, *SECRETS) == []
