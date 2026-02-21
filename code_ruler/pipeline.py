"""Orchestrates: contexts → extract → dedup → store."""

from __future__ import annotations

from typing import Callable

from anthropic import AnthropicBedrock
from sqlalchemy.orm import Session

from code_ruler.db.models import Rule
from code_ruler.db.repository import (
    create_function_type_rule,
    create_provenance,
    create_rule,
    get_all_rules,
)
from code_ruler.extraction.context_builder import ExtractionContext, build_contexts
from code_ruler.extraction.function_type_gen import generate_function_type
from code_ruler.extraction.rule_deduplicator import check_duplicate
from code_ruler.extraction.rule_extractor import extract_rules_from_context
from code_ruler.llm.client import TraceCollector, set_trace_collector
from code_ruler.llm.schemas import CandidateRule


def run_pipeline(
    client: AnthropicBedrock,
    session: Session,
    model: str,
    limit: int | None = None,
    dry_run: bool = False,
    on_review: Callable[..., None] | None = None,
    repo_full_name: str | None = None,
) -> list[CandidateRule]:
    """Run the full rule extraction pipeline.

    Args:
        on_review: Optional callback(event_type, **data) for structured events.
        repo_full_name: If set, only process comments from this repository.

    Returns all candidate rules (for dry_run inspection or confirmation).
    """
    contexts = build_contexts(session, limit=limit, repo_full_name=repo_full_name)
    if not contexts:
        print("No review comments found to process.")
        return []

    print(f"Processing {len(contexts)} review comments...")

    all_candidates: list[CandidateRule] = []

    for i, context in enumerate(contexts, 1):
        print(f"\n[{i}/{len(contexts)}] PR #{context.pr_number}: {context.file_path}")

        # Set up a trace collector for this review step
        collector = TraceCollector()
        set_trace_collector(collector)

        if on_review:
            on_review(
                "review_start",
                index=i, total=len(contexts),
                pr_number=context.pr_number, pr_title=context.pr_title,
                file_path=context.file_path, comment_author=context.comment_author,
            )

        # Phase 1: Extract rules
        try:
            candidates = extract_rules_from_context(client, context, model)
        except Exception as e:
            print(f"  Error extracting rules: {e}")
            if on_review:
                on_review(
                    "review_error",
                    index=i, total=len(contexts),
                    pr_number=context.pr_number, file_path=context.file_path,
                    error=str(e),
                    dd_traces=collector.to_dicts(),
                )
            set_trace_collector(None)
            continue
        if not candidates:
            print("  No rules extracted.")
            if on_review:
                on_review(
                    "review_done",
                    index=i, total=len(contexts),
                    pr_number=context.pr_number, file_path=context.file_path,
                    candidates=[],
                    dd_traces=collector.to_dicts(),
                )
            set_trace_collector(None)
            continue

        review_candidates = []
        for candidate in candidates:
            print(f"  Candidate: [{candidate.category}] {candidate.slug}: {candidate.title}")

            if dry_run:
                all_candidates.append(candidate)
                review_candidates.append({
                    "slug": candidate.slug, "title": candidate.title,
                    "category": candidate.category, "action": "dry_run",
                })
                continue

            # Phase 3: Deduplication (per-repo)
            existing = get_all_rules(session, repo_id=context.repo_id)
            decision = check_duplicate(client, candidate, existing, model)

            if decision.action == "discard":
                print(f"    Discarded (duplicate): {decision.reasoning}")
                review_candidates.append({
                    "slug": candidate.slug, "title": candidate.title,
                    "category": candidate.category, "action": "discard",
                })
                continue

            rule_to_store = decision.merged_rule if decision.action == "merge" else candidate
            if rule_to_store is None:
                rule_to_store = candidate

            # Store the rule
            rule = _store_rule(client, session, rule_to_store, context, model)
            all_candidates.append(candidate)
            review_candidates.append({
                "slug": candidate.slug, "title": candidate.title,
                "category": candidate.category, "action": decision.action,
            })

            print(f"    Stored as rule: {rule.slug} (v{rule.version})")

        if on_review:
            on_review(
                "review_done",
                index=i, total=len(contexts),
                pr_number=context.pr_number, file_path=context.file_path,
                candidates=review_candidates,
                dd_traces=collector.to_dicts(),
            )

        set_trace_collector(None)

    session.commit()
    return all_candidates


def _store_rule(
    client: AnthropicBedrock,
    session: Session,
    candidate: CandidateRule,
    context: ExtractionContext,
    model: str,
) -> Rule:
    """Store a candidate rule in the database."""
    rule = create_rule(
        session,
        slug=candidate.slug,
        repo_id=context.repo_id,
        category=candidate.category,
        severity=candidate.severity,
        title=candidate.title,
        description=candidate.description,
        positive_example=candidate.positive_example,
        negative_example=candidate.negative_example,
        rationale=candidate.rationale,
    )

    # Phase 2: Generate function type spec if applicable
    if candidate.category == "function_type":
        spec = generate_function_type(client, candidate, model)
        if spec:
            create_function_type_rule(
                session,
                rule_id=rule.id,
                decorator_name=spec.decorator_name,
                decorator_source=spec.decorator_source,
                linter_source=spec.linter_source,
                constraints_json=spec.constraints,
            )

    # Record provenance
    create_provenance(
        session,
        rule_id=rule.id,
        pull_request_id=context.pr_id,
        review_comment_id=context.review_comment_id,
    )

    return rule
