import subprocess
from typing import Any, Dict

from .base import Atom, AtomConfig, AtomResult, AtomStatus


class GitCommitAtomConfig(AtomConfig):
    message: str = "Auto-commit by FlowManager"


class GitCommitAtom(Atom):
    """
    GitCommitAtom (State Checkpointing).
    Commits the current project state to a local Git repository.
    """

    def _parse_config(self, config: Dict[str, Any]) -> GitCommitAtomConfig:
        return GitCommitAtomConfig(**config)

    def run(self, context: Dict[str, Any]) -> AtomResult:
        from typing import cast

        config = cast(GitCommitAtomConfig, self.config)
        commit_message = config.message  # Use config.message as per GitCommitAtomConfig
        repo_path = context.get("__root__", ".")

        try:
            # Check if there are changes
            status_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=True,
            )

            if not status_res.stdout.strip():
                # No changes to commit, yielding success (idempotent behavior)
                return AtomResult(AtomStatus.SUCCESS, "No changes to commit")

            subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True)

            subprocess.run(
                ["git", "commit", "-m", commit_message], cwd=str(repo_path), check=True
            )

            return AtomResult(
                AtomStatus.SUCCESS, f"Created git commit: {commit_message}"
            )

        except subprocess.CalledProcessError as e:
            return AtomResult(
                AtomStatus.FAILED, f"Git operation failed: {e.stderr or e.stdout}"
            )
        except FileNotFoundError:
            return AtomResult(AtomStatus.FAILED, "Git executable not found in PATH")
