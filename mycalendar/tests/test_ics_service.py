from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from icalendar import Calendar

from mycalendar.services.ics import build_calendar, parse_row


BRUSSELS = ZoneInfo("Europe/Brussels")


def test_parse_row_dd_mm_yyyy_with_dot_time():
    row = "31/12/2021;21.30;RBP;SCC;Avenue Des Vaillants 2 1200 Woluwé-St-Lambert;"
    event = parse_row(row, tz=BRUSSELS)
    assert event.summary == "RBP-SCC"
    assert event.start == datetime(2021, 12, 31, 21, 30, tzinfo=BRUSSELS)
    assert event.location == "Avenue Des Vaillants 2 1200 Woluwé-St-Lambert"


def test_parse_row_iso_date_with_colon_time():
    row = "2021-12-31;21:30;RBP;;;"
    event = parse_row(row, tz=BRUSSELS)
    assert event.summary == "RBP"
    assert event.start == datetime(2021, 12, 31, 21, 30, tzinfo=BRUSSELS)
    assert event.location is None


def test_parse_row_too_few_fields_returns_none():
    assert parse_row("only;two", tz=BRUSSELS) is None


def test_parse_row_bad_date_raises():
    with pytest.raises(ValueError):
        parse_row("bogus;21:30;A;B;;", tz=BRUSSELS)


def test_build_calendar_produces_valid_ics():
    csv_text = (
        "31/12/2021;21.30;RBP;SCC;Av Des Vaillants 2;\n"
        "2022-01-15;09:00;Solo;;;\n"
    )
    ics_bytes = build_calendar(csv_text, name="My Cal", tz=BRUSSELS)
    cal = Calendar.from_ical(ics_bytes)
    events = [c for c in cal.walk("vevent")]
    assert len(events) == 2
    assert str(events[0]["summary"]) == "RBP-SCC"
    assert str(events[1]["summary"]) == "Solo"


def test_parse_row_strips_trailing_crlf():
    row = "31/12/2021;21:30;Home;Away;Brussels Avenue;\r\n"
    event = parse_row(row, tz=BRUSSELS)
    assert event.location == "Brussels Avenue"


def test_parse_row_strips_whitespace_in_fields():
    row = " 31/12/2021 ; 21:30 ; Home ; Away ; Brussels Avenue ;"
    event = parse_row(row, tz=BRUSSELS)
    assert event.summary == "Home-Away"
    assert event.location == "Brussels Avenue"
    assert event.start == datetime(2021, 12, 31, 21, 30, tzinfo=BRUSSELS)


def test_parse_row_three_fields_only():
    event = parse_row("31/12/2021;21:30;Solo", tz=BRUSSELS)
    assert event.summary == "Solo"
    assert event.location is None


def test_parse_row_short_away_field_collapses_to_home():
    event = parse_row("31/12/2021;21:30;Home;A;Av Foo;", tz=BRUSSELS)
    assert event.summary == "Home"


def test_build_calendar_with_empty_input_returns_valid_empty_calendar():
    ics_bytes = build_calendar("", name="Empty", tz=BRUSSELS)
    cal = Calendar.from_ical(ics_bytes)
    assert list(cal.walk("vevent")) == []
    assert str(cal["X-WR-CALNAME"]) == "Empty"


def test_build_calendar_sanitizes_crlf_in_name():
    malicious_name = "Evil\r\nX-INJECTED:yes"
    ics_bytes = build_calendar("", name=malicious_name, tz=BRUSSELS)
    raw = ics_bytes.decode("utf-8", errors="replace")
    assert "X-INJECTED" not in raw
    assert "Evil" in raw
