import shutil
import subprocess
from pathlib import Path

import pytest

SANDBOX_DIR = Path(__file__).resolve().parents[1] / "src" / "codefixer" / "sandbox"
IMAGE_TAG = "codefixer-sandbox-test"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(not _docker_available(), reason="Docker is not available")


@pytest.fixture(scope="module")
def built_image() -> str:
    subprocess.run(["docker", "build", "-t", IMAGE_TAG, str(SANDBOX_DIR)], check=True, capture_output=True)
    return IMAGE_TAG


def _run(image: str, *args: str) -> str:
    result = subprocess.run(["docker", "run", "--rm", image, *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def test_sandbox_image_runs_as_a_non_root_user(built_image):
    assert _run(built_image, "whoami") == "sandbox"


def test_sandbox_image_has_pytest_available(built_image):
    assert "pytest" in _run(built_image, "pytest", "--version")
