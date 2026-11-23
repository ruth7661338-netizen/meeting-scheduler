"""הרצת ניסוי ב-LangSmith.

    python run_experiment.py --variant baseline
    python run_experiment.py --variant improved
"""
import truststore
truststore.inject_into_ssl()
import argparse

from dotenv import load_dotenv
from langsmith import Client

from scheduler.calendar_utils import validate_slot
from scheduler.graph import VARIANTS, run_auto

load_dotenv()
DATASET_NAME = "meeting-scheduler"


# ---------------------------------------------------------------- evaluators
def slot_correct(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """המדד הראשי: מועד תקין לפי האילוצים הנכונים (לא לפי מה שהמודל הבין)."""
    gold = reference_outputs["constraints"]
    if not reference_outputs["feasible"]:
        ok = outputs["status"] == "no_slot"
        comment = "expected no_slot" if ok else f"expected no_slot, got {outputs['status']} {outputs['start']}"
    elif outputs["status"] != "scheduled":
        ok, comment = False, f"a slot exists but status={outputs['status']}"
    else:
        v = validate_slot(outputs["start"], gold, inputs["calendars"])
        ok, comment = not v, "; ".join(v) or "valid"
    return {"key": "slot_correct", "score": int(ok), "comment": comment}


def parse_correct(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """אחוז השדות שחולצו נכון מהבקשה."""
    gold, got = reference_outputs["constraints"], outputs.get("constraints") or {}
    fields = ["duration_minutes", "date_from", "date_to", "earliest", "latest"]
    hits = [str(got.get(f)) == str(gold[f]) for f in fields]
    hits.append(set(got.get("participants", [])) == set(gold["participants"]))
    wrong = [f for f, h in zip(fields + ["participants"], hits) if not h]
    return {"key": "parse_correct", "score": sum(hits) / len(hits),
            "comment": "wrong: " + ", ".join(wrong) if wrong else "all correct"}


def attempts(outputs: dict) -> dict:
    return {"key": "attempts", "score": outputs["attempts"]}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=list(VARIANTS), default="baseline")
    args = ap.parse_args()

    def target(inputs: dict) -> dict:
        s = run_auto(inputs["request"], inputs["calendars"], args.variant)
        return {
            "status": s.get("status"),
            "start": (s.get("final") or {}).get("start"),
            "constraints": s.get("constraints"),
            "attempts": s.get("attempts", 0),
        }

    Client().evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[slot_correct, parse_correct, attempts],
        experiment_prefix=args.variant,
        metadata={"variant": args.variant, **VARIANTS[args.variant]},
        max_concurrency=1,
    )


if __name__ == "__main__":
    main()
