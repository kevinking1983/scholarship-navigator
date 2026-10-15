"""Build an iCalendar (.ics) file of open scholarship deadlines. No external deps."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable


def _esc(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets are folded with CRLF + space."""
    out, chunk = [], line
    while len(chunk.encode("utf-8")) > 73:
        out.append(chunk[:70])
        chunk = " " + chunk[70:]
    out.append(chunk)
    return "\r\n".join(out)


def build_ics(ranked: Iterable[dict[str, Any]], today: date | None = None) -> str:
    today = today or date.today()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Scholarship Navigator//HackIIITD 2026//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Scholarship deadlines",
    ]
    count = 0
    for item in ranked:
        dl = item.get("match", {}).get("deadline") or {}
        iso = dl.get("date")
        if not iso or dl.get("closed"):
            continue
        d = date.fromisoformat(iso) if isinstance(iso, str) else iso
        uid = hashlib.sha1(f"{item.get('name')}|{iso}".encode()).hexdigest()[:16] + "@scholarship-navigator"
        desc = (f"{item.get('provider', '')} · {item.get('amount', '')}\\n"
                f"Apply: {item.get('application_url') or item.get('source_url', '')}\\n"
                "Verify details on the official portal before applying.")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
            _fold("SUMMARY:" + _esc(f"Deadline: {item.get('name')}")),
            _fold("DESCRIPTION:" + _esc(desc).replace("\\\\n", "\\n")),
            _fold("URL:" + str(item.get("application_url") or item.get("source_url") or "")),
            "BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-P3D",
            _fold("DESCRIPTION:" + _esc(f"3 days left: {item.get('name')}")),
            "END:VALARM",
            "END:VEVENT",
        ]
        count += 1
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n", count
