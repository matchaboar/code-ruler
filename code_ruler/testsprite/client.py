"""TestSprite integration: clone repo and call TestSprite API to generate tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from code_ruler.db.models import Rule, TestSpriteResult
from code_ruler.db.repository import create_testsprite_result, update_testsprite_result

TESTSPRITE_BASE_URL = os.environ.get("TESTSPRITE_BASE_URL", "https://api.testsprite.com/v1")
TESTSPRITE_API_KEY = os.environ.get("TESTSPRITE_API_KEY", "")


def _api_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TESTSPRITE_API_KEY}",
        "Content-Type": "application/json",
    }


def _api_post(path: str, payload: dict) -> dict:
    """HTTP POST to TestSprite API. Stub that can be swapped for MCP client calls."""
    import urllib.request

    url = f"{TESTSPRITE_BASE_URL}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_api_headers(), method="POST")
    resp = urllib.request.urlopen(req, timeout=300)
    return json.loads(resp.read())


def _clone_repo(repo_url: str, dest: str) -> None:
    """Shallow clone a repo."""
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, dest],
        check=True,
        capture_output=True,
        timeout=120,
    )


def _generate_diff(repo_dir: str, generated_files: list[str]) -> str:
    """Generate a unified diff showing generated test files as new files."""
    diff_lines: list[str] = []
    for fpath in generated_files:
        rel = os.path.relpath(fpath, repo_dir)
        try:
            with open(fpath) as f:
                content = f.read()
        except OSError:
            continue
        lines = content.splitlines()
        diff_lines.append(f"--- /dev/null")
        diff_lines.append(f"+++ b/{rel}")
        diff_lines.append(f"@@ -0,0 +1,{len(lines)} @@")
        for line in lines:
            diff_lines.append(f"+{line}")
        diff_lines.append("")
    return "\n".join(diff_lines)


def generate_tests(session: Session, rule: Rule, repo_url: str) -> TestSpriteResult:
    """Clone repo and call TestSprite API to generate unit tests for a rule.

    Steps:
    1. Create DB record with status="cloning"
    2. git clone --depth 1 to temp dir
    3. Call TestSprite API (code summary → test plan → generate & execute)
    4. Collect results and update DB record
    """
    result = create_testsprite_result(
        session,
        rule_id=rule.id,
        repo_url=repo_url,
        status="cloning",
    )
    session.commit()

    tmpdir = tempfile.mkdtemp(prefix="testsprite_")
    try:
        # Step 1: Clone
        print(f"[TestSprite] Cloning {repo_url}...")
        _clone_repo(repo_url, tmpdir)

        # Step 2: Generate code summary
        update_testsprite_result(session, result, status="generating")
        session.commit()
        print("[TestSprite] Generating code summary...")

        summary_resp = _api_post("/code-summary", {
            "repo_path": tmpdir,
            "rule_slug": rule.slug,
            "rule_description": rule.description,
        })

        # Step 3: Generate test plan
        print("[TestSprite] Generating test plan...")
        plan_resp = _api_post("/test-plan", {
            "code_summary": summary_resp.get("summary", ""),
            "rule_slug": rule.slug,
            "rule_title": rule.title,
            "rule_description": rule.description,
            "positive_example": rule.positive_example or "",
            "negative_example": rule.negative_example or "",
        })
        test_plan = plan_resp.get("test_plan", {})
        update_testsprite_result(session, result, test_plan_json=test_plan)
        session.commit()

        # Step 4: Generate and execute tests
        update_testsprite_result(session, result, status="running")
        session.commit()
        print("[TestSprite] Generating and executing tests...")

        exec_resp = _api_post("/generate-and-execute", {
            "repo_path": tmpdir,
            "test_plan": test_plan,
            "rule_slug": rule.slug,
        })

        # Step 5: Collect results
        generated_files = exec_resp.get("generated_files", [])
        test_results = exec_resp.get("test_results", {})
        generated_tests_content = exec_resp.get("generated_tests", "")

        # Generate diff from the generated files
        diff = ""
        if generated_files:
            # Files are paths relative to repo_path in the API response
            abs_files = [os.path.join(tmpdir, f) for f in generated_files]
            existing_files = [f for f in abs_files if os.path.exists(f)]
            if existing_files:
                diff = _generate_diff(tmpdir, existing_files)
        if not diff and generated_tests_content:
            # Fallback: create diff from the concatenated test content
            lines = generated_tests_content.splitlines()
            diff = "\n".join([
                "--- /dev/null",
                f"+++ b/tests/{rule.slug}_test.py",
                f"@@ -0,0 +1,{len(lines)} @@",
            ] + [f"+{l}" for l in lines])

        update_testsprite_result(
            session,
            result,
            status="completed",
            generated_tests=generated_tests_content,
            test_results_json=test_results,
            diff=diff,
        )
        session.commit()
        print(f"[TestSprite] Completed successfully for rule '{rule.slug}'.")
        return result

    except Exception as e:
        update_testsprite_result(
            session,
            result,
            status="failed",
            error_message=str(e)[:2000],
        )
        session.commit()
        print(f"[TestSprite] Failed: {e}")
        raise

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
