import os
import re
from enum import StrEnum
from typing import Protocol, Self, runtime_checkable


class InitItem[T]:
    """Convenient wrapper for items that are initialized during server startup"""

    def __init__(self):
        self._item: T | None = None

    def initialize(self, item: T):
        self._item = item

    def get(self) -> T:
        assert self._item is not None
        return self._item


@runtime_checkable
class AsyncCreatable(Protocol):
    """Defines a class that can be instantiated by invoking an async 'create' method"""

    @classmethod
    async def create(cls: type[Self]) -> Self: ...


class EnvKey(StrEnum):
    """Environment Keys"""

    # Hubitat Configuration
    HUBITAT_ADDRESS = "HE_ADDRESS"
    HUBITAT_APP_ID = "HE_APP_ID"
    HUBITAT_TOKEN = "HE_ACCESS_TOKEN"

    # Agent Configuration
    MODEL_ID = "DEFAULT_BEDROCK_MODEL_ID"
    SIMPLE_MODEL_ID = "SIMPLE_BEDROCK_MODEL_ID"


def get_env_required(key: EnvKey) -> str:
    """Retrieves the provided environment variable."""
    value = os.getenv(key.value, None)

    if value is None:
        raise ValueError(f"Environment variable '{key.value}' is required but not set")

    return value


def strip_xml_tags(text: str, tag_name: str = "thinking") -> str:
    """
    Strips content between and including XML-like tags from a string.

    Args:
        text: The input string to process
        tag_name: The name of the XML tag to strip (default: "reasoning")

    Returns:
        The string with all content between and including the specified tags removed

    Example:
        >>> strip_xml_tags("Hello <reasoning>some thoughts</reasoning> world")
        "Hello  world"
        >>> strip_xml_tags("Text <custom>remove this</custom> more", "custom")
        "Text  more"
    """
    # Create regex pattern to match opening tag, content, and closing tag
    # re.DOTALL makes . match newlines as well
    pattern = rf"<{re.escape(tag_name)}>.*?</{re.escape(tag_name)}>"
    return re.sub(pattern, "", text, flags=re.DOTALL)
