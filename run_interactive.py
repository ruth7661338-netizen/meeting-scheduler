"""הרצה אינטראקטיבית עם human-in-the-loop.

    python run_interactive.py "שעה עם דנה ויוסי ביום ראשון"
    python run_interactive.py --draw      # מדפיס את הגרף כ-Mermaid
"""

import truststore
truststore.inject_into_ssl()
import argparse
import uuid

from dotenv import load_dotenv
from langgraph.types import Command

from scheduler.data import CALENDARS
from scheduler.graph import VARIANTS, build_graph

load_dotenv()


def ask_human(payload: dict) -> dict:
    print("\n--- מועד מוצע ---")
    print(f"התחלה: {payload['proposal']}  |  משך: {payload['duration_minutes']} דק'")
    print(f"משתתפים: {', '.join(payload['participants'])}")
    ans = input("approve / reject <הערה> / cancel > ").strip()
    if ans.startswith("approve") or ans in ("a", "כן"):
        return {"action": "approve"}
    if ans.startswith("reject"):
        return {"action": "reject", "feedback": ans[len("reject"):].strip()}
    return {"action": "cancel"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="?")
    ap.add_argument("--variant", choices=list(VARIANTS), default="improved")
    ap.add_argument("--draw", action="store_true")
    args = ap.parse_args()

    graph = build_graph()
    if args.draw:
        print(graph.get_graph().draw_mermaid())
        return

    request = args.request or input("בקשה: ")
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}, "run_name": "scheduler-interactive"}
    state = graph.invoke(
        {"request": request, "calendars": CALENDARS, "settings": {**VARIANTS[args.variant], "auto_approve": False}},
        cfg,
    )
    while "__interrupt__" in state:
        decision = ask_human(state["__interrupt__"][0].value)
        state = graph.invoke(Command(resume=decision), cfg)

    print("\n=== תוצאה ===")
    print("סטטוס:", state.get("status"))
    if state.get("final"):
        f = state["final"]
        print(f"נקבעה פגישה {f['start']} - {f['end'][-5:]} עם {', '.join(f['participants'])}")
    print("ניסיונות:", state.get("attempts"))


if __name__ == "__main__":
    main()
