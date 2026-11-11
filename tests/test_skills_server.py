import pytest

from codefixer.servers import skills

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_lists_the_three_skills_as_resources():
    resources = await skills.mcp.list_resources()

    uris = {str(resource.uri) for resource in resources}
    assert uris == {
        "skill://write-pytest-test",
        "skill://debug-import-error",
        "skill://repo-conventions",
    }


async def test_reads_a_skill_resources_full_content():
    contents = list(await skills.mcp.read_resource("skill://write-pytest-test"))

    assert len(contents) == 1
    text = contents[0].content
    assert text.startswith("---\nname: write-pytest-test")
    assert "## Method" in text
