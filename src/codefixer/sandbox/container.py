import difflib
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

IMAGE = "codefixer-sandbox"


@contextmanager
def sandboxed_repo(repo_path: Path, image: str = IMAGE) -> Iterator[str]:
    """Creates a container from the sandbox image, copies `repo_path` into
    it at /repo, and yields the container id so the caller can run
    commands in it with `docker exec`. The container always gets removed on
    exit, even if the caller raises.

    The host repo is never mounted - only a copy goes in via `docker cp` -
    so nothing the container does can reach the real filesystem.
    """
    container_id = subprocess.run(
        ["docker", "create", image, "sleep", "infinity"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        subprocess.run(["docker", "cp", f"{repo_path}/.", f"{container_id}:/repo"], check=True)
        subprocess.run(["docker", "start", container_id], check=True, capture_output=True)
        # docker cp always writes as root, regardless of the image's default
        # user - without this, the non-root `sandbox` user the container
        # actually runs as can't edit the files it was just given.
        subprocess.run(
            ["docker", "exec", "--user", "root", container_id, "chown", "-R", "sandbox:sandbox", "/repo"],
            check=True,
            capture_output=True,
        )
        yield container_id
    finally:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True)


def copy_repo_out(container_id: str, destination: Path) -> None:
    """Copies the container's /repo back out, e.g. to compare it against
    the original and compute a diff."""
    subprocess.run(["docker", "cp", f"{container_id}:/repo/.", str(destination)], check=True)


def diff_repos(original: Path, modified: Path) -> str:
    """A unified diff between two directory trees, file by file. Not a git
    diff: the target repo isn't guaranteed to be a git repository.
    Binary/undecodable files are reported as changed without their content.
    """
    original_files = {p.relative_to(original) for p in original.rglob("*") if p.is_file()}
    modified_files = {p.relative_to(modified) for p in modified.rglob("*") if p.is_file()}

    chunks = []
    for rel_path in sorted(original_files | modified_files):
        before_path = original / rel_path
        after_path = modified / rel_path
        try:
            before = before_path.read_text(encoding="utf-8").splitlines(keepends=True) if rel_path in original_files else []
            after = after_path.read_text(encoding="utf-8").splitlines(keepends=True) if rel_path in modified_files else []
        except UnicodeDecodeError:
            if (rel_path in original_files) != (rel_path in modified_files) or before_path.read_bytes() != after_path.read_bytes():
                chunks.append(f"Binary file {rel_path} changed\n")
            continue

        if before != after:
            chunks.extend(difflib.unified_diff(before, after, fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}"))

    return "".join(chunks)
