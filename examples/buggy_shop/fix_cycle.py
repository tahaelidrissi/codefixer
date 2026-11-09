"""Drives the ReAct loop (run_tests -> search_code -> read_file -> edit_file -> run_tests)
by hand, with no LLM, to prove the workspace tools are enough to fix this example's bug."""

import os
import sys
from pathlib import Path

os.environ["CODEFIXER_WORKSPACE"] = str(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from codefixer.servers import workspace  # noqa: E402


def main() -> None:
    print("1. run_tests: reproduce the bug", file=sys.stderr)
    output = workspace.run_tests(".")
    print(output, file=sys.stderr)
    assert "1 failed" in output

    print("2. search_code: locate the buggy function", file=sys.stderr)
    matches = workspace.search_code("calculate_discount")
    print(matches, file=sys.stderr)

    print("3. read_file: inspect it", file=sys.stderr)
    content = workspace.read_file("shop.py")
    print(content, file=sys.stderr)

    print("4. edit_file: fix the bug", file=sys.stderr)
    result = workspace.edit_file("shop.py", "price * rate / 10", "price * rate / 100")
    print(result, file=sys.stderr)

    print("5. run_tests: verify the fix", file=sys.stderr)
    output = workspace.run_tests(".")
    print(output, file=sys.stderr)
    assert "1 passed" in output

    print("Fix cycle succeeded.", file=sys.stderr)


if __name__ == "__main__":
    main()
