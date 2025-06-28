import os


def get_env_required(name: str) -> str:
    """Retrieves the provided environment variable."""
    value = os.getenv(name, None)

    if value is None:
        raise ValueError(f"Environment variable '{name}' is required but not set")

    return value
