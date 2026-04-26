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
