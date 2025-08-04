from enum import Enum
from typing import cast

from mcp import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPAgentTool, MCPClient

from . import util
from .util import EnvKey


class MCPServer(Enum):
    """The different MCP servers we support"""

    HUBITAT = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uvx",
                args=[
                    "--from",
                    "git+https://github.com/marchese29/HubitatAutomationMCP",
                    "he-mcp",
                ],
                env={
                    "HE_ADDRESS": util.get_env_required(EnvKey.HUBITAT_ADDRESS),
                    "HE_APP_ID": util.get_env_required(EnvKey.HUBITAT_APP_ID),
                    "HE_ACCESS_TOKEN": util.get_env_required(EnvKey.HUBITAT_TOKEN),
                },
            )
        )
    )
    RULES = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uvx",
                args=[
                    "--from",
                    "git+https://github.com/marchese29/HubitatRulesMCP",
                    "hubitat-rules",
                ],
                env={
                    "HE_ADDRESS": util.get_env_required(EnvKey.HUBITAT_ADDRESS),
                    "HE_APP_ID": util.get_env_required(EnvKey.HUBITAT_APP_ID),
                    "HE_ACCESS_TOKEN": util.get_env_required(EnvKey.HUBITAT_TOKEN),
                },
            )
        )
    )

    def client(self) -> MCPClient:
        return cast(MCPClient, self.value)

    def tools(self) -> list[MCPAgentTool]:
        return cast(MCPClient, self.value).list_tools_sync()
