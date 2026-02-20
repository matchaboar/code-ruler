"""SQLAlchemy ORM models for coding rules."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from github_extractor.models import Base


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
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
    provenance: Mapped[list[RuleProvenance]] = relationship(back_populates="rule")


class FunctionTypeRule(Base):
    __tablename__ = "function_type_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), unique=True, nullable=False)
    decorator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    decorator_source: Mapped[str] = mapped_column(Text, nullable=False)
    linter_source: Mapped[str] = mapped_column(Text, nullable=False)
    constraints_json: Mapped[str | None] = mapped_column(JSON, nullable=True)

    rule: Mapped[Rule] = relationship(back_populates="function_type_rule")


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
