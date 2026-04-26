"""Pure CSV→ICS conversion. No Django, no IO."""
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, vText


DEFAULT_EVENT_DURATION = timedelta(hours=1, minutes=30)


@dataclass(frozen=True)
class ParsedEvent:
    summary: str
    start: datetime
    location: Optional[str]
    uid: str
    duration: timedelta = DEFAULT_EVENT_DURATION

    def end(self) -> datetime:
        return self.start + self.duration


def _parse_date(token: str) -> tuple[int, int, int]:
    if "/" in token:
        day, month, year = token.split("/")
    elif "-" in token:
        year, month, day = token.split("-")
    else:
        raise ValueError(f"unrecognized date format: {token!r}")
    return int(year), int(month), int(day)


def _parse_time(token: str) -> tuple[int, int]:
    sep = "." if "." in token else ":" if ":" in token else None
    if sep is None:
        raise ValueError(f"unrecognized time format: {token!r}")
    hour, minute = token.split(sep)
    return int(hour), int(minute)


def parse_row(row: str, *, tz: ZoneInfo, event_duration: timedelta = DEFAULT_EVENT_DURATION) -> Optional[ParsedEvent]:
    fields = [f.strip() for f in row.rstrip("\r\n").split(";")]
    if len(fields) < 3:
        return None

    year, month, day = _parse_date(fields[0])
    hour, minute = _parse_time(fields[1])
    start = datetime(year, month, day, hour, minute, tzinfo=tz)

    home = fields[2]
    away = fields[3] if len(fields) > 3 else ""
    summary = f"{home}-{away}" if len(away) >= 2 else home

    location: Optional[str] = None
    if len(fields) > 4 and len(fields[4]) > 5:
        location = fields[4]

    uid = hashlib.sha224(f"{fields[0]}{summary}".encode("utf-8")).hexdigest()
    return ParsedEvent(summary=summary, start=start, location=location, uid=uid, duration=event_duration)


def build_calendar(csv_text: str, *, name: str, tz: ZoneInfo, event_duration: timedelta = DEFAULT_EVENT_DURATION) -> bytes:
    safe_name = name.splitlines()[0].strip() if name.strip() else ""
    cal = Calendar()
    cal.add("prodid", f"-// {safe_name} //")
    cal.add("version", "2.0")
    cal.add("X-WR-CALNAME", safe_name)

    now = datetime.now(tz=tz)
    for row in csv_text.splitlines():
        if not row.strip():
            continue
        parsed = parse_row(row, tz=tz, event_duration=event_duration)
        if parsed is None:
            continue
        event = Event()
        event.add("summary", parsed.summary)
        event.add("dtstart", parsed.start)
        event.add("dtend", parsed.end())
        event.add("dtstamp", now)
        if parsed.location:
            event["location"] = vText(parsed.location)
        event["uid"] = parsed.uid
        cal.add_component(event)

    return cal.to_ical()
