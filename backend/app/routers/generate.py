"""Text-to-shorts generation endpoint.

POST /generate  accepts a title + description + shorts_count and:

1. Creates a VideoProject with source_type=text.
2. Calls the text generation service to build a structured script.
3. Creates one Clip record per segment.
4. Schedules assemble_text_clip(clip.id) as a background job for each.
5. Returns the project + list of clip stubs (status=rendering) immediately
   so the frontend can start polling.

The client polls GET /videos/{id} until status=ready (all clips assembled)
or status=failed, then navigates to the clip list.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.clip import Clip, ClipCaptionStyle, ClipFraming, ClipStatus
from app.models.user import User
from app.models.video_project import (
    ClipLength,
    SourceType,
    VideoProject,
    VideoProjectStatus,
)
from app.schemas.clip import ClipResponse
from app.schemas.video import VideoProjectResponse
from app.services import task_queue
from app.services.text_clip_assembler import assemble_text_clip
from app.services.text_generation import generate_script

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Payload for POST /generate."""

    title: str = Field(min_length=1, max_length=255, description="Title of the video series")
    description: str = Field(
        min_length=10,
        max_length=4000,
        description="Description / outline of what the shorts should cover",
    )
    shorts_count: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of shorts to generate (1–10)",
    )
    caption_style: ClipCaptionStyle = ClipCaptionStyle.hormozi
    auto_broll: bool = True


class GenerateResponse(BaseModel):
    """Response envelope: the video project + initial clip stubs."""

    project: VideoProjectResponse
    clips: list[ClipResponse]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=GenerateResponse, status_code=202)
def generate_from_text(
    payload: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerateResponse:
    """Generate short-form videos from a title + description prompt.

    Accepted immediately (202): the heavy work (script generation + render)
    runs asynchronously.  Poll ``GET /videos/{project_id}`` until
    ``status == "ready"`` or ``status == "failed"``.
    """

    # 1. Create the VideoProject
    project = VideoProject(
        user_id=current_user.id,
        title=payload.title,
        source_type=SourceType.text,
        status=VideoProjectStatus.generating,
        description=payload.description,
        shorts_count=payload.shorts_count,
        target_clip_length=ClipLength.fast,
        framing_mode=ClipFraming.dynamic_blur,
        caption_style=payload.caption_style,
        auto_broll=payload.auto_broll,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    logger.info(
        "Starting text-to-shorts generation: project_id=%s title=%r shorts=%s",
        project.id,
        payload.title,
        payload.shorts_count,
    )

    # 2. Generate the script (synchronous; fast — either an API call or heuristics)
    try:
        segments = generate_script(payload.title, payload.description, payload.shorts_count)
    except Exception as exc:
        logger.exception("Script generation failed for project_id=%s", project.id)
        project.status = VideoProjectStatus.failed
        project.error_message = f"Script generation failed: {exc}"
        db.commit()
        raise

    # 3. Create Clip records for each segment
    clips: list[Clip] = []
    for seg in segments:
        # Store keywords in virality_reason as JSON so the assembler can read them
        kw_payload = json.dumps({"keywords": seg.keywords})

        clip = Clip(
            video_project_id=project.id,
            user_id=current_user.id,
            title=seg.title,
            start_time=0.0,
            end_time=seg.duration_seconds,
            order_index=seg.index,
            status=ClipStatus.rendering,
            caption_text=seg.narration,
            caption_style=payload.caption_style,
            framing_mode=ClipFraming.dynamic_blur,
            virality_reason=kw_payload,
        )
        db.add(clip)
        db.flush()  # get clip.id before scheduling
        clips.append(clip)

    db.commit()
    for clip in clips:
        db.refresh(clip)

    # 4. Schedule the assembler for each clip as a background job
    for clip in clips:
        task_queue.enqueue(background_tasks, assemble_text_clip, clip.id)

    logger.info(
        "Scheduled %d assembly jobs for project_id=%s",
        len(clips),
        project.id,
    )

    return GenerateResponse(
        project=VideoProjectResponse.model_validate(project),
        clips=[ClipResponse.model_validate(c) for c in clips],
    )
