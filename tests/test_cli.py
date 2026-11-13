import os

import pytest

from codefixer.cli import _parse_args, _resolve_skills_dirs, main
from codefixer.skills.loader import SKILLS_DIR


def test_resolve_skills_dirs_is_just_the_builtin_ones_by_default(tmp_path):
    assert _resolve_skills_dirs(str(tmp_path)) == [SKILLS_DIR]


def test_resolve_skills_dirs_adds_the_repos_own_skills_if_present(tmp_path):
    (tmp_path / ".codefixer" / "skills").mkdir(parents=True)

    assert _resolve_skills_dirs(str(tmp_path)) == [SKILLS_DIR, tmp_path / ".codefixer" / "skills"]


def test_parse_args_fix_defaults():
    args = _parse_args(["fix", "some/repo", "There's a bug."])

    assert args.command == "fix"
    assert args.repo == "some/repo"
    assert args.problem == "There's a bug."
    assert args.model == "claude-opus-5-5"
    assert args.max_turns == 25


def test_parse_args_fix_overrides():
    args = _parse_args(["fix", "some/repo", "There's a bug.", "--model", "groq:x", "--max-turns", "5"])

    assert args.model == "groq:x"
    assert args.max_turns == 5


def test_parse_args_fix_issue_defaults():
    args = _parse_args(["fix-issue", "https://github.com/owner/repo/issues/42"])

    assert args.command == "fix-issue"
    assert args.issue_url == "https://github.com/owner/repo/issues/42"
    assert args.model == "claude-opus-5-5"
    assert args.max_turns == 25


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY")
def test_cli_fixes_the_buggy_shop_bug(tmp_path, capsys):
    (tmp_path / "shop.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )
    (tmp_path / "test_shop.py").write_text(
        "from shop import calculate_discount\n\n\n"
        "def test_calculate_discount():\n"
        "    assert calculate_discount(100, 10) == 10\n",
        encoding="utf-8",
    )

    main(
        [
            "fix",
            str(tmp_path),
            "There's a failing test in this repository. Fix it.",
            "--model",
            "groq:openai/gpt-oss-120b",
        ]
    )

    output = capsys.readouterr().out
    assert "Tests passed: True" in output
    assert "price * rate / 100" in (tmp_path / "shop.py").read_text(encoding="utf-8")


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY")
def test_cli_reports_turn_limit_cleanly(tmp_path, capsys):
    (tmp_path / "shop.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )
    (tmp_path / "test_shop.py").write_text(
        "from shop import calculate_discount\n\n\n"
        "def test_calculate_discount():\n"
        "    assert calculate_discount(100, 10) == 10\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "fix",
                str(tmp_path),
                "There's a failing test in this repository. Fix it.",
                "--model",
                "groq:openai/gpt-oss-120b",
                "--max-turns",
                "1",
            ]
        )

    assert exc_info.value.code == 1
    assert "Gave up after 1 turns" in capsys.readouterr().err
