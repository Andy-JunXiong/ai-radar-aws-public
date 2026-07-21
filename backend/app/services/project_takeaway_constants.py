from __future__ import annotations

from typing import Literal


# Review outcomes capture the human review decision about a Project Takeaway
# candidate. Action completion is intentionally modeled as Action lifecycle,
# not as a sixth review outcome.
ReviewOutcome = Literal["confirmed", "rejected", "dismissed", "watch", "action"]
ActionState = Literal["open", "completed"]

REVIEW_OUTCOME_CONFIRMED: ReviewOutcome = "confirmed"
REVIEW_OUTCOME_REJECTED: ReviewOutcome = "rejected"
REVIEW_OUTCOME_DISMISSED: ReviewOutcome = "dismissed"
REVIEW_OUTCOME_WATCH: ReviewOutcome = "watch"
REVIEW_OUTCOME_ACTION: ReviewOutcome = "action"

REVIEW_OUTCOMES: frozenset[str] = frozenset(
    {
        REVIEW_OUTCOME_CONFIRMED,
        REVIEW_OUTCOME_REJECTED,
        REVIEW_OUTCOME_DISMISSED,
        REVIEW_OUTCOME_WATCH,
        REVIEW_OUTCOME_ACTION,
    }
)

ACTION_STATE_OPEN: ActionState = "open"
ACTION_STATE_COMPLETED: ActionState = "completed"

PROJECT_IMPROVEMENT_STATUS_NEW = "new"
PROJECT_IMPROVEMENT_STATUS_CANDIDATE = "candidate"
PROJECT_IMPROVEMENT_STATUS_REOPENED = "reopened"
PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED = "action_completed"

PROJECT_IMPROVEMENT_CLOSED_STATUSES: frozenset[str] = frozenset(
    {
        REVIEW_OUTCOME_CONFIRMED,
        REVIEW_OUTCOME_REJECTED,
        REVIEW_OUTCOME_DISMISSED,
        REVIEW_OUTCOME_WATCH,
        REVIEW_OUTCOME_ACTION,
        PROJECT_IMPROVEMENT_STATUS_ACTION_COMPLETED,
    }
)

EVENT_TYPE_BY_REVIEW_OUTCOME: dict[str, str] = {
    REVIEW_OUTCOME_CONFIRMED: "takeaway_accepted",
    REVIEW_OUTCOME_REJECTED: "takeaway_rejected",
    REVIEW_OUTCOME_DISMISSED: "takeaway_dismissed",
    REVIEW_OUTCOME_WATCH: "watch_item_created",
    REVIEW_OUTCOME_ACTION: "action_item_created",
}

EVENT_TYPE_BY_ACTION_STATE: dict[str, str] = {
    ACTION_STATE_COMPLETED: "action_item_completed",
}

PROJECT_FOLLOWUP_EVENT_WATCH_REVIEWED = "watch_item_reviewed"


def normalize_project_takeaway_status(value: object) -> str:
    return str(value or "").strip().lower()


def is_review_outcome(value: object) -> bool:
    return normalize_project_takeaway_status(value) in REVIEW_OUTCOMES


def is_closed_project_improvement_status(value: object) -> bool:
    return normalize_project_takeaway_status(value) in PROJECT_IMPROVEMENT_CLOSED_STATUSES
