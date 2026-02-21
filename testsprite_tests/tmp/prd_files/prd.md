# Code Ruler - Product Requirements Document

## Overview
Code Ruler is a tool that learns coding rules from GitHub PR reviews and enforces them as a linter. It provides a web UI for viewing and managing extracted rules.

## Core Features

### 1. Repository Management
- List all repositories with rule counts
- API: GET /api/repos

### 2. Rule Management
- List rules with filtering by category, severity, active status, and search
- Get detailed rule information including decorator and linter source
- Rules are scoped to repositories
- API: GET /api/rules, GET /api/rules/{slug}

### 3. Rule Provenance
- Track which PR reviews generated each rule
- Show PR references, comment authors, diff hunks, and file paths
- API: GET /api/rules/{slug}/provenance

### 4. Enforcer Management
- Generate enforcer scripts (AST-based linter checks) for rules
- List all enforcers, optionally scoped to a repo
- Get enforcer details including source code, test results, and Datadog traces
- API: POST /api/rules/{slug}/generate-enforcer, GET /api/enforcers, GET /api/rules/{slug}/enforcer

### 5. Video Generation
- Generate animated video previews for rules using Minimax API
- Poll for video generation status
- API: POST /api/rules/{slug}/generate-video, GET /api/video/{task_id}

### 6. Statistics
- Summary statistics about rules and PRs
- Breakdown by category and severity
- Optional repo scoping
- API: GET /api/stats

### 7. Credentials Check
- Verify connectivity to AWS Bedrock, Datadog, and GitHub
- API: GET /api/credentials/status

### 8. Pipeline Jobs
- Extract PRs from GitHub repos (full and quick modes)
- Extract rules from PR review comments (full and quick modes)
- Quick run combining PR extraction and rule extraction
- Resume and cancel DBOS workflows
- Get step-level job progress
- Get repo-level processing statistics
- API: Multiple endpoints under /api/pipeline/

## Technical Stack
- Python 3.11, FastAPI, SQLAlchemy, SQLite
- Anthropic Claude via AWS Bedrock for LLM
- DBOS for durable workflow execution
- Datadog for observability
- React + TypeScript frontend
