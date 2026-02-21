"""DBOS durable workflow for extracting rules from PR review comments."""

from __future__ import annotations

from dataclasses import asdict

from dbos import DBOS


@DBOS.workflow()
def extract_rules_workflow(
    db_path: str,
    job_id: str,
    limit: int | None = None,
    dry_run: bool = False,
    repo_full_name: str | None = None,
) -> dict:
    """Durable workflow: extract coding rules from PR review comments.

    Each LLM call is a separate DBOS step for crash-resumability.
    """
    from code_ruler.workflows.events import create_job, emit_event, update_job_status

    repo_url = f"https://github.com/{repo_full_name}" if repo_full_name else None
    workflow_id = DBOS.workflow_id
    create_job(db_path, job_id, "extract-rules", repo_url, {
        "limit": limit, "dry_run": dry_run, "repo_full_name": repo_full_name,
    }, workflow_id=workflow_id)

    try:
        contexts = build_contexts_step(db_path, limit, repo_full_name)
        if not contexts:
            update_job_status(db_path, job_id, "completed")
            return {"processed": 0, "rules_stored": 0}

        total = len(contexts)
        rules_stored = 0

        for i, ctx in enumerate(contexts, 1):
            result = process_single_review_workflow(db_path, job_id, ctx, i, total, dry_run)
            rules_stored += result.get("stored", 0)

            emit_event(db_path, job_id, "review_done", {
                "index": i, "total": total,
                "pr_number": ctx["pr_number"], "file_path": ctx["file_path"],
                "candidates": result.get("candidates", []),
            })

        update_job_status(db_path, job_id, "completed")
        return {"processed": total, "rules_stored": rules_stored}
    except Exception as e:
        update_job_status(db_path, job_id, "failed", error=str(e))
        raise


@DBOS.step()
def build_contexts_step(
    db_path: str,
    limit: int | None,
    repo_full_name: str | None,
) -> list[dict]:
    """Query the DB for unprocessed review comments and return serializable dicts."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.extraction.context_builder import build_contexts

    engine = get_engine(db_path)
    init_db(engine)
    factory = get_session_factory(engine)
    with factory() as session:
        contexts = build_contexts(session, limit=limit, repo_full_name=repo_full_name)
    return [asdict(c) for c in contexts]


@DBOS.workflow()
def process_single_review_workflow(
    db_path: str,
    job_id: str,
    ctx: dict,
    index: int,
    total: int,
    dry_run: bool,
) -> dict:
    """Child workflow: process one review comment — extract, dedup, store."""
    from code_ruler.workflows.events import emit_event

    emit_event(db_path, job_id, "review_start", {
        "index": index, "total": total,
        "pr_number": ctx["pr_number"], "pr_title": ctx["pr_title"],
        "file_path": ctx["file_path"], "comment_author": ctx["comment_author"],
    })

    candidates = extract_rules_step(ctx)
    if not candidates:
        return {"stored": 0, "candidates": []}

    if dry_run:
        return {
            "stored": 0,
            "candidates": [
                {"slug": c["slug"], "title": c["title"],
                 "category": c["category"], "action": "dry_run"}
                for c in candidates
            ],
        }

    review_candidates = []
    stored = 0
    for candidate in candidates:
        decision = dedup_step(db_path, candidate)

        if decision["action"] == "discard":
            review_candidates.append({
                "slug": candidate["slug"], "title": candidate["title"],
                "category": candidate["category"], "action": "discard",
            })
            continue

        rule_to_store = decision.get("merged_rule") or candidate
        store_rule_step(db_path, rule_to_store, ctx)
        stored += 1
        review_candidates.append({
            "slug": candidate["slug"], "title": candidate["title"],
            "category": candidate["category"], "action": decision["action"],
        })

    return {"stored": stored, "candidates": review_candidates}


@DBOS.step()
def extract_rules_step(ctx: dict) -> list[dict]:
    """LLM call #1: extract candidate rules from a review context."""
    from code_ruler.extraction.context_builder import ExtractionContext
    from code_ruler.extraction.rule_extractor import extract_rules_from_context
    from code_ruler.llm.client import DEFAULT_MODEL, TraceCollector, get_client, set_trace_collector

    collector = TraceCollector()
    set_trace_collector(collector)
    try:
        context = ExtractionContext(**ctx)
        client = get_client()
        candidates = extract_rules_from_context(client, context, DEFAULT_MODEL)
        return [c.model_dump() for c in candidates]
    finally:
        set_trace_collector(None)


@DBOS.step()
def dedup_step(db_path: str, candidate_dict: dict) -> dict:
    """LLM call #2: check if a candidate rule is a duplicate."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.db.repository import get_all_rules
    from code_ruler.extraction.rule_deduplicator import check_duplicate
    from code_ruler.llm.client import DEFAULT_MODEL, TraceCollector, get_client, set_trace_collector
    from code_ruler.llm.schemas import CandidateRule

    collector = TraceCollector()
    set_trace_collector(collector)
    try:
        engine = get_engine(db_path)
        init_db(engine)
        factory = get_session_factory(engine)
        with factory() as session:
            existing = get_all_rules(session)
            client = get_client()
            candidate = CandidateRule(**candidate_dict)
            decision = check_duplicate(client, candidate, existing, DEFAULT_MODEL)
        result = {"action": decision.action, "reasoning": decision.reasoning}
        if decision.merged_rule:
            result["merged_rule"] = decision.merged_rule.model_dump()
        return result
    finally:
        set_trace_collector(None)


@DBOS.step()
def store_rule_step(db_path: str, candidate_dict: dict, ctx: dict) -> dict:
    """LLM call #3 (if function_type) + DB write: store a rule and commit."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.db.repository import create_function_type_rule, create_provenance, create_rule
    from code_ruler.extraction.function_type_gen import generate_function_type
    from code_ruler.llm.client import DEFAULT_MODEL, TraceCollector, get_client, set_trace_collector
    from code_ruler.llm.schemas import CandidateRule

    collector = TraceCollector()
    set_trace_collector(collector)
    try:
        engine = get_engine(db_path)
        init_db(engine)
        factory = get_session_factory(engine)

        candidate = CandidateRule(**candidate_dict)

        with factory() as session:
            rule = create_rule(
                session,
                slug=candidate.slug,
                category=candidate.category,
                severity=candidate.severity,
                title=candidate.title,
                description=candidate.description,
                positive_example=candidate.positive_example,
                negative_example=candidate.negative_example,
                rationale=candidate.rationale,
            )

            if candidate.category == "function_type":
                client = get_client()
                spec = generate_function_type(client, candidate, DEFAULT_MODEL)
                if spec:
                    create_function_type_rule(
                        session,
                        rule_id=rule.id,
                        decorator_name=spec.decorator_name,
                        decorator_source=spec.decorator_source,
                        linter_source=spec.linter_source,
                        constraints_json=spec.constraints,
                    )

            create_provenance(
                session,
                rule_id=rule.id,
                pull_request_id=ctx["pr_id"],
                review_comment_id=ctx["review_comment_id"],
            )
            session.commit()

            result_slug = rule.slug
            result_version = rule.version

        return {"slug": result_slug, "version": result_version}
    finally:
        set_trace_collector(None)
