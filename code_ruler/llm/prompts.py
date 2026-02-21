"""Prompt templates for LLM interactions."""

RULE_EXTRACTION_SYSTEM = """\
You are an expert code reviewer analyzing PR review feedback to extract reusable coding rules.

Given a review comment, its associated diff hunk, and PR context, extract zero or more coding rules.
Each rule should be general enough to apply beyond this specific PR.

Categories:
- best_practice: General coding best practices (naming, structure, patterns)
- lint: Specific code style or error-prone pattern to flag
- function_usage: How a specific function/API should be used
- function_type: A type of function with specific constraints (e.g., pure functions, API handlers)

Severities: error, warning, info
"""

RULE_EXTRACTION_USER = """\
## PR Context
- PR #{pr_number}: {pr_title}
- Repository: {repo_name}
- Author: {pr_author}

## Review Comment
Author: {comment_author}
File: {file_path}
Comment: {comment_body}

## Diff Hunk
```
{diff_hunk}
```

Extract coding rules from this review feedback. Return a JSON array of rules.
If no generalizable rule can be extracted, return an empty array `[]`.

Each rule object must have exactly these fields:
- slug: a short kebab-case identifier (e.g. "single-responsibility-functions")
- category: one of "best_practice", "lint", "function_usage", "function_type"
- severity: one of "error", "warning", "info"
- title: a short human-readable title
- description: detailed description of the rule
- positive_example: a short code snippet showing correct usage (or null)
- negative_example: a short code snippet showing incorrect usage (or null)
- rationale: why this rule matters

Return ONLY the JSON array, no other text.
"""

FUNCTION_TYPE_SYSTEM = """\
You are an expert Python developer generating decorator and linter code for function type rules.

Given a function type rule description, generate:
1. A Python decorator that stamps `__rule_marker_type__` metadata on the function (no runtime behavior change)
2. A `check(func_node: ast.FunctionDef, source: str) -> list[str]` linter function using only stdlib `ast`

The decorator must be a simple marker - it should NOT modify the function's behavior.
The linter function receives an AST node and source code, returning a list of violation messages.
"""

FUNCTION_TYPE_USER = """\
## Rule
Title: {title}
Description: {description}
Constraints: {constraints}

## Positive Example (correct code)
```python
{positive_example}
```

## Negative Example (violating code)
```python
{negative_example}
```

Generate the decorator and linter source code. Return JSON with:
- decorator_name: the decorator function name
- constraints: list of constraint descriptions
- decorator_source: complete Python source for the decorator function
- linter_source: complete Python source for the check() function
"""

ENFORCER_SYSTEM = """\
You are an expert Python developer generating automated enforcement checks for coding rules.

Given a coding rule, generate a Python function:
    def check(tree: ast.Module, source: str) -> list[str]

This function receives a parsed AST module and the raw source code. It must return a list of
violation message strings. An empty list means the code is compliant.

Rules:
- Use ONLY the stdlib `ast` module for analysis
- Do NOT import any external packages
- The function must be self-contained
- Return clear, actionable violation messages
- Be precise: only flag actual violations of the described rule

For function_type rules, also generate decorator code that stamps __rule_marker_type__ metadata:
    def decorator_name(func):
        func.__rule_marker_type__ = "rule_slug"
        return func

Return your code inside ```python fences.
"""

ENFORCER_USER = """\
## Rule
Title: {title}
Description: {description}
Category: {category}

## Positive Example (correct code)
```python
{positive_example}
```

## Negative Example (violating code)
```python
{negative_example}
```

Generate a `check(tree: ast.Module, source: str) -> list[str]` function that detects violations \
of this rule. The function should return violations for the negative example and no violations for \
the positive example.

Return ONLY the Python code inside ```python fences. Do not include imports — `ast` is already available.
"""

ENFORCER_FIX_USER = """\
## Rule
Title: {title}
Description: {description}
Category: {category}

## Previous Attempt (failed)
```python
{previous_source}
```

## Error
{error}

## Negative Example (should trigger violations)
```python
{negative_example}
```

Fix the check function so it correctly detects violations in the negative example. \
Return ONLY the corrected Python code inside ```python fences.
"""

DEDUP_SYSTEM = """\
You are comparing a candidate coding rule against existing rules to detect duplicates.

Respond with a JSON object:
- action: "merge" (combine into one), "discard" (candidate is redundant), or "keep_both" (distinct rules)
- merged_rule: if action is "merge", the merged rule object; otherwise null
- reasoning: brief explanation
"""

DEDUP_USER = """\
## Candidate Rule
Slug: {candidate_slug}
Title: {candidate_title}
Description: {candidate_description}
Category: {candidate_category}

## Existing Rules
{existing_rules}

Is the candidate a duplicate of any existing rule?
"""
