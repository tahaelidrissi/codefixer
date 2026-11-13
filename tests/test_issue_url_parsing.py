import pytest

from codefixer.agent.github_client import parse_issue_url


def test_parses_owner_repo_and_number():
    assert parse_issue_url("https://github.com/github/github-mcp-server/issues/1") == (
        "github",
        "github-mcp-server",
        1,
    )


def test_parses_with_trailing_slash():
    assert parse_issue_url("https://github.com/owner/repo/issues/42/") == ("owner", "repo", 42)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner/repo/pull/42",
        "https://github.com/owner/repo",
        "not a url",
        "https://gitlab.com/owner/repo/issues/1",
    ],
)
def test_rejects_non_issue_urls(url):
    with pytest.raises(ValueError):
        parse_issue_url(url)
