# Rule Extraction Test Run: p-e-w/heretic

**Date:** 2026-02-20
**Repository:** https://github.com/p-e-w/heretic
**Description:** A tool for "abliterating" LLM safety guardrails via activation engineering. Python/PyTorch ML codebase.

---

## Step 1: GitHub PR Data Extraction

**Command:** `uv run github-extractor https://github.com/p-e-w/heretic --db heretic.db`

**Results:**
| Metric | Count |
|---|---|
| Merged PRs extracted | 31 |
| Commits extracted | 139 |
| Review comments extracted | 505 |
| Issue comments extracted | 261 |
| Top-level review comments (used for rule extraction) | 234 |

**Bug fix required:** `github_extractor/extractor.py` line 147 used `gh_comment.line` which doesn't exist on PyGithub's `PullRequestComment` object. Fixed to use `getattr(gh_comment, "line", None)` (same for `original_line`).

---

## Step 2: Rule Extraction (Dry Run)

**Command:** `uv run code-ruler extract-rules --db heretic.db --dry-run`

**Bug fixes required:**
1. `code_ruler/llm/client.py` - `call_llm_json()` failed to parse LLM responses that included narrative text around JSON code blocks. Fixed JSON extraction to use regex to find JSON within markdown code blocks or raw text.
2. `code_ruler/llm/prompts.py` - `RULE_EXTRACTION_USER` prompt didn't specify the expected JSON schema fields. Added explicit field definitions (slug, category, severity, title, description, positive_example, negative_example, rationale) and instruction to return only JSON.
3. `code_ruler/pipeline.py` - Added try/except around `extract_rules_from_context()` so one bad LLM response doesn't crash the entire pipeline.

**Results (partial - 151/234 comments processed before termination):**

| Metric | Count |
|---|---|
| Comments processed | 151 |
| Candidate rules extracted | 180 |
| Comments with no rules | 1 |
| Rules per comment (avg) | ~1.2 |

### Rules by Category

| Category | Count | % |
|---|---|---|
| best_practice | 157 | 87.2% |
| function_usage | 12 | 6.7% |
| lint | 11 | 6.1% |

### Rules by Source PR (top contributors)

| PR | Title | Rules Extracted |
|---|---|---|
| #106 | feat: Allow study progress to be saved & resumed | 46 |
| #60 | feat: Add 4-bit loading + LoRA support for low VRAM optimization | 31 |
| #52 | Implement Magnitude-Preserving Orthogonal Ablation | 31 |
| #73 | feat: avoid excessive low divergence iteration | 9 |
| #76 | feat: add continuous optimization option | 8 |
| #108 | fix: Allow abliterating VL models | 7 |
| #110 | feat: refactor save machinery | 5 |
| #42 | Featuring Notebook (Colab/Jupyter) Compatibility | 3 |
| #169 | fix: report VRAM usage across all GPUs | 3 |
| #116 | fix: Use file instead of symlink lock (for windows) | 3 |

### All Extracted Rules

#### best_practice (157 rules)

| # | Slug | Title |
|---|---|---|
| 1 | single-responsibility-functions | Functions should have a single responsibility |
| 2 | default-arg-over-kwargs | Use default arguments instead of kwargs for optional parameters |
| 3 | cache-repeated-calls | Cache repeated function call results |
| 4 | parallel-code-structure | Maintain parallel structure across similar code blocks |
| 5 | minimize-repeated-static-output | Avoid repeating static information in repeated output |
| 6 | display-hardware-specs-details | Show detailed hardware specifications when reporting device info |
| 7 | inclusive-threshold-ranges | Use Inclusive Bounds for Threshold Comparisons |
| 8 | no-magic-numbers | Avoid Magic Numbers in Code |
| 9 | externalize-tuning-parameters | Make Tuning Parameters Configurable |
| 10 | clear-variable-naming | Use variable names that reflect their actual content |
| 11 | constrained-parameter-ranges | Use theoretically justified parameter ranges in optimization |
| 12 | document-experimental-parameters | Document the rationale for experimental parameter ranges |
| 13 | consistent-direction-scope | Maintain consistent scoping of directional parameters |
| 14 | do-preprocessing-once | Perform data transformations as early as possible |
| 15 | avoid-duplicate-operations | Avoid duplicate operations on data |
| 16 | prefer-assignment-over-out-param | Prefer assignment over 'out' parameters |
| 17 | upcast-early | Perform type upcasting early in the function |
| 18 | consistent-naming-conventions | Use consistent naming conventions across the codebase |
| 19 | interdependent-settings-cohesion | Use enums for interdependent configuration flags |
| 20 | tensor-shape-normalization | Normalize tensor shapes when processing weights |
| 21 | comment-implementation-tradeoffs | Document implementation tradeoffs in code comments |
| 22 | preserve-original-values | Store original values before modifications when needed later |
| 23 | document-commented-code | Document reasons for commented-out code |
| 24 | document-algorithmic-details | Document implementation details for algorithmic operations |
| 25 | naming-visual-distinction | Use visually distinct variable names for opposing concepts |
| 26 | neutral-variable-names | Use neutral terminology in variable names |
| 27 | check-numerical-stability | Check for numerical stability in vector operations |
| 28 | make-magic-numbers-configurable | Make Domain-Specific Magic Numbers Configurable |
| 29 | avoid-config-duplication | Store and reuse configuration objects instead of individual values |
| 30 | avoid-unnecessary-type-cast | Avoid unnecessary type casting |
| 31 | justify-rank-impact | Justify high-rank transformations in ML models |
| 32 | comment-performance-impacts | Comment on Performance-Critical Operations |
| 33 | avoid-redundant-splits | Avoid redundantly splitting values across multiple components |
| 34 | validate-float-bounds | Validate boundary conditions for float ranges |
| 35 | consistent-dimension-transforms | Keep transformations consistent across relevant dimensions |
| 36 | consistent-data-processing | Keep data processing consistent across load and use |
| 37 | sanitize-markdown-user-input | Sanitize user input used in markdown content |
| 38 | avoid-optional-null-empty | Prefer empty objects over null for optional values |
| 39 | reduce-nesting-depth | Minimize conditional nesting depth |
| 40 | dependency-deletion-order | Delete objects in reverse dependency order |
| 41 | document-platform-workarounds | Document platform-specific workarounds |
| 42 | no-del-for-cleanup | Don't use 'del' statements for cleanup |
| 43 | explicit-resource-cleanup | Clean up all related resources when reinitializing a system |
| 44 | avoid-magic-strings | Avoid Magic Strings - Use Named Constants |
| 45 | config-values-in-settings | Store Configuration Values in Settings Class |
| 46 | prevent-hashing-collisions | Use unambiguous string representations when hashing data structures |
| 47 | leverage-builtin-features | Leverage Built-in Library Features |
| 48 | document-transforms | Document non-obvious data transformations |
| 49 | derive-related-filenames | Derive related filenames automatically |
| 50 | clear-code-comments | Document complex code with clear comments |
| 51 | hide-implementation-details | Hide implementation details from user interfaces |
| 52 | prefer-object-serialization | Prefer Object Serialization Over Manual Field Processing |
| 53 | user-action-continuity | Provide fallback paths for user action rejections |
| 54 | configurable-paths | Make file/directory paths configurable |
| 55 | document-collection-type-changes | Document changes to collection type handling |
| 56 | cleanup-temp-files | Clean up temporary files after use |
| 57 | avoid-redundant-prefixes | Avoid redundant namespace prefixes |
| 58 | directory-name-conflicts | Avoid directory names that could conflict with future features |
| 59 | required-config-fields | Configuration fields should have non-null default values |
| 60 | use-target-path-directly | Use target path directly when creating parent directories |
| 61 | cross-platform-validation | Validate code behavior on major operating systems |
| 62 | explicit-file-missing-handling | Handle file not found scenarios explicitly |
| 63 | inconsistent-storage-state | Storage state consistency must be maintained |
| 64 | no-swallow-errors | Do not silently swallow errors |
| 65 | consistent-color-semantics | Use consistent color semantics for status messages |
| 66 | use-self-closing-tags | Use self-closing tag syntax for markup |
| 67 | avoid-redundant-prompts | Avoid redundant user prompts |
| 68 | handle-ctrl-c-cancellation | Handle cancellation/interruption cases explicitly |
| 69 | minimize-control-variables | Minimize control flag variables |
| 70 | cohesive-operations | Keep related operations together |
| 71 | clear-file-operation-intent | Document file operation side effects |
| 72 | use-dict-get | Use dict.get() for safe key access |
| 73 | avoid-redundant-calls | Avoid redundant function calls |
| 74 | specific-exceptions | Raise specific exceptions instead of generic Exception |
| 75 | clear-error-state-initialization | Initialize error/completion states at function start |
| 76 | descriptive-gitignore-sections | Use descriptive section comments in .gitignore |
| 77 | no-path-traversal | Prevent path traversal in file paths derived from user input |
| 78 | simplify-single-item-lists | Simplify code that handles known single-item lists |
| 79 | avoid-flag-variables | Avoid using flag variables to control downstream logic |
| 80 | avoid-redundant-instantiation | Avoid redundant object instantiation |
| 81 | use-existing-state-checks | Use existing state enums/flags rather than creating redundant ones |
| 82 | validate-state-invariants | Validate state invariants when resuming saved application state |
| 83 | explicit-completion-conditions | Include extra conditions in completion checks |
| 84 | declare-variables-near-usage | Declare variables close to where they are used |
| 85 | minimize-variable-scope | Minimize the scope and number of variables |
| 86 | simple-iteration-counts | Use simple, clear logic for iteration counts |
| 87 | settings-priority-clarity | Document settings source priority |
| 88 | name-matches-return-type | Function name should reflect return value type |
| 89 | function-return-type-annotation | Functions should have return type annotations |
| 90 | clean-up-unused-code | Remove unused code rather than commenting out or keeping dead code |
| 91 | typed-function-returns | Functions must have return type annotations |
| 92 | annotate-function-return-types | Function Return Types Must Be Annotated |
| 93 | avoid-abbreviations-in-names | Avoid abbreviations in identifier names |
| 94 | use-pythonic-dict-key-check | Use 'in' operator for dictionary key checks |
| 95 | specific-exceptions (dup) | Raise specific exception types |
| 96 | minimal-parameter-passing | Pass only required parameters |
| 97 | maintain-backward-compatibility | Maintain backward compatibility when modifying model support |
| 98 | simplest-config-check | Use the simplest possible configuration check |
| 99 | match-function-return-doc | Function return values must match documented return types |
| 100 | annotate-function-return-type | Always annotate function return types |
| 101 | reusable-function-extraction | Only extract reusable functionality into separate functions |
| 102 | sync-lock-dependencies | Keep dependency lock files in sync with package specifications |
| 103 | respect-algorithm-autonomy | Respect ML algorithm autonomy |
| 104 | test-changes-impacts | Test impacts before committing optimization changes |
| 105 | meaningful-ui-information | Only display UI information that provides actionable value |
| 106 | prefer-simple-optimization | Prefer simple optimization approaches unless complexity is justified |
| 107 | validate-optimization-improvements | Validate optimization improvements with thorough testing |
| 108 | consistent-variable-references | Use consistent variable references throughout a function |
| 109 | accurate-parameter-descriptions | Parameter descriptions must be technically accurate |
| 110 | pareto-sort-optimal | Sort multi-objective optimization results by all objectives |
| 111 | explicit-state-check | Explicitly check operation state before processing |
| 112 | preserve-variable-semantics | Preserve semantic meaning of domain variables |
| 113 | meaningful-variable-purpose | Variables should have clear and obvious purpose |
| 114 | avoid-redundant-code | Avoid redundant code duplication |
| 115 | avoid-scattered-conditionals | Avoid scattered repetitive conditionals |
| 116 | maintain-logical-code-order | Maintain logical code ordering within functions |
| 117 | explicit-empty-string-check | Check for both None and empty string explicitly |
| 118 | unclear-infinite-loop | Avoid unclear infinite loops without documented purpose |
| 119 | avoid-redundant-checks | Avoid redundant conditional checks |
| 120 | maintain-code-comments | Maintain explanatory code comments when modifying code |
| 121 | review-changes-carefully | Review your own code changes carefully before submission |
| 122 | module-vs-parameter-handling | Handle both Module and Parameter types in neural network traversal |
| 123 | matrix-tensor-device-match | Ensure tensor operations occur on matching devices |
| 124 | document-matrix-operations | Document matrix operation shapes and intentions |
| 125 | avoid-fork-attribution | Remove fork references when repository is independent |
| 126 | prefer-enums-over-flags | Prefer enums over boolean flags for multi-option settings |
| 127 | config-param-type-consistency | Ensure configuration parameter types are consistent across related API calls |
| 128 | descriptive-output-labels | Use clear and descriptive labels in log/output messages |
| 129 | model-wrapper-compatibility | Ensure model wrapper compatibility across variants |
| 130 | type-aware-hasattr | Use hasattr() checks to handle polymorphic types |
| 131 | validate-target-modules | Validate target modules before applying model adapters |
| 132 | explicit-type-cast-justification | Document explicit type conversions |
| 133 | handle-all-code-paths | Handle all possible code paths and configurations |
| 134 | precise-return-type-hints | Use precise type hints in function return annotations |
| 135 | validate-type-before-add | Validate types before adding to collections |
| 136 | module-validation-upfront | Validate module properties early |
| 137 | code-path-separation | Keep code path-specific logic separate |
| 138 | test-data-size | Keep test data and dependencies minimal |
| 139 | explicit-text-file-handling | Use explicit text file handling in Git |
| 140 | avoid-lockfile-binary | Treat lockfiles as text files in Git |
| 141 | document-config-options | Document configuration options with all valid choices |
| 142 | instance-method-over-function | Prefer instance methods over standalone functions that operate on class instances |
| 143 | separation-of-concerns | Maintain clear separation of concerns between modules |
| 144 | input-handling-location | Centralize input handling in main entry points |
| 145 | validate-memory-requirements | Validate memory requirements before heavy operations |
| 146 | respect-cancel-actions | Respect user cancellation actions |
| 147 | memory-efficient-load-order | Load resource-intensive operations in RAM before VRAM when possible |
| 148 | memory-requirement-warnings | Provide clear memory requirement warnings for resource-intensive operations |
| 149 | consistent-dtype-settings | Use consistent data type settings across model operations |
| 150 | avoid-premature-optimization | Avoid premature optimization and unnecessary complexity |
| 151 | handle-critical-failures | Handle critical failures immediately |
| 152 | keep-static-kwargs | Keep static keyword arguments in function calls |
| 153 | error-handling-completeness | Handle all error cases explicitly |
| 154 | document-error-handling | Document expected error scenarios in error handling blocks |
| 155 | specific-exception-handling | Handle specific exceptions rather than catching all exceptions |
| 156 | memory-warning-for-large-ops | Warn users about significant memory operations |
| 157 | error-handling-clarity | Document error scenarios in function docstrings |

#### function_usage (12 rules)

| # | Slug | Title |
|---|---|---|
| 1 | use-provided-parameters | Use Provided Function Parameters When Available |
| 2 | document-api-behavior | Document unexpected API return values |
| 3 | lora-alpha-scaling | LoRA alpha should match computation method |
| 4 | prefer-built-in-copy-params | Prefer built-in copy parameters when available |
| 5 | use-named-args-torch | Use named arguments for PyTorch function parameters |
| 6 | validate-trial-completion | Validate trial completion when checking optimization study progress |
| 7 | function-argument-count | Match function argument count exactly |
| 8 | validate-function-parameters | Pass correct parameter types when calling functions |
| 9 | explicit-cli-args-handling | Explicitly handle CLI arguments in settings priority |
| 10 | consistent-remote-code-trust | Use consistent patterns for handling remote code trust settings |
| 11 | conditional-sampling-tpe | Avoid conditional parameters with multivariate TPE sampling |
| 12 | tensor-type-check | Validate tensor types when processing ML model data |

#### lint (11 rules)

| # | Slug | Title |
|---|---|---|
| 1 | comment-punctuation | End comments with periods |
| 2 | validate-hash-function-names | Use correct hash function names |
| 3 | comment-sentence-punctuation | Comments should use proper sentence punctuation |
| 4 | avoid-redundant-string-conversion | Avoid redundant string conversions |
| 5 | field-colon-class-attr | Include colon after Field definitions in class attributes |
| 6 | no-trailing-newline | Avoid unnecessary blank lines at the end of code blocks |
| 7 | redundant-type-cast | Avoid redundant type casts |
| 8 | comment-style-standard | Comments should be complete sentences with proper capitalization and punctuation |
| 9 | attribute-checks-before-usage | Check for attributes before accessing them |
| 10 | remove-unused-parameters | Remove unused function parameters |
| 11 | consistent-indentation | Maintain consistent indentation style throughout the file |

---

## Observations

1. **High yield rate**: 180 rules from 151 comments (1.2 rules/comment avg), with only 1 comment yielding no rules.

2. **Category skew**: 87% of rules are `best_practice`. The LLM rarely classifies rules as `lint` or `function_usage` even when they could be. The prompt may need tuning to encourage more specific categorization.

3. **Duplicate detection needed**: Several rules appear semantically duplicated (e.g., `specific-exceptions` appears twice, multiple variants of "annotate return types", several "avoid redundant X" rules). The dedup phase (skipped in dry-run) would consolidate these.

4. **Domain-specific rules**: The heretic repo produced interesting ML/PyTorch-specific rules (tensor device matching, LoRA alpha scaling, VRAM management) alongside general coding best practices.

5. **PR #106 dominance**: The "save & resume" feature PR contributed 46 rules alone (25% of total), suggesting large PRs with extensive review feedback generate disproportionately many rules.

6. **Pipeline stability**: Three bugs were found and fixed during this run (PyGithub attribute access, JSON parsing, error handling). The pipeline is now more robust for future runs.
