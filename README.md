# Code Ruler

## `TO RUN, USE ./start.sh`

<a href="https://youtu.be/B43seaULG2o">
  <img src="https://img.youtube.com/vi/B43seaULG2o/maxresdefault.jpg" alt="Code Ruler Demo Video" width="600">
</a>

![Code Ruler](image.png)

AI-powered system that automatically extracts coding rules from GitHub PR review comments, then generates enforcement scripts and tests for those rules.

## Prerequisites

- If on linux, you must install prerequisite packages to the OS
that are needed to build python (google command for OS).
- Install mise.

## Running

`uv run ./package_name/main.py`

## Testing

- [TestSprite Test Report](testsprite_tests/testsprite-mcp-test-report.md)
- [TestSprite Raw Report](testsprite_tests/tmp/raw_report.md)

Run tests: `uv run pytest testsprite_tests/test_all_endpoints.py -v`

## Architecture Overview

```mermaid
graph TB
    subgraph Frontend["Frontend - React/TypeScript"]
        RL[Rule List Page]
        RD[Rule Detail Page]
        PP[Pipeline Page]
        EP[Enforcer Page]
        TP[Tests Page]
        SP[Status Page]
    end

    subgraph Backend["Backend - FastAPI"]
        API[REST API]
        EXT[Rule Extraction]
        ENF[Enforcer Generator]
        WF[Durable Workflows]
    end

    subgraph Storage["Storage"]
        DB[(SQLite Database)]
    end

    subgraph External["External Services"]
        GH[GitHub]
        LLM[Claude AI via AWS Bedrock]
        DD[Datadog]
        TS[TestSprite]
        MM[Minimax Video]
    end

    Frontend -->|HTTP| API
    API --> EXT
    API --> ENF
    API --> WF
    EXT --> LLM
    ENF --> LLM
    WF --> DB
    EXT --> DB
    ENF --> DB
    EXT --> GH
    API --> TS
    API --> MM
    API --> DD
```

## Main User Workflow

```mermaid
flowchart LR
    A[GitHub PRs] -->|Extract PRs| B[Review Comments in DB]
    B -->|Extract Rules| C[Coding Rules]
    C -->|Generate Enforcer| D[AST Enforcement Scripts]
    C -->|Generate Tests| E[Automated Tests]
    C -->|Generate Video| F[Rule Visualization]
```

## Rule Extraction Pipeline

```mermaid
flowchart TD
    Start([User clicks Extract Rules]) --> Fetch[Fetch unprocessed review comments]
    Fetch --> Build[Build extraction context per comment]
    Build --> LLM1["Claude AI: Extract candidate rules"]
    LLM1 --> Dedup["Claude AI: Check for duplicates"]
    Dedup -->|Discard| Skip[Skip duplicate]
    Dedup -->|Merge| Merge[Merge with existing rule]
    Dedup -->|Keep| Store[Store new rule in DB]
    Merge --> Store
    Store --> FT{Function type rule?}
    FT -->|Yes| Gen["Claude AI: Generate decorator and linter"]
    FT -->|No| Prov[Record provenance]
    Gen --> Prov
    Prov --> Done([Rules available in UI])
```

## Enforcer Generation Flow

```mermaid
flowchart TD
    Start([User clicks Generate Enforcer]) --> Check{Has existing linter source?}
    Check -->|Yes| Copy[Copy linter source as enforcer]
    Check -->|No| LLM["Claude AI: Generate AST check function"]
    LLM --> Test[Run check against negative example]
    Test -->|Violations found| Pass[Test passed - save enforcer]
    Test -->|No violations| Retry{Attempts < 3?}
    Retry -->|Yes| Fix["Claude AI: Fix enforcement code"]
    Fix --> Test
    Retry -->|No| Fail[Save as failed]
    Copy --> Done([Enforcer available in UI])
    Pass --> Done
    Fail --> Done
```

## Frontend Pages and Actions

```mermaid
flowchart TD
    subgraph Pipeline["Pipeline Page"]
        EP_BTN["Extract PRs button"]
        ER_BTN["Extract Rules button"]
        QR_BTN["Quick Run button"]
        JOBS[Job status and event log]
    end

    subgraph Rules["Rule List Page"]
        FILTER[Filter by category / severity / search]
        CARDS[Rule cards grid]
    end

    subgraph Detail["Rule Detail Page"]
        INFO[Title, description, examples, rationale]
        GEN_ENF["Generate Enforcer button"]
        REGEN["Regenerate button"]
        GEN_VID["Generate Video button"]
        TABS["Tabs: Overview / Provenance / Enforcer / Tests / Video"]
    end

    subgraph Enforcers["Enforcer Page"]
        ENF_LIST[List of enforcement scripts]
        ENF_CODE[Source code and test output]
    end

    subgraph Tests["Tests Page"]
        TEST_LIST[Test generation results]
        TEST_CODE[Generated tests and results]
    end

    Pipeline -->|Rules extracted| Rules
    Rules -->|Click rule| Detail
    Detail -->|Enforcer generated| Enforcers
    Detail -->|Tests generated| Tests
```

## Data Model

```mermaid
erDiagram
    Rule ||--o| FunctionTypeRule : has
    Rule ||--o| EnforcerScript : has
    Rule ||--o{ TestSpriteResult : has
    Rule ||--o{ RuleProvenance : has
    PipelineJob ||--o{ PipelineEvent : has
    RuleProvenance }o--|| PullRequest : "sourced from"
    RuleProvenance }o--|| ReviewComment : "sourced from"

    Rule {
        string slug
        string category
        string severity
        string title
        string description
        bool is_active
    }

    EnforcerScript {
        string enforcer_source
        string check_type
        string test_result
        int attempt_count
    }

    FunctionTypeRule {
        string decorator_source
        string linter_source
    }

    PipelineJob {
        string job_type
        string status
        string repo_url
    }
```
