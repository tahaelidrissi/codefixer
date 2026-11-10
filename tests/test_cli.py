import os

import pytest

from codefixer.cli import _parse_args, main


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
