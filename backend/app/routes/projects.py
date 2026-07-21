from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.services.admin_guard import require_admin_auth
from app.services import final_takeaway_artifact_service as final_takeaway_artifacts

from app.project_registry import (
    delete_project,
    get_next_project_id,
    get_project,
    list_active_projects,
    list_projects,
    update_project_repo,
    upsert_project,
)
from app.services.model_attribution_analytics_service import summarize_model_attribution
from app.services.project_intelligence_service import (
    add_signal_to_project_improvements,
    close_project_takeaway_candidate,
    complete_project_action_item,
    confirm_project_improvement,
    generate_project_improvement_updated_documents,
    generate_project_improvement_reviews,
    get_project_github_context_with_cache,
    load_project_improvements,
    reopen_project_improvement,
    refresh_project_improvement_analysis,
    submit_project_improvement_to_github,
    override_action_project_takeaway_candidate,
    override_confirm_project_improvement,
    review_project_watch_item,
    save_reasoning_counter_check_draft,
)
from app.services.project_calibration_event_service import (
    backfill_project_calibration_events_from_review_records,
    list_project_calibration_events,
    summarize_project_calibration_events,
)
from app.services.project_learning_profile_service import build_project_learning_profile
from app.services.project_review_record_service import (
    build_project_review_record_detail,
    list_project_review_records,
    summarize_project_review_records,
)
from app.services.project_repo_snapshot_service import (
    get_or_refresh_project_repo_snapshot,
    load_project_repo_snapshot,
    maybe_refresh_project_repo_snapshot_after_save,
)
from app.services.rejected_learning_buffer_service import build_rejected_learning_buffer
from app.services.project_takeaway_constants import (
    PROJECT_IMPROVEMENT_CLOSED_STATUSES,
    PROJECT_IMPROVEMENT_STATUS_CANDIDATE,
    REVIEW_OUTCOME_ACTION,
    REVIEW_OUTCOME_CONFIRMED,
    REVIEW_OUTCOME_DISMISSED,
    REVIEW_OUTCOME_REJECTED,
    REVIEW_OUTCOME_WATCH,
)
from app.services.project_takeaway_candidate_policy import (
    build_project_takeaway_candidate_input,
)
from app.services.project_trajectory_event_service import build_trajectory_events_response
from app.services.reasoning_counter_check_service import generate_reasoning_counter_check
from app.services.s3_reader import get_signal_by_id


router = APIRouter()


def _is_v1_model_provenance(value: object) -> bool:
    return isinstance(value, dict) and value.get("provenance_schema_version") == 1


def _first_v1_model_provenance(*candidates: object) -> dict | None:
    for candidate in candidates:
        if _is_v1_model_provenance(candidate):
            return candidate
    return None


def _attach_signal_model_provenance(
    *,
    signal_id: str,
    verification: dict,
) -> dict:
    if _is_v1_model_provenance(verification.get("produced_by_model")):
        return verification

    try:
        signal = get_signal_by_id(signal_id, force_refresh=True)
    except Exception:
        return verification
    if not isinstance(signal, dict):
        return verification

    signal_verification = signal.get("verification") if isinstance(signal.get("verification"), dict) else {}
    policy_metadata = signal.get("policy_metadata") if isinstance(signal.get("policy_metadata"), dict) else {}
    policy_verification = (
        policy_metadata.get("verification")
        if isinstance(policy_metadata.get("verification"), dict)
        else {}
    )
    verified_insight = (
        signal_verification.get("verified_insight")
        if isinstance(signal_verification.get("verified_insight"), dict)
        else {}
    )
    policy_verified_insight = (
        policy_verification.get("verified_insight")
        if isinstance(policy_verification.get("verified_insight"), dict)
        else {}
    )
    produced_by_model = _first_v1_model_provenance(
        signal.get("produced_by_model"),
        signal_verification.get("produced_by_model"),
        verified_insight.get("produced_by_model"),
        policy_verification.get("produced_by_model"),
        policy_verified_insight.get("produced_by_model"),
    )
    if not produced_by_model:
        return verification

    enriched = {**verification, "produced_by_model": produced_by_model}
    existing_verified_insight = enriched.get("verified_insight")
    if isinstance(existing_verified_insight, dict) and not _is_v1_model_provenance(
        existing_verified_insight.get("produced_by_model")
    ):
        enriched["verified_insight"] = {
            **existing_verified_insight,
            "produced_by_model": produced_by_model,
        }
    return enriched


def _load_model_attribution_candidates(project_id: str | None = None) -> list[dict[str, object]]:
    target_project_id = str(project_id or "").strip()
    candidates: list[dict[str, object]] = []
    for project in list_projects():
        current_project_id = str(project.get("project_id") or "").strip()
        if not current_project_id or (target_project_id and current_project_id != target_project_id):
            continue

        payload = load_project_improvements(current_project_id)
        items = payload.get("items", [])
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            candidates.append(
                {
                    **item,
                    "project_id": item.get("project_id") or current_project_id,
                    "project_name": item.get("project_name") or project.get("name") or current_project_id,
                }
            )
    return candidates


class ProjectRepoUpdateRequest(BaseModel):
    repo: str


class ProjectUpsertRequest(BaseModel):
    project_id: str = ""
    name: str
    enabled: bool = True
    status: str = "planning"
    description: str = ""
    repo: str = ""
    current_state: str = ""
    roadmap: str = ""
    topics: list[str] = []


class ProjectTakeawayCandidateRequest(BaseModel):
    signal_id: str
    signal_title: str = ""
    signal_summary: str = ""
    why_it_matters: str = ""
    relevance_to_projects: object = ""
    synthesized_insight: str = ""
    final_reflection: str = ""
    subscription_project_links: list[dict] = []
    verification_metadata: dict = {}


class ConfirmedFinalTakeawayCandidateRequest(ProjectTakeawayCandidateRequest):
    final_takeaway_id: str


class ProjectTakeawayReviewActionRequest(BaseModel):
    reason: str = ""
    review_date: str = ""
    success_criteria: str = ""
    watch_status: str = ""
    expected_outcome: str = ""
    due_date: str = ""
    followup_result: str = ""
    evidence_update: str = ""
    next_review_date: str = ""


class ReasoningCounterCheckRequest(BaseModel):
    project_id: str = ""
    project_name: str = ""
    signal_id: str = ""
    signal_title: str = ""
    signal_summary: str = ""
    takeaway: str = ""
    why_it_matters: str = ""
    fit_reason: str = ""
    benefits: str = ""
    final_reflection: str = ""
    claim_support: str = ""
    warrant: str = ""
    counter_check_prompt: str = ""
    boundary: str = ""
    source_model_provenance: dict = {}
    verification_metadata: dict = {}
    action_eligibility: dict = {}


def require_review_fields(fields: dict[str, str]) -> None:
    missing = [label for label, value in fields.items() if not normalize_text(value).strip()]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Required review detail missing: {', '.join(missing)}.",
        )


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def parse_project_takeaway(value: object) -> dict[str, str]:
    if value is None:
        return {}

    if isinstance(value, dict):
        result: dict[str, str] = {}
        for key, raw in value.items():
            text = normalize_text(raw).strip()
            if text:
                result[str(key)] = text
        return result

    text = normalize_text(value).strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {
                str(key): normalize_text(raw).strip()
                for key, raw in parsed.items()
                if normalize_text(raw).strip()
            }
    except Exception:
        pass

    return {"General": text}


def _create_project_takeaway_candidate_response(
    payload: ProjectTakeawayCandidateRequest,
    *,
    verification: dict,
    message: str = "project takeaway candidate created successfully",
) -> dict[str, object]:
    verification = _attach_signal_model_provenance(
        signal_id=payload.signal_id,
        verification=verification,
    )
    try:
        candidate_input = build_project_takeaway_candidate_input(verification)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        written = add_signal_to_project_improvements(
            signal_id=payload.signal_id,
            signal_title=payload.signal_title,
            signal_summary=payload.signal_summary,
            why_it_matters=payload.why_it_matters,
            relevance_to_projects=payload.relevance_to_projects,
            synthesized_insight=payload.synthesized_insight,
            final_reflection=payload.final_reflection,
            subscription_project_links=payload.subscription_project_links or [],
            verification_metadata=candidate_input.verification_metadata,
            candidate_source=candidate_input.candidate_source,
            status="candidate",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "items": written,
        "created_count": len(written),
        "candidate_source": candidate_input.candidate_source,
        "message": message,
    }


@router.get("/projects")
def get_projects():
    return {
        "items": list_projects(),
        "message": "projects loaded successfully",
    }


@router.get("/projects/next-id")
def get_projects_next_id():
    return {
        "project_id": get_next_project_id(),
        "message": "next project id generated successfully",
    }


@router.post("/projects", dependencies=[Depends(require_admin_auth)])
def save_project(payload: ProjectUpsertRequest):
    project_id = (payload.project_id or "").strip() or get_next_project_id()
    previous_project = get_project(project_id)
    previous_repo = str((previous_project or {}).get("repo") or "")
    item = upsert_project(
        project_id,
        {
            "name": payload.name,
            "enabled": payload.enabled,
            "status": payload.status,
            "description": payload.description,
            "repo": payload.repo,
            "current_state": payload.current_state,
            "roadmap": payload.roadmap,
            "topics": payload.topics,
            "source": "manual",
        },
    )
    snapshot = None
    try:
        snapshot = maybe_refresh_project_repo_snapshot_after_save(item, previous_repo=previous_repo)
    except Exception as exc:
        snapshot = {
            "status": "failed",
            "repo": item.get("repo") or "",
            "message": f"Project saved, but repo snapshot failed: {exc}",
        }
    return {
        "item": item,
        "repo_snapshot": snapshot,
        "message": "project saved successfully",
    }


@router.delete("/projects/{project_id}", dependencies=[Depends(require_admin_auth)])
def remove_project(project_id: str):
    try:
        item = delete_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "item": item,
        "message": "project deleted successfully",
    }


@router.get("/projects/workspace-view")
def get_projects_workspace_view():
    items: list[dict[str, object]] = []
    for project in list_active_projects():
        improvements_payload = load_project_improvements(str(project.get("project_id") or ""))
        improvements = improvements_payload.get("items", [])
        if not isinstance(improvements, list):
            improvements = []
        items.append(
            {
                "project": project,
                "improvement_count": len(improvements),
                "confirmed_count": len(
                    [
                        row
                        for row in improvements
                        if isinstance(row, dict) and str(row.get("status") or "").strip().lower() == REVIEW_OUTCOME_CONFIRMED
                    ]
                ),
                "latest_improvement": improvements[0] if improvements else None,
            }
        )

    return {
        "items": items,
        "message": "workspace project view loaded successfully",
    }


@router.get("/projects/takeaway-candidates", dependencies=[Depends(require_admin_auth)])
def list_project_takeaway_candidates(
    include_confirmed: bool = False,
    include_closed: bool = False,
):
    candidates: list[dict[str, object]] = []
    for project in list_active_projects():
        project_id = str(project.get("project_id") or "").strip()
        if not project_id:
            continue

        payload = load_project_improvements(project_id)
        items = payload.get("items", [])
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip().lower()
            if status == REVIEW_OUTCOME_CONFIRMED and not include_confirmed:
                continue
            if status not in {PROJECT_IMPROVEMENT_STATUS_CANDIDATE, REVIEW_OUTCOME_CONFIRMED}:
                if not include_closed or status not in PROJECT_IMPROVEMENT_CLOSED_STATUSES:
                    continue
            if status != PROJECT_IMPROVEMENT_STATUS_CANDIDATE and status != REVIEW_OUTCOME_CONFIRMED and not include_closed:
                continue
            candidates.append(
                {
                    **item,
                    "project": project,
                    "project_id": project_id,
                    "project_name": project.get("name") or item.get("project_name") or project_id,
                    "project_updated_at": payload.get("updated_at"),
                }
            )

    candidates.sort(key=lambda item: str(item.get("saved_at") or ""), reverse=True)
    return {
        "items": candidates,
        "message": "project takeaway candidates loaded successfully",
    }


@router.post("/projects/takeaway-candidates", dependencies=[Depends(require_admin_auth)])
def create_project_takeaway_candidate(payload: ProjectTakeawayCandidateRequest):
    return _create_project_takeaway_candidate_response(
        payload,
        verification=payload.verification_metadata or {},
    )


@router.post("/projects/takeaway-candidates/from-final-takeaway", dependencies=[Depends(require_admin_auth)])
def create_project_takeaway_candidate_from_final_takeaway(payload: ConfirmedFinalTakeawayCandidateRequest):
    final_takeaway_id = normalize_text(payload.final_takeaway_id).strip()
    if not final_takeaway_id:
        raise HTTPException(status_code=400, detail="final_takeaway_id is required.")

    final_takeaway = final_takeaway_artifacts.get_final_takeaway(final_takeaway_id)
    if not final_takeaway:
        raise HTTPException(status_code=404, detail="final takeaway artifact not found.")
    if normalize_text(final_takeaway.get("status")).strip().lower() != "confirmed":
        raise HTTPException(status_code=400, detail="final takeaway artifact is not confirmed.")

    payload_signal_id = normalize_text(payload.signal_id).strip()
    artifact_signal_id = normalize_text(final_takeaway.get("signal_id")).strip()
    if artifact_signal_id and artifact_signal_id != payload_signal_id:
        raise HTTPException(status_code=400, detail="final takeaway artifact signal_id does not match payload.")
    if not payload_signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required.")

    verification = {
        **(payload.verification_metadata or {}),
        "confirmed_final_takeaway": True,
        "candidate_requested_from": "confirmed_final_takeaway",
        "verification_status": (payload.verification_metadata or {}).get("verification_status")
        or "confirmed_final_takeaway_review_candidate",
        "final_takeaway_id": normalize_text(final_takeaway.get("final_takeaway_id")) or final_takeaway_id,
        "final_takeaway_status": normalize_text(final_takeaway.get("status")),
        "final_takeaway_confirmed_at": normalize_text(final_takeaway.get("confirmed_at")),
        "review_bundle_snapshot_id": normalize_text(final_takeaway.get("review_bundle_snapshot_id")),
        "review_bundle_content_hash": normalize_text(final_takeaway.get("review_bundle_content_hash")),
        "source_completion_note_available": bool(normalize_text(final_takeaway.get("source_completion_note"))),
    }

    confirmed_text = normalize_text(final_takeaway.get("confirmed_text"))
    if confirmed_text and not normalize_text(payload.synthesized_insight):
        payload.synthesized_insight = confirmed_text
    if confirmed_text and not normalize_text(payload.final_reflection):
        payload.final_reflection = confirmed_text

    response = _create_project_takeaway_candidate_response(
        payload,
        verification=verification,
        message="confirmed final takeaway candidate created successfully",
    )
    response["final_takeaway_id"] = verification["final_takeaway_id"]
    return response


@router.post("/projects/reasoning-counter-check", dependencies=[Depends(require_admin_auth)])
def create_reasoning_counter_check_draft(payload: ReasoningCounterCheckRequest):
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        draft = generate_reasoning_counter_check(payload_data)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to generate counter-check draft: {exc}",
        ) from exc

    persisted_item: dict[str, object] | None = None
    if normalize_text(payload.project_id).strip() and normalize_text(payload.signal_id).strip():
        try:
            persisted_item = save_reasoning_counter_check_draft(
                payload.project_id,
                payload.signal_id,
                draft,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "draft": draft,
        "item": persisted_item,
        "persisted": persisted_item is not None,
        "message": "counter-check draft generated and persisted as reviewer advisory only",
    }


@router.get("/projects/review-records", dependencies=[Depends(require_admin_auth)])
def get_project_review_records(
    project_id: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
):
    items = list_project_review_records(
        project_id=project_id,
        signal_id=signal_id,
        outcome=outcome,
    )
    return {
        "items": items,
        "count": len(items),
        "message": "project review records loaded successfully",
    }


@router.get("/projects/review-records/summary", dependencies=[Depends(require_admin_auth)])
def get_project_review_records_summary(
    project_id: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
):
    summary = summarize_project_review_records(
        project_id=project_id,
        signal_id=signal_id,
    )
    return {
        "summary": summary,
        "message": "project review record summary loaded successfully",
    }


@router.get("/projects/review-records/{record_id}", dependencies=[Depends(require_admin_auth)])
def get_project_review_record_detail(record_id: str):
    detail = build_project_review_record_detail(record_id)
    if not detail:
        raise HTTPException(status_code=404, detail="project review record not found")
    return detail


@router.get("/projects/rejected-learning-buffer", dependencies=[Depends(require_admin_auth)])
def get_project_rejected_learning_buffer(
    project_id: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
):
    buffer = build_rejected_learning_buffer(
        project_id=project_id,
        signal_id=signal_id,
        limit=limit,
    )
    return {
        **buffer,
        "message": "project rejected learning buffer loaded successfully",
    }


@router.get("/projects/calibration-events", dependencies=[Depends(require_admin_auth)])
def get_project_calibration_events(
    project_id: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
):
    items = list_project_calibration_events(
        project_id=project_id,
        signal_id=signal_id,
        event_type=event_type,
    )
    return {
        "items": items,
        "count": len(items),
        "message": "project calibration events loaded successfully",
    }


@router.get("/projects/calibration-events/summary", dependencies=[Depends(require_admin_auth)])
def get_project_calibration_events_summary(
    project_id: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
):
    summary = summarize_project_calibration_events(
        project_id=project_id,
        signal_id=signal_id,
    )
    return {
        "summary": summary,
        "message": "project calibration event summary loaded successfully",
    }


@router.get("/projects/learning-profile", dependencies=[Depends(require_admin_auth)])
def get_project_learning_profile(
    project_id: str | None = Query(default=None),
    recent_limit: int = Query(default=5, ge=1, le=20),
):
    profile = build_project_learning_profile(
        project_id=project_id,
        recent_limit=recent_limit,
    )
    return {
        **profile,
        "message": "project learning profile loaded successfully",
    }


@router.get("/projects/model-attribution/summary", dependencies=[Depends(require_admin_auth)])
def get_project_model_attribution_summary(
    project_id: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
):
    candidates = _load_model_attribution_candidates(project_id=project_id)
    if signal_id:
        candidates = [item for item in candidates if str(item.get("signal_id") or "").strip() == signal_id]

    summary = summarize_model_attribution(
        candidates=candidates,
        review_records=list_project_review_records(project_id=project_id, signal_id=signal_id),
        calibration_events=list_project_calibration_events(project_id=project_id, signal_id=signal_id),
        scope={
            "days": days,
            "project_id": project_id or "all",
            "signal_id": signal_id or "all",
            "record_families": ["candidate", "review_record", "calibration_event"],
        },
    )
    return {
        "summary": summary,
        "message": "project model attribution summary loaded successfully",
    }


@router.get("/projects/trajectory-events", dependencies=[Depends(require_admin_auth)])
def get_project_trajectory_events(
    project_id: str | None = Query(default=None),
    signal_id: str | None = Query(default=None),
    event_kind: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    trajectory_signal_type: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
):
    review_records = list_project_review_records(project_id=project_id, signal_id=signal_id)
    calibration_events = list_project_calibration_events(project_id=project_id, signal_id=signal_id)
    result = build_trajectory_events_response(
        review_records,
        calibration_events,
        event_kind=event_kind,
        risk_level=risk_level,
        trajectory_signal_type=trajectory_signal_type,
        source_type=source_type,
    )
    return {
        **result,
        "message": "project trajectory events loaded successfully",
    }


@router.post("/projects/calibration-events/backfill", dependencies=[Depends(require_admin_auth)])
def backfill_project_calibration_events(project_id: str | None = Query(default=None), signal_id: str | None = Query(default=None)):
    records = list_project_review_records(project_id=project_id, signal_id=signal_id)
    result = backfill_project_calibration_events_from_review_records(records)
    return {
        **result,
        "message": "project calibration events backfilled successfully",
    }


@router.get("/projects/{project_id}")
def get_project_detail(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    return {
        "item": project,
        "message": "project loaded successfully",
    }


@router.post("/projects/{project_id}/repo", dependencies=[Depends(require_admin_auth)])
def save_project_repo(project_id: str, payload: ProjectRepoUpdateRequest):
    previous_project = get_project(project_id)
    previous_repo = str((previous_project or {}).get("repo") or "")
    try:
        project = update_project_repo(project_id, payload.repo)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = None
    try:
        snapshot = maybe_refresh_project_repo_snapshot_after_save(project, previous_repo=previous_repo)
    except Exception as exc:
        snapshot = {
            "status": "failed",
            "repo": project.get("repo") or "",
            "message": f"Project repo updated, but repo snapshot failed: {exc}",
        }

    return {
        "item": project,
        "repo_snapshot": snapshot,
        "message": "project repo updated successfully",
    }


@router.get("/projects/{project_id}/repo-snapshot")
def get_project_repo_snapshot(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    snapshot = load_project_repo_snapshot(project_id)
    if not snapshot:
        snapshot = {
            "schema_version": 1,
            "project_id": project_id,
            "status": "missing",
            "repo": project.get("repo") or "",
            "message": "No repo snapshot has been generated yet. Save the project or refresh the light snapshot.",
        }
    return {
        "project": project,
        "repo_snapshot": snapshot,
    }


@router.post("/projects/{project_id}/repo-snapshot/refresh", dependencies=[Depends(require_admin_auth)])
def refresh_project_repo_snapshot(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    snapshot = get_or_refresh_project_repo_snapshot(project, force_refresh=True)
    return {
        "project": project,
        "repo_snapshot": snapshot,
        "message": "project repo snapshot refreshed successfully",
    }


@router.get("/projects/{project_id}/github-context")
def get_project_github_context(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    cache_payload = get_project_github_context_with_cache(project, force_refresh=False)
    return {
        "project": project,
        "github": cache_payload.get("github"),
        "cache": {
            "repo": cache_payload.get("repo"),
            "fetched_at": cache_payload.get("fetched_at"),
        },
    }


@router.post("/projects/{project_id}/github-context/refresh", dependencies=[Depends(require_admin_auth)])
def refresh_project_github_context(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    cache_payload = get_project_github_context_with_cache(project, force_refresh=True)
    return {
        "project": project,
        "github": cache_payload.get("github"),
        "cache": {
            "repo": cache_payload.get("repo"),
            "fetched_at": cache_payload.get("fetched_at"),
        },
        "message": "project github context refreshed successfully",
    }


@router.get("/projects/{project_id}/improvements")
def get_project_improvements(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    payload = load_project_improvements(project_id)
    return {
        "project": project,
        "items": payload.get("items", []),
        "updated_at": payload.get("updated_at"),
        "message": "project improvements loaded successfully",
    }


@router.get("/projects/{project_id}/improvements/{signal_id}")
def get_project_improvement_detail(project_id: str, signal_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    payload = load_project_improvements(project_id)
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    for item in items:
        if isinstance(item, dict) and str(item.get("signal_id") or "").strip() == signal_id:
            return {
                "project": project,
                "item": item,
                "updated_at": payload.get("updated_at"),
                "message": "project improvement loaded successfully",
            }

    raise HTTPException(status_code=404, detail="Project improvement not found.")


@router.post("/projects/{project_id}/improvements/{signal_id}/refresh-fit", dependencies=[Depends(require_admin_auth)])
def refresh_improvement_fit(project_id: str, signal_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = refresh_project_improvement_analysis(project_id, signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project improvement fit analysis refreshed successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/draft-reviews", dependencies=[Depends(require_admin_auth)])
def generate_improvement_draft_reviews(project_id: str, signal_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = generate_project_improvement_reviews(project_id, signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project improvement draft reviews generated successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/generate-documents", dependencies=[Depends(require_admin_auth)])
def generate_improvement_updated_documents(project_id: str, signal_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = generate_project_improvement_updated_documents(project_id, signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project improvement documents generated successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/confirm", dependencies=[Depends(require_admin_auth)])
def confirm_improvement(project_id: str, signal_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = confirm_project_improvement(project_id, signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project improvement confirmed successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/override-confirm", dependencies=[Depends(require_admin_auth)])
def override_confirm_improvement(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = override_confirm_project_improvement(
            project_id,
            signal_id,
            reason=payload.reason,
            expected_outcome=payload.expected_outcome,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project improvement override-confirmed successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/reject", dependencies=[Depends(require_admin_auth)])
def reject_project_takeaway_candidate(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = close_project_takeaway_candidate(
            project_id,
            signal_id,
            status=REVIEW_OUTCOME_REJECTED,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project takeaway candidate rejected successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/dismiss", dependencies=[Depends(require_admin_auth)])
def dismiss_project_takeaway_candidate(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = close_project_takeaway_candidate(
            project_id,
            signal_id,
            status=REVIEW_OUTCOME_DISMISSED,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project takeaway candidate dismissed successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/watch", dependencies=[Depends(require_admin_auth)])
def watch_project_takeaway_candidate(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    require_review_fields(
        {
            "watch review date": payload.review_date,
            "watch status": payload.watch_status,
            "watch success criteria": payload.success_criteria,
        }
    )

    try:
        item = close_project_takeaway_candidate(
            project_id,
            signal_id,
            status=REVIEW_OUTCOME_WATCH,
            reason=payload.reason,
            review_date=payload.review_date,
            success_criteria=payload.success_criteria,
            watch_status=payload.watch_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project takeaway candidate added to watch successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/action", dependencies=[Depends(require_admin_auth)])
def action_project_takeaway_candidate(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    require_review_fields(
        {
            "action due date": payload.due_date,
            "action review date": payload.review_date,
            "expected outcome": payload.expected_outcome,
        }
    )

    try:
        item = close_project_takeaway_candidate(
            project_id,
            signal_id,
            status=REVIEW_OUTCOME_ACTION,
            reason=payload.reason,
            expected_outcome=payload.expected_outcome,
            due_date=payload.due_date,
            review_date=payload.review_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project takeaway candidate added to action successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/override-action", dependencies=[Depends(require_admin_auth)])
def override_action_project_takeaway_candidate_route(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = override_action_project_takeaway_candidate(
            project_id,
            signal_id,
            reason=payload.reason,
            expected_outcome=payload.expected_outcome,
            due_date=payload.due_date,
            review_date=payload.review_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project takeaway candidate override-action created successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/complete-action", dependencies=[Depends(require_admin_auth)])
def complete_project_takeaway_action(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = complete_project_action_item(
            project_id,
            signal_id,
            note=payload.reason,
            followup_result=payload.followup_result,
            evidence_update=payload.evidence_update,
            next_review_date=payload.next_review_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project takeaway action completed successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/review-watch", dependencies=[Depends(require_admin_auth)])
def review_project_takeaway_watch(project_id: str, signal_id: str, payload: ProjectTakeawayReviewActionRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = review_project_watch_item(
            project_id,
            signal_id,
            followup_result=payload.followup_result,
            note=payload.reason,
            evidence_update=payload.evidence_update,
            next_review_date=payload.next_review_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project takeaway watch item reviewed successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/reopen", dependencies=[Depends(require_admin_auth)])
def reopen_improvement(project_id: str, signal_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = reopen_project_improvement(project_id, signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project improvement reopened successfully",
    }


@router.post("/projects/{project_id}/improvements/{signal_id}/submit-github", dependencies=[Depends(require_admin_auth)])
def submit_improvement_to_github(project_id: str, signal_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        item = submit_project_improvement_to_github(project_id, signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "project": project,
        "item": item,
        "message": "project improvement submitted to GitHub successfully",
    }
