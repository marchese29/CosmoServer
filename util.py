import os
from enum import StrEnum


class InitItem[T]:
    """Convenient wrapper for items that are initialized during server startup"""

    def __init__(self):
        self._item: T | None = None

    def initialize(self, item: T):
        self._item = item

    def get(self) -> T:
        if self._item is None:
            raise AttributeError("InitItem was not initialized")
        return self._item


class EnvKey(StrEnum):
    """Environment Keys"""

    # Hubitat Configuration
    HUBITAT_ADDRESS = "HE_ADDRESS"
    HUBITAT_APP_ID = "HE_APP_ID"
    HUBITAT_TOKEN = "HE_ACCESS_TOKEN"

    # Agent Configuration
    MODEL_ID = "DEFAULT_BEDROCK_MODEL_ID"


def get_env_required(key: EnvKey) -> str:
    """Retrieves the provided environment variable."""
    value = os.getenv(key.value, None)

    if value is None:
        raise ValueError(f"Environment variable '{key.value}' is required but not set")

    return value
