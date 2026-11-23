"""ממשק משתמש למתאם הפגישות - לפי התאריך של היום.

    python -m streamlit run app.py
"""
import truststore
truststore.inject_into_ssl()

import random
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from scheduler.data import PARTICIPANTS
from scheduler.graph import VARIANTS, build_graph

load_dotenv()

HEB_DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
WORKDAYS = {6, 0, 1, 2, 3}  # ראשון-חמישי לפי weekday()
TODAY = date.today()
HORIZON_DAYS = 21  # כמה ימים קדימה יש יומנים

st.set_page_config(page_title="מתאם פגישות", page_icon="📅", layout="wide")
st.markdown(
    """<style>
    .stApp, [data-testid="stSidebar"] {direction: rtl; text-align: right;}
    .proposal {background:#f0f6ff; border:1px solid #c9dcf5; border-radius:12px;
               padding:18px 22px; margin:8px 0 16px 0; font-size:1.15rem;}
    .proposal b {font-size:1.35rem;}
    </style>""",
    unsafe_allow_html=True,
)


# ---------- יומנים ----------
def build_calendars(start, days):
    """יומנים לדוגמה לימים הקרובים. קבועים לכל תאריך (אותו תאריך = אותן פגישות)."""
    cals = {k: [] for k in PARTICIPANTS}
    for i in range(days):
        d = start + timedelta(days=i)
        if d.weekday() not in WORKDAYS:
            continue
        for key in PARTICIPANTS:
            rng = random.Random(f"{key}-{d.isoformat()}")
            if rng.random() < 0.08:  # עסוק כל היום
                cals[key].append({"start": f"{d}T09:00", "end": f"{d}T17:00"})
                continue
            for _ in range(rng.randint(0, 3)):
                h = rng.randint(9, 15)
                m = rng.choice([0, 30])
                dur = rng.choice([30, 60, 60, 90, 120])
                s = datetime(d.year, d.month, d.day, h, m)
                e = min(s + timedelta(minutes=dur), datetime(d.year, d.month, d.day, 17, 0))
                cals[key].append({"start": s.strftime("%Y-%m-%dT%H:%M"), "end": e.strftime("%Y-%m-%dT%H:%M")})
    for key in cals:  # מיון ואיחוד פגישות חופפות
        merged = []
        for b in sorted(cals[key], key=lambda b: b["start"]):
            if merged and b["start"] <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], b["end"])
            else:
                merged.append(dict(b))
        cals[key] = merged
    return cals


CALENDARS = build_calendars(TODAY, HORIZON_DAYS)


def week_start(d):
    """יום ראשון של השבוע שבו נמצא d."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def calendar_table(sunday):
    rows = {}
    for key, busy in CALENDARS.items():
        row = {}
        for i in range(5):
            d = sunday + timedelta(days=i)
            col = f"{HEB_DAYS[d.weekday()]} {d:%d.%m}"
            if d < TODAY:
                row[col] = "—"
                continue
            slots = [f"{b['start'][-5:]}–{b['end'][-5:]}" for b in busy if b["start"].startswith(d.isoformat())]
            row[col] = ", ".join(slots) or "פנוי"
        rows[PARTICIPANTS[key]] = row
    return pd.DataFrame(rows).T


# ---------- עזר ----------
@st.cache_resource
def get_graph():
    return build_graph()


def heb_name(key):
    return PARTICIPANTS.get(key, key)


def fmt_slot(start, minutes):
    s = datetime.strptime(start, "%Y-%m-%dT%H:%M")
    e = s + timedelta(minutes=minutes)
    return f"יום {HEB_DAYS[s.weekday()]} {s:%d.%m.%Y}, {s:%H:%M}–{e:%H:%M}"


ss = st.session_state
ss.setdefault("thread_id", None)
ss.setdefault("result", None)
ss.setdefault("log", [])
graph = get_graph()


def cfg():
    return {"configurable": {"thread_id": ss.thread_id}, "run_name": "scheduler-ui"}


def start(request, variant):
    ss.thread_id = str(uuid.uuid4())
    ss.log = [f"בקשה: {request}"]
    settings = {**VARIANTS[variant], "auto_approve": False, "today": TODAY.isoformat()}
    with st.spinner("מחפש מועד מתאים..."):
        ss.result = graph.invoke(
            {"request": request, "calendars": CALENDARS, "settings": settings}, cfg()
        )


def resume(decision, log_line):
    ss.log.append(log_line)
    with st.spinner("ממשיך..."):
        ss.result = graph.invoke(Command(resume=decision), cfg())


# ---------- צד ----------
with st.sidebar:
    st.header("הגדרות")
    variant = st.radio("גרסת הסוכן", list(VARIANTS), index=1)
    st.caption(str(VARIANTS[variant]))
    st.divider()
    st.write(f"**היום:** יום {HEB_DAYS[TODAY.weekday()]}, {TODAY:%d.%m.%Y}")
    st.caption(f"היומנים מכסים את {HORIZON_DAYS} הימים הקרובים (ראשון-חמישי, 09:00-17:00).")

# ---------- ראשי ----------
st.title("📅 מתאם פגישות")
st.caption("כתוב בקשה בשפה חופשית. הסוכן יציע מועד שמתאים ליומנים של כל המשתתפים, ויחכה לאישור שלך.")

with st.expander("📆 היומנים של הצוות", expanded=True):
    picked = st.date_input(
        "בחר תאריך כדי לראות את השבוע שלו",
        value=TODAY,
        min_value=TODAY,
        max_value=TODAY + timedelta(days=HORIZON_DAYS - 1),
        format="DD/MM/YYYY",
    )
    sunday = week_start(picked)
    st.caption(f"שבוע {sunday:%d.%m} – {sunday + timedelta(days=4):%d.%m.%Y}")
    st.dataframe(calendar_table(sunday), use_container_width=True)

request = st.text_input("הבקשה שלך", placeholder="לדוגמה: שעה עם דנה ויוסי ביום ראשון הבא אחרי 12:00")
if st.button("מצא מועד", type="primary", disabled=not request.strip()):
    start(request.strip(), variant)
    st.rerun()

result = ss.result
if result is not None:
    st.divider()

    if "__interrupt__" in result:
        p = result["__interrupt__"][0].value
        names = ", ".join(heb_name(x) for x in p["participants"])
        st.markdown(
            f'<div class="proposal">מועד מוצע:<br><b>{fmt_slot(p["proposal"], p["duration_minutes"])}</b>'
            f"<br>משתתפים: {names}</div>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("✅ אשר ושלח זימון", type="primary", use_container_width=True):
                resume({"action": "approve"}, "אושר")
                st.rerun()
            if st.button("✖ בטל", use_container_width=True):
                resume({"action": "cancel"}, "בוטל")
                st.rerun()
        with c2:
            feedback = st.text_input("לא מתאים? כתוב מה לשנות", placeholder="למשל: מאוחר יותר, אחרי 15:00")
            if st.button("🔄 הצע מועד אחר", disabled=not feedback.strip()):
                resume({"action": "reject", "feedback": feedback.strip()}, f"נדחה: {feedback.strip()}")
                st.rerun()
    else:
        status = result.get("status")
        if status == "scheduled":
            f = result["final"]
            names = ", ".join(heb_name(x) for x in f["participants"])
            st.success(f"הפגישה נקבעה: {fmt_slot(f['start'], result['constraints']['duration_minutes'])} | {names}")
        elif status == "no_slot":
            st.warning("לא נמצא מועד שמתאים לכל המשתתפים בטווח שביקשת.")
        elif status == "failed":
            st.error("הסוכן לא הצליח למצוא מועד תקין אחרי כל הניסיונות.")
        elif status == "cancelled":
            st.info("הבקשה בוטלה.")

    with st.expander("מה קרה מאחורי הקלעים"):
        for line in ss.log:
            st.write("•", line)
        st.write("**אילוצים שחולצו מהבקשה:**")
        st.json(result.get("constraints", {}))
        st.write(f"**ניסיונות הצעה:** {result.get('attempts', 0)}")
        if result.get("proposal"):
            st.write("**נימוק המודל:**", result["proposal"].get("reasoning", ""))