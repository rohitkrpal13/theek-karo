"""Phase 13 community request/response schemas (API.md §10, PRD §8, §15)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReactionKind = Literal["like", "helpful", "confirm", "celebrate", "flag"]

FEED_TABS = ("for_you", "following", "trending", "latest", "geography")


class ReactionCreate(BaseModel):
    kind: ReactionKind


class CommentEditBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentRemoveBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ContentReportCreate(BaseModel):
    content_type: Literal["report", "comment", "institution", "post"]
    content_id: str
    reason: str = Field(min_length=1, max_length=64)
    details: str | None = Field(default=None, max_length=2000)


class ModerationResolveBody(BaseModel):
    action: Literal["dismiss", "remove"]
    reason: str | None = Field(default=None, max_length=500)


class DiscussionSummaryRequest(BaseModel):
    locale: str = Field(default="en", max_length=8)
