"""SQLAlchemy models — mirrors schema.sql. Channel-generalized. (Substrate.)

Same tables serve every channel: a `channel_accounts` row carries which channel it is and
channel-specific auth in JSONB; `content_pieces` carry the owning app + channel.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

UID = UUID(as_uuid=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(Text, server_default="founder")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    channel: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class ChannelAccount(Base):
    __tablename__ = "channel_accounts"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(Text, server_default="instagram")
    handle: Mapped[str] = mapped_column(Text)
    ig_user_id: Mapped[str | None] = mapped_column(Text)
    compliance_mode: Mapped[str] = mapped_column(Text, server_default="official")
    autonomous_optin: Mapped[bool] = mapped_column(Boolean, server_default="false")
    auth: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    consent_tiers: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    auto_post_threshold: Mapped[int] = mapped_column(Integer, server_default="30")
    post_count: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentPiece(Base):
    __tablename__ = "content_pieces"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str | None] = mapped_column(UID, ForeignKey("channel_accounts.id", ondelete="CASCADE"))
    app: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text, server_default="instagram")
    source: Mapped[str] = mapped_column(Text, server_default="watched_folder")
    goal_id: Mapped[str | None] = mapped_column(UID)
    playbook_key: Mapped[str | None] = mapped_column(Text)
    lens_keys: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    transcript: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="new")
    meta: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentDraft(Base):
    __tablename__ = "content_drafts"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    content_piece_id: Mapped[str] = mapped_column(UID, ForeignKey("content_pieces.id", ondelete="CASCADE"))
    variant_key: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    hooks: Mapped[list] = mapped_column(JSONB, server_default="[]")
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    cta: Mapped[str | None] = mapped_column(Text)
    lens_key: Mapped[str | None] = mapped_column(Text)
    curator_rank: Mapped[int | None] = mapped_column(Integer)
    curator_reason: Mapped[str | None] = mapped_column(Text)
    chosen: Mapped[bool] = mapped_column(Boolean, server_default="false")
    suggestion_id: Mapped[str | None] = mapped_column(UID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    content_piece_id: Mapped[str | None] = mapped_column(UID, ForeignKey("content_pieces.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(Text)
    duration_s: Mapped[float | None] = mapped_column(Numeric)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Playbook(Base):
    __tablename__ = "playbooks"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Lens(Base):
    __tablename__ = "lenses"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class ContentGoal(Base):
    __tablename__ = "content_goals"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str | None] = mapped_column(UID, ForeignKey("channel_accounts.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    wolfos_goal_id: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text)
    success_metric: Mapped[str | None] = mapped_column(Text)
    target: Mapped[float | None] = mapped_column(Numeric)
    current: Mapped[float] = mapped_column(Numeric, server_default="0")
    playbook_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str] = mapped_column(UID, ForeignKey("channel_accounts.id", ondelete="CASCADE"))
    content_piece_id: Mapped[str] = mapped_column(UID, ForeignKey("content_pieces.id", ondelete="CASCADE"))
    draft_id: Mapped[str | None] = mapped_column(UID, ForeignKey("content_drafts.id", ondelete="SET NULL"))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(Text, server_default="reel")
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    backend_mode: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str] = mapped_column(UID, ForeignKey("channel_accounts.id", ondelete="CASCADE"))
    content_piece_id: Mapped[str | None] = mapped_column(UID, ForeignKey("content_pieces.id", ondelete="SET NULL"))
    draft_id: Mapped[str | None] = mapped_column(UID, ForeignKey("content_drafts.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(Text, server_default="instagram")
    platform_post_id: Mapped[str | None] = mapped_column(Text)
    permalink: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default="reel")
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    backend_mode: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    post_id: Mapped[str | None] = mapped_column(UID, ForeignKey("posts.id", ondelete="CASCADE"))
    platform_post_id: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reach: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    plays: Mapped[int | None] = mapped_column(Integer)
    profile_visits: Mapped[int | None] = mapped_column(Integer)
    follows: Mapped[int | None] = mapped_column(Integer)
    link_clicks: Mapped[int | None] = mapped_column(Integer)
    goal_outcome: Mapped[float | None] = mapped_column(Numeric)
    raw: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class DmFlow(Base):
    __tablename__ = "dm_flows"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str] = mapped_column(UID, ForeignKey("channel_accounts.id", ondelete="CASCADE"))
    thread_id: Mapped[str | None] = mapped_column(Text)
    contact_id: Mapped[str | None] = mapped_column(Text)
    flow_key: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="new")
    window_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DmMessage(Base):
    __tablename__ = "dm_messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    flow_id: Mapped[str] = mapped_column(UID, ForeignKey("dm_flows.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskScore(Base):
    __tablename__ = "risk_scores"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str | None] = mapped_column(UID, ForeignKey("channel_accounts.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[str | None] = mapped_column(UID)
    inputs: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    score: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(Text)
    threshold: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WardenAudit(Base):
    __tablename__ = "warden_audit_trail"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    agent: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    constitution_result: Mapped[str | None] = mapped_column(Text)
    consent_tier: Mapped[str | None] = mapped_column(Text)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    decision: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str | None] = mapped_column(UID, ForeignKey("channel_accounts.id", ondelete="CASCADE"))
    action_type: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[str | None] = mapped_column(UID)
    payload: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    risk_score: Mapped[int | None] = mapped_column(Integer)
    consent_tier: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Suggestion(Base):
    __tablename__ = "suggestions"
    id: Mapped[str] = mapped_column(UID, primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    context: Mapped[dict] = mapped_column(JSONB)
    action: Mapped[dict] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text, server_default="llm_prior")
    prob: Mapped[float | None] = mapped_column(Numeric)


class SuggestionOutcome(Base):
    __tablename__ = "suggestion_outcomes"
    suggestion_id: Mapped[str] = mapped_column(UID, ForeignKey("suggestions.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"))
    reward: Mapped[float] = mapped_column(Numeric)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BanditState(Base):
    __tablename__ = "bandit_state"
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    policy_key: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
