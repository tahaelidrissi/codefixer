from codefixer.agent.github_client import cloned_repo


def test_clones_a_real_public_repo():
    with cloned_repo("https://github.com/octocat/Hello-World.git") as workdir:
        assert (workdir / "README").exists()

    assert not workdir.exists()
