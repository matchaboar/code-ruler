"""SQLAlchemy ORM models for coding rules."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from github_extractor.models import Base


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (
        UniqueConstraint("slug", "repo_id", name="uq_rule_slug_repo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # best_practice, lint, function_usage, function_type
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # error, warning, info
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    positive_example: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_example: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    function_type_rule: Mapped[FunctionTypeRule | None] = relationship(
        back_populates="rule", uselist=False
    )
    enforcer_script: Mapped[EnforcerScript | None] = relationship(
        back_populates="rule", uselist=False
    )
    testsprite_results: Mapped[list[TestSpriteResult]] = relationship(back_populates="rule")
    provenance: Mapped[list[RuleProvenance]] = relationship(back_populates="rule")
    repository = relationship("Repository", foreign_keys=[repo_id])


class FunctionTypeRule(Base):
    __tablename__ = "function_type_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), unique=True, nullable=False)
    decorator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    decorator_source: Mapped[str] = mapped_column(Text, nullable=False)
    linter_source: Mapped[str] = mapped_column(Text, nullable=False)
    constraints_json: Mapped[str | None] = mapped_column(JSON, nullable=True)

    rule: Mapped[Rule] = relationship(back_populates="function_type_rule")


class EnforcerScript(Base):
    __tablename__ = "enforcer_scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), unique=True, nullable=False)
    enforcer_source: Mapped[str] = mapped_column(Text, nullable=False)
    check_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "module" or "function"
    decorator_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    test_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    dd_traces: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    rule: Mapped[Rule] = relationship(back_populates="enforcer_script")


class RuleProvenance(Base):
    __tablename__ = "rule_provenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False)
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"), nullable=False)
    review_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("review_comments.id"), nullable=True
    )
    extraction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    rule: Mapped[Rule] = relationship(back_populates="provenance")


class PipelineJob(Base):
    """Persisted record of a pipeline job (extract-prs, extract-rules, quick-run)."""

    __tablename__ = "pipeline_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    repo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    params_json: Mapped[str | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    events: Mapped[list[PipelineEvent]] = relationship(
        back_populates="job", order_by="PipelineEvent.created_at"
    )


class PipelineEvent(Base):
    """Persisted event emitted by a pipeline workflow step."""

    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline_jobs.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data_json: Mapped[str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    job: Mapped[PipelineJob] = relationship(back_populates="events")


class TestSpriteResult(Base):
    __tablename__ = "testsprite_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    test_plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_tests: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_results_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    rule: Mapped[Rule] = relationship(back_populates="testsprite_results")
