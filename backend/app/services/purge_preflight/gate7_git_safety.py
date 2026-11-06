"""
Gate 7: Git Safety Verification

Verifies:
- Expected branch and base (using real PR base/head SHAs for pull_request; workflow_dispatch separately)
- Worktree isolation (distinguishes CI detached checkout from developer worktree)
- No unrelated changes overwritten
- Target files scoped correctly with precise allowlist
- No accidental nested repositories
- No unintended changes to unrelated application code
- No credentials/secrets in tracked files (detects actual credential values, not env var names)
- No production deployment or database mutation introduced
- Inspects committed diff, not just working tree
- Scans added/changed content for secrets
- Enforces scope, inspects nested repos, deployment risk and detached-head cases
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List

from .metadata import save_result_with_metadata


@dataclass
class Gate7Result:
    """Gate 7 execution result."""
    test_name: str = "gate7_git_safety"
    current_branch: str = ""
    base_branch: str = ""
    expected_branch: str = "fix/production-expired-cycle-purge"
    expected_base: str = "master"
    pr_head_sha: str = ""
    pr_base_sha: str = ""
    branch_match: bool = False
    base_match: bool = False
    worktree_isolated: bool = False
    worktree_path: str = ""
    nested_repos: List[str] = None
    unrelated_changes: List[str] = None
    secrets_detected: List[dict] = None
    purge_files_only: bool = False
    changed_files: List[str] = None
    production_mutation_risk: bool = False
    deployment_risk: bool = False
    status: str = "PENDING"
    error: Optional[str] = None

    def __post_init__(self):
        if self.nested_repos is None:
            self.nested_repos = []
        if self.unrelated_changes is None:
            self.unrelated_changes = []
        if self.secrets_detected is None:
            self.secrets_detected = []
        if self.changed_files is None:
            self.changed_files = []

    def to_dict(self) -> dict:
        return asdict(self)


# Secret patterns - detect ACTUAL credential values, not environment variable names
# These patterns match actual secrets, tokens, passwords, and credential-bearing URLs
# GitHub secrets expressions (${{ secrets.NAME }}) and env var references ($NAME, ${NAME}) are explicitly allowed
SECRET_PATTERNS = [
    (r"postgresql://[^:\s]+:[^@\s]+@", "PostgreSQL connection string with embedded password"),
    (r"mysql://[^:\s]+:[^@\s]+@", "MySQL connection string with embedded password"),
    (r"mongodb://[^:\s]+:[^@\s]+@", "MongoDB connection string with embedded password"),
    (r"redis://[^:\s]+:[^@\s]+@", "Redis connection string with embedded password"),
    (r"gh[ps]_[a-zA-Z0-9]{36,}", "GitHub token (ghp_ or ghs_)"),
    (r"sk_[a-zA-Z0-9]{32,}", "OpenAI/API key (sk_ prefix)"),
    (r"xoxb-[a-zA-Z0-9-]+", "Slack bot token"),
    (r"xoxp-[a-zA-Z0-9-]+", "Slack user token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    (r"[a-zA-Z0-9+/]{40,}=[=]?", "Potential base64 encoded secret (AWS secret, etc.)"),
    (r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "Private key in PEM format"),
    (r"[a-f0-9]{40}", "Potential GPG fingerprint or SHA1 hash (40 hex chars)"),
]


def run_git_command(args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a git command safely."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30
    )


def ensure_git_history(repo_root: Path, required_refs: List[str]) -> tuple[bool, str]:
    """Ensure sufficient Git history and refs exist for validation.
    
    Returns (success, error_message). Fails if required refs cannot be resolved.
    """
    for ref in required_refs:
        result = run_git_command(["rev-parse", ref], repo_root)
        if result.returncode != 0:
            return False, f"Required ref '{ref}' not available: {result.stderr.strip()}"
    return True, ""


def get_pr_shas(repo_root: Path) -> tuple[str, str, Optional[str]]:
    """
    Get PR head and base SHAs from GitHub environment variables.
    
    For pull_request events: use GITHUB_EVENT_PATH to read actual PR head/base SHAs
    For workflow_dispatch: current HEAD as head, base from input or default to master
    
    Returns (head_sha, base_sha, error). If error is not None, validation should BLOCK.
    """
    head_sha = os.getenv("GITHUB_SHA", "")
    base_sha = ""
    
    # For pull_request, get base SHA from event payload
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    event_path = os.getenv("GITHUB_EVENT_PATH", "")
    
    if event_name == "pull_request":
        if not event_path or not os.path.exists(event_path):
            return "", "", "GITHUB_EVENT_PATH missing or file not found for pull_request event"
        try:
            with open(event_path, "r") as f:
                event_data = json.load(f)
            # PR head SHA
            head_sha = event_data.get("pull_request", {}).get("head", {}).get("sha", head_sha)
            # PR base SHA
            base_sha = event_data.get("pull_request", {}).get("base", {}).get("sha", "")
            # If base SHA not directly available, try to resolve base ref
            if not base_sha:
                base_ref = event_data.get("pull_request", {}).get("base", {}).get("ref", "")
                if base_ref:
                    result = run_git_command(["rev-parse", f"origin/{base_ref}"], repo_root)
                    if result.returncode == 0:
                        base_sha = result.stdout.strip()
                    else:
                        return "", "", f"Failed to resolve base ref 'origin/{base_ref}': {result.stderr.strip()}"
                else:
                    return "", "", "PR base ref not found in event payload"
            if not head_sha:
                return "", "", "PR head SHA not found in event payload"
            if not base_sha:
                return "", "", "PR base SHA could not be determined"
        except json.JSONDecodeError as e:
            return "", "", f"Failed to parse GITHUB_EVENT_PATH JSON: {e}"
        except Exception as e:
            return "", "", f"Error reading PR event payload: {e}"
    elif event_name == "workflow_dispatch":
        # For manual dispatch, use current HEAD as head, master as base
        result = run_git_command(["rev-parse", "HEAD"], repo_root)
        if result.returncode == 0:
            head_sha = result.stdout.strip()
        else:
            return "", "", f"Failed to resolve HEAD: {result.stderr.strip()}"
        result = run_git_command(["rev-parse", "origin/master"], repo_root)
        if result.returncode == 0:
            base_sha = result.stdout.strip()
        else:
            return "", "", f"Failed to resolve origin/master: {result.stderr.strip()}"
    else:
        return "", "", f"Unsupported event type: {event_name}"
    
    return head_sha, base_sha, None


def check_branch_and_base(repo_root: Path) -> tuple[str, str, str, str, bool, bool, Optional[str]]:
    """Check current branch and base using real PR SHAs.
    
    Handles detached HEAD in CI by not requiring branch name match.
    Validates actual base commit SHA against expected base branch.
    
    Returns (current_branch, expected_base, pr_head_sha, pr_base_sha, branch_match, base_match, error).
    """
    # Get current branch (will be empty in detached HEAD)
    result = run_git_command(["branch", "--show-current"], repo_root)
    current_branch = result.stdout.strip()

    # Get PR SHAs with error handling
    pr_head_sha, pr_base_sha, error = get_pr_shas(repo_root)
    if error:
        return current_branch, "master", "", "", False, False, error

    # Check if we're on the expected branch (only if not detached HEAD)
    expected_branch = "fix/production-expired-cycle-purge"
    expected_base = "master"
    
    if current_branch:
        branch_match = current_branch == expected_branch
    else:
        # Detached HEAD (common in CI) - verify HEAD matches expected PR head SHA
        head_result = run_git_command(["rev-parse", "HEAD"], repo_root)
        if head_result.returncode == 0:
            actual_head = head_result.stdout.strip()
            branch_match = (actual_head == pr_head_sha)
        else:
            branch_match = False

    # Check if base is master by verifying the actual base SHA equals origin/master
    # Exact semantics: PR base MUST be the current origin/master, not just an ancestor
    base_match = False
    if pr_base_sha:
        master_result = run_git_command(["rev-parse", "origin/master"], repo_root)
        if master_result.returncode == 0:
            actual_master_sha = master_result.stdout.strip()
            base_match = (pr_base_sha == actual_master_sha)
    
    return current_branch, expected_base, pr_head_sha, pr_base_sha, branch_match, base_match, None


def check_worktree_isolation(repo_root: Path) -> tuple[bool, str]:
    """Check if we're in an isolated worktree or a normal CI checkout.
    
    In GitHub Actions, the checkout is typically a detached HEAD with .git as directory.
    This is NOT a developer worktree - it's an ephemeral CI checkout.
    A developer worktree has .git as a file pointing to the main repo's .git directory.
    
    Returns (is_developer_worktree, path_description).
    """
    # Check if .git is a file (developer worktree) or directory (main repo or CI checkout)
    git_path = repo_root / ".git"
    is_developer_worktree = git_path.is_file()

    if is_developer_worktree:
        # Read the gitdir from the file
        with open(git_path, "r") as f:
            content = f.read().strip()
        if content.startswith("gitdir: "):
            worktree_path = content[8:].strip()
            return True, worktree_path

    # Not a linked developer worktree - could be main repo or CI detached checkout
    # In CI, this is normal and expected - return False with repo root
    return False, str(repo_root)


def find_nested_repos(repo_root: Path) -> List[str]:
    """Find any nested .git directories (accidental nested repositories)."""
    nested = []
    for git_dir in repo_root.rglob(".git"):
        # Skip the main .git
        if git_dir == repo_root / ".git":
            continue
        # Skip .git in node_modules, .kilo, etc.
        parts = git_dir.relative_to(repo_root).parts
        if any(skip in parts for skip in ["node_modules", ".kilo", "__pycache__", ".github"]):
            continue
        nested.append(str(git_dir.relative_to(repo_root)))
    return nested


def get_merge_base(repo_root: Path, base_sha: str, head_sha: str) -> Optional[str]:
    """Get the merge base commit between base and head SHAs."""
    result = run_git_command(["merge-base", base_sha, head_sha], repo_root)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_committed_diff(repo_root: Path, base_sha: str, head_sha: str) -> List[str]:
    """Get list of files changed in the committed diff (PR range), not just working tree.
    
    Uses merge-base semantics to correctly handle force-pushes and rebases.
    """
    if not base_sha or not head_sha:
        # Fallback to working tree changes
        return get_changed_files(repo_root)

    # First, get the merge base to handle rebases correctly
    merge_base = get_merge_base(repo_root, base_sha, head_sha)
    if merge_base:
        # Use merge-base..head for the actual PR diff
        result = run_git_command(["diff", "--name-only", f"{merge_base}..{head_sha}"], repo_root)
    else:
        # Fallback to base..head if merge-base fails
        result = run_git_command(["diff", "--name-only", f"{base_sha}..{head_sha}"], repo_root)
    
    changed = [f for f in result.stdout.strip().split('\n') if f]
    return sorted(set(changed))


def get_changed_files(repo_root: Path) -> List[str]:
    """Get list of changed files (staged and unstaged) - working tree."""
    # Staged
    result = run_git_command(["diff", "--cached", "--name-only"], repo_root)
    staged = [f for f in result.stdout.strip().split('\n') if f]

    # Unstaged
    result = run_git_command(["diff", "--name-only"], repo_root)
    unstaged = [f for f in result.stdout.strip().split('\n') if f]

    # Untracked
    result = run_git_command(["ls-files", "--others", "--exclude-standard"], repo_root)
    untracked = [f for f in result.stdout.strip().split('\n') if f]

    return sorted(set(staged + unstaged + untracked))


def check_unrelated_changes(changed_files: List[str]) -> List[str]:
    """Identify changes outside the purge preflight scope."""
    purge_prefixes = [
        ".github/scripts/",
        ".github/workflows/production-purge-preflight.yml",
        "backend/app/services/purge_preflight/",
        "backend/tests/test_purge_preflight.py",
        "backend/scripts/validate_snapshot_ids.py",
    ]

    unrelated = []
    for f in changed_files:
        if not any(f.startswith(p) for p in purge_prefixes):
            unrelated.append(f)
    return unrelated


def scan_for_secrets(repo_root: Path, changed_files: List[str]) -> List[dict]:
    """Scan changed files for potential secrets.
    
    Detects actual credential values, tokens, passwords, and credential-bearing URLs.
    Allows GitHub secrets expressions (${{ secrets.NAME }}) and environment variable
    references ($NAME, ${NAME}) as these are not actual secret values.
    Masks all matched values in reports.
    """
    secrets = []

    # Patterns that indicate a value is a reference/placeholder, not an actual secret
    placeholder_patterns = [
        r"\$\{\{\s*secrets\.",  # GitHub secrets: ${{ secrets.NAME }}
        r"\$\{\s*secrets\.",    # Alternative syntax
        r"\$\{[A-Z_][A-Z0-9_]*\}",  # Environment variable: ${VAR_NAME}
        r"\$[A-Z_][A-Z0-9_]*\b",    # Environment variable: $VAR_NAME
        r"YOUR_.*_HERE",        # Template placeholders
        r"REPLACE_ME",          # Template placeholders
        r"CHANGE_ME",           # Template placeholders
        r"dummy",               # Test/dummy values
        r"test",                # Test values (in context of URLs)
        r"example\.com",        # Example domains
        r"localhost",           # Localhost
        r"127\.0\.0\.1",        # Loopback
        r"0\.0\.0\.0",          # Bind all
        r"fake",                # Fake values
        r"placeholder",         # Placeholder keyword
    ]

    def is_placeholder(match_text: str, context_line: str) -> bool:
        """Check if a match appears to be a placeholder/reference rather than actual secret."""
        for pp in placeholder_patterns:
            if re.search(pp, context_line, re.IGNORECASE):
                if re.search(r"(secrets\.|YOUR_|REPLACE_|CHANGE_|dummy|test|example|localhost|fake|placeholder)", match_text, re.IGNORECASE):
                    return True
        return False

    for file_path in changed_files:
        full_path = repo_root / file_path
        if not full_path.exists() or not full_path.is_file():
            continue

        # Skip binary files
        try:
            content = full_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue

        for pattern, description in SECRET_PATTERNS:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Get line number and context
                line_no = content[:match.start()].count('\n') + 1
                line = content.split('\n')[line_no - 1].strip()
                
                # Skip if this looks like a placeholder/reference
                if is_placeholder(match.group(), line):
                    continue
                
                # Mask potential secrets in output
                masked_line = re.sub(pattern, "[REDACTED]", line)
                secrets.append({
                    "file": file_path,
                    "line": line_no,
                    "pattern": description,
                    "context": masked_line[:100]
                })

    return secrets


def check_purge_files_only(changed_files: List[str]) -> bool:
    """Verify changes are only to purge-related files.
    
    This is a precise allowlist of all file patterns that are intentionally
    part of the production purge preflight PR. Includes implementation,
    tests, CI configuration, documentation, and evidence files.
    """
    # Precise allowlist matching the actual intended scope of the PR
    purge_patterns = [
        # Workflow files
        r"^\.github/workflows/production-purge-preflight\.yml$",
        r"^\.github/workflows/ci\.yml$",
        
        # Gate implementation modules
        r"^backend/app/services/purge_preflight/.*\.py$",
        
        # CLI wrappers
        r"^\.github/scripts/gate[1-7]_.*\.py$",
        r"^\.github/scripts/purge_manifest\.py$",
        r"^\.github/scripts/summary\.py$",
        r"^\.github/scripts/check_preflight_status\.py$",
        
        # Tests
        r"^backend/tests/test_purge_preflight\.py$",
        
        # Validation scripts
        r"^backend/scripts/validate_snapshot_ids\.py$",
        
        # Documentation and evidence (intentionally included in PR)
        r"^gate[1-7]_.*\.md$",
        r"^gate[1-7]_.*\.sql$",
        r"^FINAL_DELIVERY_REPORT.*\.md$",
        r"^recovery_procedure\.md$",
        
        # Manifest and config
        r"^purge_manifest\.(json|md)$",
    ]

    for f in changed_files:
        if not any(re.match(p, f) for p in purge_patterns):
            return False
    return True


def check_production_mutation_risk(repo_root: Path, changed_files: List[str]) -> bool:
    """Check for patterns that could mutate production database.
    
    Inspects execution path and database target, not just SQL text.
    A test DELETE against an explicitly isolated disposable DB is not production mutation.
    A production-connected write is always a blocker.
    """
    risk_patterns = [
        r"DELETE\s+FROM\s+scholarships",
        r"DROP\s+TABLE",
        r"ALTER\s+TABLE.*DROP",
        r"TRUNCATE",
        r"pg_dump.*--clean",
        r"psql.*-c.*DELETE",
    ]

    for file_path in changed_files:
        full_path = repo_root / file_path
        if not full_path.exists() or not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue

        # Check if this file is test code using disposable/test database
        is_test_code = (
            "test" in file_path.lower() or
            "TEST_DATABASE_URL" in content or
            "connect_test" in content or
            "test_purge" in content or
            "disposable" in content.lower()
        )

        # Check if file connects to production database
        connects_to_production = (
            "SCHOLARZONE_DATABASE_URL" in content and "TEST_DATABASE_URL" not in content and
            "production" in content.lower()
        )

        # If it's test code with disposable DB, allow mutation patterns
        if is_test_code and not connects_to_production:
            continue

        # For non-test code or production-connected code, flag mutation patterns
        for pattern in risk_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
    return False


def check_deployment_risk(changed_files: List[str]) -> bool:
    """Check for deployment-related changes."""
    deploy_files = [
        "deploy.yml",
        "deploy.yaml",
        "Dockerfile",
        "docker-compose",
        "vercel.json",
        "netlify.toml",
        "render.yaml",
        "wrangler.toml",
    ]
    for f in changed_files:
        if any(df in f for df in deploy_files):
            return True
    return False


def get_repo_root() -> Path:
    """Get the repository root using git rev-parse --show-toplevel."""
    result = run_git_command(["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise RuntimeError(f"Failed to find repository root: {result.stderr}")
    return Path(result.stdout.strip())


def run_gate7() -> Gate7Result:
    """Execute Gate 7: Git Safety Verification."""
    result = Gate7Result()
    try:
        repo_root = get_repo_root()
    except RuntimeError as e:
        result.status = "ERROR"
        result.error = str(e)
        return result

    # 1. Check branch and base using PR SHAs
    current_branch, base_branch, pr_head_sha, pr_base_sha, branch_match, base_match, error = check_branch_and_base(repo_root)
    result.current_branch = current_branch
    result.base_branch = base_branch
    result.pr_head_sha = pr_head_sha
    result.pr_base_sha = pr_base_sha
    result.branch_match = branch_match
    result.base_match = base_match
    if error:
        result.status = "BLOCKED"
        result.error = error
        return result

    # 2. Ensure sufficient Git history for validation (fetch-depth: 0 in workflow)
    # Verify we can resolve required refs
    required_refs = ["origin/master", "HEAD"]
    if pr_base_sha:
        required_refs.append(pr_base_sha)
    if pr_head_sha:
        required_refs.append(pr_head_sha)
    history_ok, history_error = ensure_git_history(repo_root, required_refs)
    if not history_ok:
        result.status = "BLOCKED"
        result.error = f"Insufficient Git history: {history_error}"
        return result

    # 3. Check worktree isolation (informational - not required in CI)
    worktree_isolated, worktree_path = check_worktree_isolation(repo_root)
    result.worktree_isolated = worktree_isolated
    result.worktree_path = worktree_path

    # 4. Find nested repos
    result.nested_repos = find_nested_repos(repo_root)

    # 5. Get committed diff (PR range) - not just working tree
    result.changed_files = get_committed_diff(repo_root, pr_base_sha, pr_head_sha)

    # 6. Check unrelated changes
    result.unrelated_changes = check_unrelated_changes(result.changed_files)

    # 7. Scan for secrets in committed changes
    result.secrets_detected = scan_for_secrets(repo_root, result.changed_files)

    # 8. Check purge files only
    result.purge_files_only = check_purge_files_only(result.changed_files)

    # 9. Check production mutation risk (with repo_root for content inspection)
    result.production_mutation_risk = check_production_mutation_risk(repo_root, result.changed_files)

    # 10. Check deployment risk
    result.deployment_risk = check_deployment_risk(result.changed_files)

    # Determine overall status
    issues = []
    if not result.branch_match:
        issues.append(f"Branch mismatch: expected '{result.expected_branch}', got '{current_branch}' (or detached HEAD mismatch)")
    if not result.base_match:
        issues.append(f"Base branch mismatch: expected '{result.expected_base}' (PR base SHA must equal current origin/master)")
    if result.nested_repos:
        issues.append(f"Nested repositories detected: {result.nested_repos}")
    if result.unrelated_changes:
        issues.append(f"Unrelated changes: {result.unrelated_changes}")
    if result.secrets_detected:
        issues.append(f"Secrets detected in {len(result.secrets_detected)} locations")
    if not result.purge_files_only:
        issues.append("Changes include non-purge files")
    if result.production_mutation_risk:
        issues.append("Production mutation patterns detected (excluding test code with disposable DB)")
    if result.deployment_risk:
        issues.append("Deployment configuration changes detected")

    if issues:
        result.status = "FAIL"
        result.error = "; ".join(issues)
    else:
        result.status = "PASS"

    return result


def main() -> int:
    """CLI entry point for Gate 7."""
    print("=== GATE 7: GIT SAFETY VERIFICATION ===")
    print()

    result = run_gate7()

    # Save results with metadata
    save_result_with_metadata(result.to_dict(), "gate7", "gate7_result.json")

    print("\n=== GATE 7 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print("\n[PASS] GATE 7 PASSED: Git safety checks passed")
        return 0
    elif result.status == "BLOCKED":
        print(f"\n[BLOCKED] GATE 7 BLOCKED: {result.error}")
        return 2
    else:
        print(f"\n[FAIL] GATE 7 {result.status}: {result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())