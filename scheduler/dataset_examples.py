"""דוגמאות לדאטהסט. האם קיים מועד אפשרי (feasible) מחושב אוטומטית לפי היומנים."""
from .calendar_utils import free_slots
from .data import CALENDARS

SUN, MON, TUE, WED, THU, FRI = (
    "2026-11-29", "2026-11-30", "2026-12-01", "2026-12-02", "2026-12-03", "2026-12-04"
)


def c(participants, minutes, d_from, d_to=None, earliest="09:00", latest="17:00"):
    return {
        "participants": participants,
        "duration_minutes": minutes,
        "date_from": d_from,
        "date_to": d_to or d_from,
        "earliest": earliest,
        "latest": latest,
    }


RAW = [
    ("קבע פגישה של שעה עם דנה ויוסי ביום ראשון הבא", c(["dana", "yossi"], 60, SUN)),
    ("חצי שעה עם משה ואבי ביום שני", c(["moshe", "avi"], 30, MON)),
    ("פגישה של שעתיים עם דנה, יוסי ומשה בשבוע הבא", c(["dana", "yossi", "moshe"], 120, SUN, THU)),
    ("שעה עם יוסי ביום רביעי", c(["yossi"], 60, WED)),
    ("45 דקות עם אבי ואלי ביום ראשון", c(["avi", "eli"], 45, SUN)),
    ("שעה וחצי עם דנה ומשה ביום שלישי אחרי 12:00", c(["dana", "moshe"], 90, TUE, earliest="12:00")),
    ("30 דקות עם דנה, יוסי, משה, אבי ואלי בשבוע הבא", c(["dana", "yossi", "moshe", "avi", "eli"], 30, SUN, THU)),
    ("שעה עם אלי ביום שישי", c(["eli"], 60, FRI)),
    ("שעתיים עם משה ביום חמישי לפני 12:00", c(["moshe"], 120, THU, latest="12:00")),
    ("שעה עם דנה ואבי ביום שלישי או רביעי", c(["dana", "avi"], 60, TUE, WED)),
    ("פגישה של 3 שעות עם יוסי ואלי ביום ראשון", c(["yossi", "eli"], 180, SUN)),
    ("20 דקות עם משה ביום שני בין 13:00 ל-15:00", c(["moshe"], 20, MON, earliest="13:00", latest="15:00")),
    ("שעה עם דנה ויוסי ביום חמישי אחרי 13:00", c(["dana", "yossi"], 60, THU, earliest="13:00")),
    ("חצי שעה עם אבי ביום רביעי עד 11:00", c(["avi"], 30, WED, latest="11:00")),
    ("פגישה של שעה עם דנה ביום שני", c(["dana"], 60, MON)),
    ("שעה עם יוסי ומשה בשבוע הבא, רק אחרי 15:00", c(["yossi", "moshe"], 60, SUN, THU, earliest="15:00")),
    ("90 דקות עם אלי ומשה ביום שלישי", c(["eli", "moshe"], 90, TUE)),
    ("שעה עם דנה, אבי ואלי ביום רביעי", c(["dana", "avi", "eli"], 60, WED)),
    ("חצי שעה עם יוסי ביום חמישי בין 9:00 ל-10:00", c(["yossi"], 30, THU, earliest="09:00", latest="10:00")),
    ("שעתיים עם אבי ויוסי ביום שני החל מ-12:00", c(["avi", "yossi"], 120, MON, earliest="12:00")),
    ("שעה עם משה ודנה ביום ראשון", c(["moshe", "dana"], 60, SUN)),
    ("45 דקות עם דנה ואלי ביום חמישי", c(["dana", "eli"], 45, THU)),
    ("פגישה של 4 שעות עם אלי ביום שני", c(["eli"], 240, MON)),
    ("שעה עם יוסי ביום ראשון בין 11:00 ל-13:00", c(["yossi"], 60, SUN, earliest="11:00", latest="13:00")),
    ("רבע שעה עם משה ואבי ביום רביעי אחרי 13:00", c(["moshe", "avi"], 15, WED, earliest="13:00")),
]


def build_examples():
    examples = []
    for request, constraints in RAW:
        slots = free_slots(constraints, CALENDARS)
        examples.append({
            "inputs": {"request": request, "calendars": CALENDARS},
            "outputs": {"constraints": constraints, "feasible": bool(slots)},
        })
    return examples


if __name__ == "__main__":
    for ex in build_examples():
        cons = ex["outputs"]["constraints"]
        n = len(free_slots(cons, CALENDARS))
        print(f"{'V' if n else 'X'} {n:3d} slots | {ex['inputs']['request']}")
