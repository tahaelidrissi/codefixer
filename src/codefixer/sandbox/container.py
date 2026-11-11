import difflib
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

IMAGE = "codefixer-sandbox"
DEFAULT_CPUS = "1"
DEFAULT_MEMORY = "512m"
DEFAULT_EXEC_TIMEOUT_SECONDS = 60


def _chown_repo_to_sandbox(container_id: str) -> None:
    # docker cp always writes as root, regardless of the image's default
    # user - without this, the non-root `sandbox` user can't edit the files
    # it was just given.
    subprocess.run(
        ["docker", "exec", "--user", "root", container_id, "chown", "-R", "sandbox:sandbox", "/repo"],
        check=True,
        capture_output=True,
    )


def _load_repo_into_volume(repo_path: Path, volume_name: str, image: str) -> None:
    """Copies `repo_path` into a Docker-managed volume through a throwaway,
    writable container - never through the real sandboxed one, since
    `docker cp` refuses outright to write into a --read-only container."""
    loader_id = subprocess.run(
        [
            "docker",
            "create",
            "--mount",
            f"type=volume,source={volume_name},target=/repo",
            image,
            "sleep",
            "infinity",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        subprocess.run(["docker", "start", loader_id], check=True, capture_output=True)
        subprocess.run(["docker", "cp", f"{repo_path}/.", f"{loader_id}:/repo"], check=True)
        _chown_repo_to_sandbox(loader_id)
    finally:
        subprocess.run(["docker", "rm", "-f", loader_id], capture_output=True)


@contextmanager
def sandboxed_repo(
    repo_path: Path,
    image: str = IMAGE,
    cpus: str = DEFAULT_CPUS,
    memory: str = DEFAULT_MEMORY,
) -> Iterator[str]:
    """Creates a container from the sandbox image, copies `repo_path` into
    it at /repo, and yields the container id so the caller can run
    commands in it with `docker exec` (or `exec_in_container`, below, for a
    time limit). The container always gets removed on exit, even if the
    caller raises.

    The host repo is never mounted - only a copy goes in - so nothing the
    container does can reach the real filesystem. The container also has
    no network access and capped CPU/memory, and its root filesystem is
    read-only except /repo and /tmp (wiped when the container is
    destroyed): even a hostile or buggy test can't exfiltrate anything, hog
    resources, or write outside its own sandbox.

    /repo lives on a Docker-managed volume rather than the container's own
    filesystem, because `docker cp` refuses outright to write into a
    --read-only container - the repo is loaded into that volume through a
    separate, throwaway writable container (`_load_repo_into_volume`)
    before this one even starts. The volume is still never the host's
    actual repo path.
    """
    volume_name = subprocess.run(
        ["docker", "volume", "create"], capture_output=True, text=True, check=True
    ).stdout.strip()
    try:
        _load_repo_into_volume(repo_path, volume_name, image)

        container_id = subprocess.run(
            [
                "docker",
                "create",
                "--network",
                "none",
                "--cpus",
                cpus,
                "--memory",
                memory,
                "--read-only",
                "--tmpfs",
                "/tmp:exec,uid=1000,gid=1000",
                "--mount",
                f"type=volume,source={volume_name},target=/repo",
                image,
                "sleep",
                "infinity",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        try:
            subprocess.run(["docker", "start", container_id], check=True, capture_output=True)
            yield container_id
        finally:
            subprocess.run(["docker", "rm", "-f", container_id], capture_output=True)
    finally:
        subprocess.run(["docker", "volume", "rm", "-f", volume_name], capture_output=True)


def exec_in_container(
    container_id: str, *command: str, timeout_seconds: int = DEFAULT_EXEC_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """Runs a command inside the container, killed after `timeout_seconds`.

    The timeout is enforced by coreutils' own `timeout`, run inside the
    container - killing the host-side `docker exec` client wouldn't
    necessarily kill the process it started inside the container.
    """
    return subprocess.run(
        ["docker", "exec", container_id, "timeout", "--signal=KILL", str(timeout_seconds), *command],
        capture_output=True,
        text=True,
    )


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
