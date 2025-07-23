import argparse
import asyncio
import os

from coagent.core import (
    AgentSpec,
    BaseAgent,
    Context,
    handler,
    init_logger,
    Message,
    new,
)
from coagent.core.exceptions import InternalError
from coagent.runtimes import LocalRuntime
from jinja2 import Template
from pydantic import BaseModel


class MCPServer(BaseModel):
    name: str
    url: str


class AgentMetadata(BaseModel):
    name: str
    description: str
    prompt: str = ""
    mcp_servers: list[MCPServer] | None = None
    plugins: list[str] | None = None


class Requirement(Message):
    data: AgentMetadata | None = None
    text: str | None = None


class File(BaseModel):
    name: str
    content: str

    def __str__(self) -> str:
        return f"--> {self.name}\n{self.content}"

    def save(self, out: str) -> None:
        filename = os.path.join(out, self.name)
        with open(filename, "w+") as f:
            f.write(self.content)


class Artifact(Message):
    agent_file: File
    pyproject_file: File
    init_file: File
    main_file: File | None = None
    env_file: File
    readme_file: File


AGENT_TEMPLATE = '''\
import os

from coagent.agents import ChatAgent, Model
{%- if mcp_servers %}
from coagent.agents.mcp_server import (
    Connect,
    MCPServer,
    MCPServerSSEParams,
    NamedMCPServer,
)
{%- endif %}
from coagent.core import AgentSpec, new
from dotenv import load_dotenv


load_dotenv()

model = Model(
    id=os.getenv('MODEL_ID'),
    base_url=os.getenv('MODEL_BASE_URL'),
    api_key=os.getenv("MODEL_API_KEY"),
)


{%- if mcp_servers %}


# The agent for managing MCP servers
mcp_server_agent = AgentSpec("mcp_server", new(MCPServer))
{%- endif %}


# The main agent
class Agent(ChatAgent):
    """{{ description }}"""

    system = "{{ prompt }}"
    model = model
    {%- if mcp_servers %}
    mcp_servers = [
        {%- for server in mcp_servers %}
        NamedMCPServer(
            name="{{ server.name }}",
            connect=Connect(
                transport="sse",
                params=MCPServerSSEParams(
                    url="{{ server.url }}"
                )
            ),
        ),
        {%- endfor %}
    ]
    mcp_server_agent_type = mcp_server_agent.name
    {%- endif %}


{{ name }} = AgentSpec("{{ name }}", new(Agent))
'''

ENTRYPOINT_TEMPLATE = """\
"""

PYPROJECT_TEMPLATE = """\
[project]
name = "{{ name }}"
version = "{{ version }}"
description = "{{ description }}"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "python-dotenv>=1.1.0",
    "coagent-python[a2a] @ git+https://github.com/OpenCSGs/coagent.git@2a00e4f2ef9d4d09488f36402a291e12b1753642",
    "grpcio>=1.73.1",
    "protobuf>=6.31.1",
    "google-api-python-client>=2.176.0",
    "hypercorn>=0.17.3",
    "python-telegram-bot>=22.2",
]

[tool.hatch.build.targets.wheel]
packages = ["."]

[tool.hatch.metadata]
allow-direct-references = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

MAIN_FILE = """\
import asyncio

{%- if mcp_servers %}
from coagent.agents.mcp_server import MCPServer
{%- endif %}
from coagent.core import AgentSpec, init_logger, new
from coagent.runtimes import LocalRuntime
from coagent_web3 import Application
{%- for plugin in plugins %}
from coagent_web3.plugins import {{ plugin }}
{%- endfor %}

from {{ name }} import {{ name }}

{% if mcp_servers -%}
mcp_server = AgentSpec("mcp_server", new(MCPServer))
{%- endif %}


async def main() -> None:
    async with LocalRuntime() as runtime:
        {%- if mcp_servers %}
        await runtime.register(mcp_server)
        {%- endif %}
        await runtime.register({{ name }})

        app = Application()
        {%- for plugin in plugins %}
        await app.register({{ plugin }}.Plugin(runtime, {{ name }}))
        {%- endfor %}
        await app.run()


if __name__ == "__main__":
    init_logger("DEBUG")
    asyncio.run(main())
"""

ENV_FILE = """\
MODEL_ID=<your-model-id>
MODEL_BASE_URL=<your-model-base-url>
MODEL_API_KEY=<your-model-api-key>
"""

README_TEMPLATE = """\
# {{ name }}

{{ description }}


## Getting started

```bash
uv run .
```
"""


class Builder(BaseAgent):
    """An agent who is committed to build agents, based on user's requirement."""

    @handler
    async def build(self, msg: Requirement, ctx: Context) -> Artifact:
        if not msg.json:
            raise InternalError("json requirement is required")

        data = msg.data
        name = data.name.replace(" ", "_").replace(" ", "_").lower()

        agent_file = File(
            name=f"{name}.py",
            content=Template(AGENT_TEMPLATE).render(
                name=name,
                description=data.description,
                prompt=data.prompt or data.description,
                mcp_servers=data.mcp_servers,
            ),
        )
        pyproject_file = File(
            name="pyproject.toml",
            content=Template(PYPROJECT_TEMPLATE).render(
                name=name,
                version="0.1.0",
                description=data.description,
            ),
        )
        init_file = File(
            name="__init__.py",
            content="",
        )

        main_file = None
        if data.plugins:
            main_file = File(
                name="__main__.py",
                content=Template(MAIN_FILE).render(
                    name=name, plugins=data.plugins, mcp_servers=data.mcp_servers
                ),
            )
        env_file = File(
            name=".env",
            content=ENV_FILE,
        )
        readme_file = File(
            name="README.md",
            content=Template(README_TEMPLATE).render(
                name=name, description=data.description
            ),
        )

        return Artifact(
            agent_file=agent_file,
            pyproject_file=pyproject_file,
            init_file=init_file,
            main_file=main_file,
            env_file=env_file,
            readme_file=readme_file,
        )


builder = AgentSpec("builder", new(Builder))


async def run(req: Requirement, out: str) -> None:
    async with LocalRuntime() as runtime:
        await runtime.register(builder)

        result = await builder.run(req.encode())
        msg = Artifact.decode(result)

        msg.agent_file.save(out)
        msg.pyproject_file.save(out)
        msg.env_file.save(out)
        msg.init_file.save(out)
        if msg.main_file:
            msg.main_file.save(out)
        msg.readme_file.save(out)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an agent based on user's requirement."
    )
    parser.add_argument(
        "--character", required=True, type=str, help="The character file of the agent"
    )
    parser.add_argument(
        "--out", type=str, default=".", help="Output directory for generated files"
    )
    args = parser.parse_args()

    with open(args.character, "r") as f:
        character = f.read()
    metadata = AgentMetadata.model_validate_json(character)
    req = Requirement(data=metadata)

    out = args.out
    os.makedirs(out, exist_ok=True)

    await run(req, out)


if __name__ == "__main__":
    init_logger()
    asyncio.run(main())
