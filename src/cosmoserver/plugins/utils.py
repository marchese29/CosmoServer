"""Utilities for plugin management and bundled environment generation."""

import asyncio
import copy
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ..database.models import Plugin


class PluginDependencyConflictError(Exception):
    """Raised when plugin dependencies cannot be resolved."""

    def __init__(self, message: str, uv_error: str | None = None):
        super().__init__(message)
        self.uv_error = uv_error


def find_pyproject_toml(start_path: Path | None = None) -> Path:
    """Find pyproject.toml by recursing up from start_path or current directory."""
    current = start_path or Path.cwd()

    while current != current.parent:  # Stop at filesystem root
        # Check for original first (clean slate preference)
        original_path = current / "pyproject.original.toml"
        if original_path.exists():
            return original_path

        # Fall back to regular pyproject.toml
        pyproject_path = current / "pyproject.toml"
        if pyproject_path.exists():
            return pyproject_path
        current = current.parent

    raise FileNotFoundError(
        "Could not find pyproject.toml or pyproject.original.toml in current "
        "directory or parents"
    )


def load_server_config(start_path: Path | None = None) -> dict:
    """Load and parse the main pyproject.toml."""
    pyproject_path = find_pyproject_toml(start_path)

    with open(pyproject_path) as f:
        return tomlkit.parse(f.read())


def format_pypi_dependency(plugin: "Plugin") -> str:
    """Format PyPI plugin as dependency string."""
    version = plugin.updated_version or plugin.installed_version
    if version:
        return f"{plugin.source}=={version}"
    else:
        return plugin.source


def add_git_source(config: dict, plugin: "Plugin") -> None:
    """Add git plugin to tool.uv.sources section."""
    # Ensure tool.uv.sources exists
    if "tool" not in config:
        config["tool"] = {}
    if "uv" not in config["tool"]:
        config["tool"]["uv"] = {}
    if "sources" not in config["tool"]["uv"]:
        config["tool"]["uv"]["sources"] = {}

    # Create git source entry
    git_source = {"git": plugin.source}

    # Add version/branch if specified
    version = plugin.updated_version or plugin.installed_version
    if version:
        # Use branch for git versioning
        git_source["branch"] = version

    # Use python_package_name if available, otherwise fallback to plugin name
    package_name = plugin.python_package_name or plugin.name
    config["tool"]["uv"]["sources"][package_name] = git_source


def generate_bundled_config(plugins: list["Plugin"], bundled_path: Path) -> None:
    """Generate pyproject.toml with plugin dependencies at the specified path."""
    # Load main server configuration, starting search from bundle path
    config = load_server_config(bundled_path.parent)

    # Create a deep copy to avoid modifying original
    bundled_config = copy.deepcopy(config)

    # Change project name
    bundled_config["project"]["name"] = "cosmo-server-bundled"

    # Get existing git sources to avoid duplicates (UV handles dependency duplicates)
    existing_sources = set()
    if (
        "tool" in bundled_config
        and "uv" in bundled_config["tool"]
        and "sources" in bundled_config["tool"]["uv"]
    ):
        existing_sources = set(bundled_config["tool"]["uv"]["sources"].keys())

    # Process each plugin
    for plugin in plugins:
        if plugin.source_type.value == "pypi":
            # Add PyPI plugin to dependencies (UV will handle duplicates)
            dependency = format_pypi_dependency(plugin)
            bundled_config["project"]["dependencies"].append(dependency)

        elif plugin.source_type.value == "git":
            # Use python_package_name if available, otherwise fallback to plugin name
            package_name = plugin.python_package_name or plugin.name

            # Only add git plugin if not already in sources
            if package_name not in existing_sources:
                # Add package name to dependencies
                bundled_config["project"]["dependencies"].append(package_name)

                # Add git source configuration
                add_git_source(bundled_config, plugin)
                existing_sources.add(package_name)

    # Ensure parent directory exists
    bundled_path.parent.mkdir(parents=True, exist_ok=True)

    # Write bundled pyproject.toml to specified path
    with open(bundled_path, "w") as f:
        tomlkit.dump(bundled_config, f)


def validate_bundled_path(bundled_dir: Path) -> None:
    """Ensure bundled directory is not inside current environment."""
    current_pyproject = find_pyproject_toml()
    current_root = current_pyproject.parent

    # Resolve paths to handle symlinks properly
    bundled_resolved = bundled_dir.resolve()
    current_resolved = current_root.resolve()

    # Check if bundled dir is inside current environment
    try:
        bundled_resolved.relative_to(current_resolved)
        raise ValueError(
            f"Bundled directory {bundled_dir} cannot be inside current environment "
            f"{current_root}"
        )
    except ValueError as e:
        if "cannot be inside current environment" in str(e):
            raise
        # relative_to() throws ValueError if not related - this is good!
        pass


def symlink_current_environment(bundled_dir: Path) -> None:
    """Create symlinks to current environment's src/ tree and .env.

    Also creates pyproject.original.toml symlink for clean slate reference.
    """
    current_pyproject = find_pyproject_toml()
    current_root = current_pyproject.parent
    current_src_dir = current_root / "src"
    current_env_file = current_root / ".env"

    # Symlink original pyproject.toml as pyproject.original.toml (for clean slate)
    bundled_original = bundled_dir / "pyproject.original.toml"
    bundled_original.symlink_to(current_pyproject)

    # Symlink entire src/ directory
    bundled_src = bundled_dir / "src"
    bundled_src.symlink_to(current_src_dir)

    # Symlink .env file if it exists
    if current_env_file.exists():
        bundled_env = bundled_dir / ".env"
        bundled_env.symlink_to(current_env_file)


async def run_uv_lock_and_sync(bundled_dir: Path) -> None:
    """Run UV commands in bundled directory asynchronously."""
    # Run UV lock asynchronously
    process = await asyncio.create_subprocess_exec(
        "uv",
        "lock",
        cwd=bundled_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode or 1, ["uv", "lock"], stderr=stderr
        )

    # Run UV sync asynchronously
    process = await asyncio.create_subprocess_exec(
        "uv",
        "sync",
        cwd=bundled_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode or 1, ["uv", "sync"], stderr=stderr
        )


async def setup_bundled_environment(plugins: list["Plugin"], bundled_dir: Path) -> None:
    """Set up complete bundled environment with symlinks and plugin dependencies."""
    # Safety check first!
    validate_bundled_path(bundled_dir)

    # Clean and recreate bundled directory
    if bundled_dir.exists():
        shutil.rmtree(bundled_dir)
    bundled_dir.mkdir(parents=True)

    # Symlink current environment's files
    symlink_current_environment(bundled_dir)

    # Generate bundled config with plugin dependencies as the main pyproject.toml
    bundled_config_path = bundled_dir / "pyproject.toml"
    generate_bundled_config(plugins, bundled_config_path)

    # Initialize UV environment asynchronously
    await run_uv_lock_and_sync(bundled_dir)


async def test_plugin_dependencies(db: "Session") -> None:
    """Test plugin dependencies by creating temporary bundled environment.

    Tests all plugins currently in the database session (including uncommitted ones).
    Raises PluginDependencyConflictError if dependencies cannot be resolved.
    """
    from ..database.models import Plugin as PluginModel

    # Get all plugins from current database session (including uncommitted)
    all_plugins = db.query(PluginModel).all()

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory(prefix="cosmo_plugin_test_") as temp_dir:
        temp_bundled_dir = Path(temp_dir)

        try:
            # Set up temporary bundled environment asynchronously
            await setup_bundled_environment(all_plugins, temp_bundled_dir)

        except subprocess.CalledProcessError as e:
            # UV lock/sync failed - capture error for debugging
            error_output = e.stderr.decode() if e.stderr else str(e)

            # Don't try to parse error messages - just provide generic message
            raise PluginDependencyConflictError(
                "Plugin dependencies cannot be resolved. This may be due to version "
                "conflicts, missing packages, or incompatible requirements.",
                uv_error=error_output,
            ) from e

        except Exception as e:
            # Other errors during bundled environment setup
            raise PluginDependencyConflictError(
                f"Failed to test plugin dependencies: {str(e)}", uv_error=str(e)
            ) from e
