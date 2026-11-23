"""כלים דטרמיניסטיים לבדיקת מועדים - ללא מודל שפה.

משמשים גם בתוך הגרף (צומת check_slot) וגם ב-evaluators של LangSmith.
"""
from datetime import datetime, timedelta, date

FMT = "%Y-%m-%dT%H:%M"
NON_WORKING_WEEKDAYS = {4, 5}  # Python: שישי=4, שבת=5


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, FMT)


def _hm(s: str):
    h, m = s.split(":")
    return int(h), int(m)


def validate_slot(start: str, constraints: dict, calendars: dict) -> list[str]:
    """מחזיר רשימת הפרות. רשימה ריקה = המועד תקין."""
    violations: list[str] = []
    try:
        st = parse_dt(start)
    except (ValueError, TypeError):
        return [f"Invalid start format '{start}', expected YYYY-MM-DDTHH:MM"]

    end = st + timedelta(minutes=int(constraints["duration_minutes"]))
    d_from = date.fromisoformat(constraints["date_from"])
    d_to = date.fromisoformat(constraints["date_to"])

    if not (d_from <= st.date() <= d_to):
        violations.append(
            f"Date {st.date()} is outside the requested range {d_from}..{d_to}"
        )
    if st.weekday() in NON_WORKING_WEEKDAYS:
        violations.append(f"{st.date()} is a Friday/Saturday - not a working day")

    eh, em = _hm(constraints["earliest"])
    lh, lm = _hm(constraints["latest"])
    day_earliest = st.replace(hour=eh, minute=em)
    day_latest = st.replace(hour=lh, minute=lm)
    if st < day_earliest or end > day_latest:
        violations.append(
            f"Meeting {st:%H:%M}-{end:%H:%M} is outside allowed hours "
            f"{constraints['earliest']}-{constraints['latest']}"
        )

    for person in constraints["participants"]:
        if person not in calendars:
            violations.append(f"Unknown participant '{person}'")
            continue
        for busy in calendars[person]:
            b_st, b_end = parse_dt(busy["start"]), parse_dt(busy["end"])
            if st < b_end and b_st < end:
                violations.append(
                    f"Conflict: {person} is busy {busy['start']}..{busy['end'][-5:]}"
                )
    return violations


def free_slots(constraints: dict, calendars: dict, step_minutes: int = 15) -> list[str]:
    """כל זמני ההתחלה החוקיים (בקפיצות של step_minutes)."""
    result = []
    d = date.fromisoformat(constraints["date_from"])
    d_to = date.fromisoformat(constraints["date_to"])
    eh, em = _hm(constraints["earliest"])
    lh, lm = _hm(constraints["latest"])
    while d <= d_to:
        t = datetime(d.year, d.month, d.day, eh, em)
        day_latest = datetime(d.year, d.month, d.day, lh, lm)
        while t + timedelta(minutes=int(constraints["duration_minutes"])) <= day_latest:
            s = t.strftime(FMT)
            if not validate_slot(s, constraints, calendars):
                result.append(s)
            t += timedelta(minutes=step_minutes)
        d += timedelta(days=1)
    return result
