r"""גרף LangGraph למתאם פגישות.

parse_request -> propose_slot -> check_slot --(הפרות)--> propose_slot   [לולאה 1]
                                         \--(אין מועד)--> give_up
                                         \--(תקין)--> human_review (interrupt)
human_review --(approve)--> send_invite
             --(reject + הערה)--> propose_slot                         [לולאה 2]
             --(cancel)--> END
"""
import json
import os
import uuid
from datetime import date, timedelta
from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from .calendar_utils import free_slots, parse_dt, validate_slot
from .data import PARTICIPANTS, TODAY
from langgraph.types import Command, RetryPolicy, interrupt
HEB_DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]  # לפי weekday()

# ---------------------------------------------------------------- settings
VARIANTS = {
    # גרסת בסיס: ניסיון אחד, בלי טבלת תאריכים
    "baseline": {"max_attempts": 1, "date_table": False, "show_free_slots": False},
    # גרסה משופרת: לולאת תיקון עם משוב + טבלת תאריכים בפרומפט
    "improved": {"max_attempts": 3, "date_table": True, "show_free_slots": False},
    # אופציונלי: נותנים למודל את רשימת החלונות הפנויים
    "improved_plus": {"max_attempts": 3, "date_table": True, "show_free_slots": True},
}


def get_llm():
    return init_chat_model(os.getenv("MODEL", "openai:gpt-4o-mini"), temperature=0, max_retries=6)

# ---------------------------------------------------------------- schemas
class Constraints(BaseModel):
    participants: list[str] = Field(description="Participant keys, e.g. ['dana','yossi']")
    duration_minutes: int = Field(description="Meeting length in minutes")
    date_from: str = Field(description="First allowed date, YYYY-MM-DD")
    date_to: str = Field(description="Last allowed date, YYYY-MM-DD")
    earliest: str = Field(description="Earliest start time HH:MM (default 09:00)")
    latest: str = Field(description="Meeting must END by this time HH:MM (default 17:00)")


class Proposal(BaseModel):
    reasoning: str = Field(description="Short reasoning")
    feasible: bool = Field(description="False if no valid slot exists")
    start: str = Field(description="Start time YYYY-MM-DDTHH:MM, or empty string if not feasible")


class State(TypedDict, total=False):
    request: str
    calendars: dict
    settings: dict
    constraints: dict
    proposal: dict
    violations: list[str]
    attempts: int
    human_feedback: str
    status: str  # scheduled | no_slot | failed | cancelled
    final: dict


# ---------------------------------------------------------------- helpers
def date_table(today: str) -> str:
    d0 = date.fromisoformat(today)
    lines = [f"- {d0 + timedelta(days=i)}: יום {HEB_DAYS[(d0 + timedelta(days=i)).weekday()]}"
             for i in range(1, 9)]
    return (
        "Upcoming dates (use them, do not compute weekdays yourself):\n"
        + "\n".join(lines)
        + "\n'Next week' (השבוע הבא) means Sunday-Thursday of the coming week."
    )


# ---------------------------------------------------------------- nodes
def parse_request(state: State) -> dict:
    s = state["settings"]
    today = s.get("today", TODAY)
    prompt = f"""Extract meeting constraints from the user's request (in Hebrew).
    Today is {today}.
    {date_table(today) if s.get("date_table") else ""}
Known participants (key: Hebrew name): {json.dumps(PARTICIPANTS, ensure_ascii=False)}
Use participant KEYS only. If no hours are mentioned use earliest=09:00 latest=17:00.
"after X" sets earliest=X, "before X"/"until X" sets latest=X.

Request: {state["request"]}"""
    c = get_llm().with_structured_output(Constraints).invoke(prompt).model_dump()
    for k in ("earliest", "latest"):  # נרמול "9:00" -> "09:00"
        h, m = c[k].split(":")
        c[k] = f"{int(h):02d}:{int(m):02d}"
    return {"constraints": c, "attempts": 0, "violations": []}


def propose_slot(state: State) -> dict:
    s, c = state["settings"], state["constraints"]
    busy = {p: state["calendars"].get(p, []) for p in c["participants"]}
    parts = [
        "Find ONE meeting start time that satisfies all constraints.",
        "Working days are Sunday-Thursday only (no Friday/Saturday).",
        f"Constraints: {json.dumps(c, ensure_ascii=False)}",
        f"Busy times of participants: {json.dumps(busy)}",
    ]
    if s.get("show_free_slots"):
        slots = free_slots(c, state["calendars"])
        parts.append(f"Valid start times (pick one): {slots[:40]}")
    if state.get("violations"):
        parts.append(
            "Your previous proposal was INVALID because:\n- "
            + "\n- ".join(state["violations"])
            + "\nFix these problems."
        )
    if state.get("human_feedback"):
        parts.append(f"The user rejected the previous slot with this comment: {state['human_feedback']}")
    parts.append("If no valid time exists, set feasible=false and start=''.")
    p = get_llm().with_structured_output(Proposal).invoke("\n\n".join(parts))
    return {"proposal": p.model_dump(), "attempts": state.get("attempts", 0) + 1}


def check_slot(state: State) -> dict:
    p = state["proposal"]
    if not p["feasible"]:
        return {"violations": []}
    return {"violations": validate_slot(p["start"], state["constraints"], state["calendars"])}


def route_after_check(state: State) -> Literal["propose_slot", "give_up", "human_review"]:
    if state["violations"]:
        if state["attempts"] < state["settings"]["max_attempts"]:
            return "propose_slot"
        return "give_up"
    if not state["proposal"]["feasible"]:
        return "give_up"
    return "human_review"


def human_review(state: State) -> Command[Literal["send_invite", "propose_slot", "__end__"]]:
    if state["settings"].get("auto_approve"):
        return Command(goto="send_invite")

    decision = interrupt({
        "proposal": state["proposal"]["start"],
        "duration_minutes": state["constraints"]["duration_minutes"],
        "participants": state["constraints"]["participants"],
        "question": "approve / reject <הערה> / cancel",
    })
    action = decision.get("action")
    if action == "approve":
        return Command(goto="send_invite")
    if action == "reject":
        return Command(
            goto="propose_slot",
            update={"human_feedback": decision.get("feedback", ""), "attempts": 0, "violations": []},
        )
    return Command(goto=END, update={"status": "cancelled"})


def send_invite(state: State) -> dict:
    # כאן הייתה נשלחת הזמנה אמיתית (Google Calendar וכו'). כרגע - סימולציה.
    st = parse_dt(state["proposal"]["start"])
    end = st + timedelta(minutes=state["constraints"]["duration_minutes"])
    return {
        "status": "scheduled",
        "final": {
            "start": state["proposal"]["start"],
            "end": end.strftime("%Y-%m-%dT%H:%M"),
            "participants": state["constraints"]["participants"],
        },
    }


def give_up(state: State) -> dict:
    return {"status": "no_slot" if not state["proposal"]["feasible"] else "failed"}


# ---------------------------------------------------------------- build
def build_graph(checkpointer=None):
    g = StateGraph(State)
    retry = RetryPolicy(max_attempts=4, initial_interval=2.0, retry_on=Exception)  # חדש
    g.add_node("parse_request", parse_request, retry_policy=retry)                 # שונה
    g.add_node("propose_slot", propose_slot, retry_policy=retry)                   # שונה
    g.add_node("check_slot", check_slot)
    g.add_node("human_review", human_review)
    g.add_node("send_invite", send_invite)
    g.add_node("give_up", give_up)

    g.add_edge(START, "parse_request")
    g.add_edge("parse_request", "propose_slot")
    g.add_edge("propose_slot", "check_slot")
    g.add_conditional_edges("check_slot", route_after_check)
    g.add_edge("send_invite", END)
    g.add_edge("give_up", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def run_auto(request: str, calendars: dict, variant: str) -> dict:
    """הרצה ללא אדם (לצורך evaluation) - human_review מאשר אוטומטית."""
    graph = build_graph()
    settings = {**VARIANTS[variant], "auto_approve": True}
    cfg = {
        "configurable": {"thread_id": str(uuid.uuid4())},
        "run_name": f"scheduler-{variant}",
        "tags": [variant],
    }
    return graph.invoke({"request": request, "calendars": calendars, "settings": settings}, cfg)
