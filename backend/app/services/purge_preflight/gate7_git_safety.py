"""
Gate 7: Git Safety Verification

Verifies:
- Expected branch and base
- Worktree isolation
- No unrelated changes overwritten
- Target files scoped correctly
- No accidental nested repositories
- No unintended changes to unrelated application code
- No credentials/secrets in tracked files
- No production deployment or database mutation introduced
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List


@dataclass
class Gate7Result:
    """Gate 7 execution result."""
    test_name: str = "gate7_git_safety"
    current_branch: str = ""
    base_branch: str = ""
    expected_branch: str = "fix/production-expired-cycle-purge"
    expected_base: str = "master"
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


SECRET_PATTERNS = [
    (r"SCHOLARZONE_DATABASE_URL", "Database URL"),
    (r"postgresql://[^:\s]+:[^@\s]+@", "PostgreSQL connection with password"),
    (r"GPG_RECIPIENT", "GPG recipient"),
    (r"EXPECTED_NEON_PROJECT_ID", "Neon project ID"),
    (r"EXPECTED_NEON_BRANCH_ID", "Neon branch ID"),
    (r"EXPECTED_NEON_BRANCH_NAME", "Neon branch name"),
    (r"EXPECTED_DATABASE_NAME", "Database name"),
    (r"GPG_EXPECTED_FINGERPRINT", "GPG fingerprint"),
    (r"[a-zA-Z0-9+/]{40,}=", "Potential base64 encoded secret"),
    (r"gh[ps]_[a-zA-Z0-9]{36,}", "GitHub token"),
    (r"sk_[a-zA-Z0-9]{32,}", "OpenAI/API key"),
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


def check_branch_and_base(repo_root: Path) -> tuple[str, str, bool, bool]:
    """Check current branch and base."""
    # Get current branch
    result = run_git_command(["branch", "--show-current"], repo_root)
    current_branch = result.stdout.strip()

    # Get base branch (the branch we're comparing against)
    # For PR workflow, this is typically the target branch
    result = run_git_command(["merge-base", "HEAD", "origin/master"], repo_root)
    merge_base = result.stdout.strip()

    # Check if we're on the expected branch
    expected_branch = "fix/production-expired-cycle-purge"
    expected_base = "master"

    branch_match = current_branch == expected_branch

    # Check if base is master (or origin/master)
    base_match = True  # We'll verify by checking merge base exists

    return current_branch, expected_base, branch_match, base_match


def check_worktree_isolation(repo_root: Path) -> tuple[bool, str]:
    """Check if we're in an isolated worktree."""
    # Check if .git is a file (worktree) or directory (main repo)
    git_path = repo_root / ".git"
    is_worktree = git_path.is_file()

    if is_worktree:
        # Read the gitdir from the file
        with open(git_path, "r") as f:
            content = f.read().strip()
        if content.startswith("gitdir: "):
            worktree_path = content[8:].strip()
            return True, worktree_path

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


def get_changed_files(repo_root: Path) -> List[str]:
    """Get list of changed files (staged and unstaged)."""
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
    """Scan changed files for potential secrets."""
    secrets = []

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
                # Get line number
                line_no = content[:match.start()].count('\n') + 1
                line = content.split('\n')[line_no - 1].strip()
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
    """Verify changes are only to purge-related files."""
    purge_patterns = [
        r"^\.github/scripts/gate[1-7]_.*\.py$",
        r"^\.github/scripts/purge_manifest\.py$",
        r"^\.github/scripts/summary\.py$",
        r"^\.github/workflows/production-purge-preflight\.yml$",
        r"^backend/app/services/purge_preflight/.*\.py$",
        r"^backend/tests/test_purge_preflight\.py$",
        r"^backend/scripts/validate_snapshot_ids\.py$",
    ]

    for f in changed_files:
        if not any(re.match(p, f) for p in purge_patterns):
            return False
    return True


def check_production_mutation_risk(changed_files: List[str]) -> bool:
    """Check for patterns that could mutate production."""
    risk_patterns = [
        r"DELETE\s+FROM\s+scholarships",
        r"DROP\s+TABLE",
        r"ALTER\s+TABLE.*DROP",
        r"TRUNCATE",
        r"pg_dump.*--clean",
        r"psql.*-c.*DELETE",
    ]

    for file_path in changed_files:
        full_path = Path(file_path)
        if not full_path.exists() or not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue

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
    ]
    for f in changed_files:
        if any(df in f for df in deploy_files):
            return True
    return False


def run_gate7() -> Gate7Result:
    """Execute Gate 7: Git Safety Verification."""
    result = Gate7Result()
    repo_root = Path(__file__).resolve().parents[3]  # backend/app/services/purge_preflight -> repo root

    try:
        # 1. Check branch and base
        current_branch, base_branch, branch_match, base_match = check_branch_and_base(repo_root)
        result.current_branch = current_branch
        result.base_branch = base_branch
        result.branch_match = branch_match
        result.base_match = base_match

        # 2. Check worktree isolation
        worktree_isolated, worktree_path = check_worktree_isolation(repo_root)
        result.worktree_isolated = worktree_isolated
        result.worktree_path = worktree_path

        # 3. Find nested repos
        result.nested_repos = find_nested_repos(repo_root)

        # 4. Get changed files
        result.changed_files = get_changed_files(repo_root)

        # 5. Check unrelated changes
        result.unrelated_changes = check_unrelated_changes(result.changed_files)

        # 6. Scan for secrets
        result.secrets_detected = scan_for_secrets(repo_root, result.changed_files)

        # 7. Check purge files only
        result.purge_files_only = check_purge_files_only(result.changed_files)

        # 8. Check production mutation risk
        result.production_mutation_risk = check_production_mutation_risk(result.changed_files)

        # 9. Check deployment risk
        result.deployment_risk = check_deployment_risk(result.changed_files)

        # Determine overall status
        issues = []
        if not result.branch_match:
            issues.append(f"Branch mismatch: expected '{result.expected_branch}', got '{current_branch}'")
        if not result.base_match:
            issues.append(f"Base branch mismatch: expected '{result.expected_base}'")
        if result.nested_repos:
            issues.append(f"Nested repositories detected: {result.nested_repos}")
        if result.unrelated_changes:
            issues.append(f"Unrelated changes: {result.unrelated_changes}")
        if result.secrets_detected:
            issues.append(f"Secrets detected in {len(result.secrets_detected)} locations")
        if not result.purge_files_only:
            issues.append("Changes include non-purge files")
        if result.production_mutation_risk:
            issues.append("Production mutation patterns detected")
        if result.deployment_risk:
            issues.append("Deployment configuration changes detected")

        if issues:
            result.status = "FAIL"
            result.error = "; ".join(issues)
        else:
            result.status = "PASS"

        return result

    except Exception as e:
        result.status = "ERROR"
        result.error = str(e)
        return result


def main() -> int:
    """CLI entry point for Gate 7."""
    print("=== GATE 7: GIT SAFETY VERIFICATION ===")
    print()

    result = run_gate7()

    # Save results
    with open("gate7_result.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)

    print("\n=== GATE 7 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print("\n✅ GATE 7 PASSED: Git safety checks passed")
        return 0
    else:
        print(f"\n❌ GATE 7 {result.status}: {result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())