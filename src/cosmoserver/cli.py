"""Command-line interface for CosmoServer startup and management."""

import argparse
import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .database.models import Plugin as PluginModel
from .database.models import PluginInstallStatus, PluginSourceType
from .plugins.utils import setup_bundled_environment
from .util import get_user_data_dir

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    """Configure logging for the CLI."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    logging.basicConfig(
        level=numeric_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def get_default_bundle_dir() -> Path:
    """Get the default bundle directory using XDG standards."""
    return get_user_data_dir("cosmoserver") / "bundled"


def ensure_hubitat_plugin_in_database() -> None:
    """Ensure Hubitat plugin is registered in database with git configuration."""
    try:
        # Try to connect to default database location
        data_dir = get_user_data_dir("cosmoserver")
        db_path = data_dir / "cosmo.db"

        if not db_path.exists():
            logger.info("Database not found, skipping Hubitat plugin check")
            return

        # Create database connection
        engine = create_engine(f"sqlite:///{db_path}")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with SessionLocal() as db:
            # Check if Hubitat plugin already exists
            existing = (
                db.query(PluginModel)
                .filter(
                    PluginModel.source
                    == "https://github.com/marchese29/CosmoHubitatPlugin"
                )
                .first()
            )

            if not existing:
                # Add Hubitat plugin with git configuration
                hubitat_plugin = PluginModel(
                    name="Hubitat Plugin",
                    source="https://github.com/marchese29/CosmoHubitatPlugin",
                    source_type=PluginSourceType.GIT,
                    python_package_name="cosmohubitatplugin",
                    install_status=PluginInstallStatus.INSTALLED,
                    installed_version="main",
                )
                db.add(hubitat_plugin)
                db.commit()
                logger.info("Added Hubitat plugin to database")
            else:
                logger.info("Hubitat plugin already exists in database")

    except Exception as e:
        logger.warning(f"Failed to ensure Hubitat plugin in database: {e}")


def get_database_plugins() -> list[PluginModel]:
    """Query database for all plugins. Returns empty list if database doesn't exist."""
    try:
        # Try to connect to default database location
        data_dir = get_user_data_dir("cosmoserver")
        db_path = data_dir / "cosmo.db"

        if not db_path.exists():
            logger.info("Database not found, assuming no plugins")
            return []

        # Create database connection
        engine = create_engine(f"sqlite:///{db_path}")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with SessionLocal() as db:
            plugins = db.query(PluginModel).all()
            logger.info(f"Found {len(plugins)} plugins in database")
            return plugins

    except Exception as e:
        logger.warning(f"Failed to query database: {e}. Assuming no plugins.")
        return []


async def create_bundled_environment(
    bundle_dir: Path, force_rebuild: bool = False
) -> None:
    """Create or update the bundled environment."""
    logger.info(f"Setting up bundled environment at {bundle_dir}")

    # Get plugins from database
    plugins = get_database_plugins()

    # Check if we need to rebuild
    if bundle_dir.exists() and not force_rebuild:
        logger.info("Bundled environment exists. Use --force-rebuild to recreate.")
    else:
        if force_rebuild and bundle_dir.exists():
            logger.info("Force rebuilding bundled environment")

        try:
            await setup_bundled_environment(plugins, bundle_dir)
            logger.info("Bundled environment created successfully")
        except Exception as e:
            logger.error(f"Failed to create bundled environment: {e}")
            sys.exit(1)


def run_fastapi_command(
    bundle_dir: Path | None, host: str, port: int, dev_mode: bool, clean_mode: bool
) -> None:
    """Run the FastAPI server with appropriate command."""

    # Determine the command
    if dev_mode:
        cmd = ["uv", "run", "fastapi", "dev"]
    else:
        cmd = ["uv", "run", "fastapi", "run"]

    # Add the main file
    cmd.append("src/cosmoserver/main.py")

    # Add host and port
    cmd.extend(["--host", host, "--port", str(port)])

    # Set working directory for bundled mode
    cwd = bundle_dir if not clean_mode and bundle_dir else None

    if cwd:
        logger.info(f"Starting server from bundled environment: {cwd}")
    else:
        logger.info("Starting server in clean mode")

    logger.info(f"Executing: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)


async def main() -> None:
    """Main CLI entry point."""
    # Load environment variables from .env file first
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="CosmoServer startup script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start bundled server (default)
  uv run python -m cosmoserver.cli

  # Start in development mode with bundled plugins
  uv run python -m cosmoserver.cli --dev

  # Start clean server without bundling
  uv run python -m cosmoserver.cli --clean

  # Create bundle without starting server
  uv run python -m cosmoserver.cli --bundle-only

  # Start with custom host/port
  uv run python -m cosmoserver.cli --host 0.0.0.0 --port 9000
        """,
    )

    # Main mode flags
    parser.add_argument(
        "--clean", action="store_true", help="Run in clean mode (no bundling)"
    )

    parser.add_argument(
        "--bundle-only", action="store_true", help="Create bundle but don't start server"
    )

    parser.add_argument(
        "--dev", action="store_true", help="Development mode with auto-reload"
    )

    # Server configuration
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind socket to this host (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port", type=int, default=8000, help="Bind socket to this port (default: 8000)"
    )

    # Bundle configuration
    parser.add_argument(
        "--bundle-dir", type=Path, help="Override default bundle directory"
    )

    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Force recreation of bundled environment",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Set logging level (default: info)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Determine bundle directory
    bundle_dir = args.bundle_dir or get_default_bundle_dir()

    # Validate arguments
    if args.clean and args.bundle_only:
        logger.error("Cannot use --clean and --bundle-only together")
        sys.exit(1)

    # Handle clean mode
    if args.clean:
        logger.info("Starting in clean mode (no bundling)")
        run_fastapi_command(None, args.host, args.port, args.dev, clean_mode=True)
        return

    # Ensure Hubitat plugin is registered in database
    ensure_hubitat_plugin_in_database()

    # Create bundled environment
    await create_bundled_environment(bundle_dir, args.force_rebuild)

    # Handle bundle-only mode
    if args.bundle_only:
        logger.info("Bundle created successfully. Exiting without starting server.")
        return

    # Start bundled server
    run_fastapi_command(bundle_dir, args.host, args.port, args.dev, clean_mode=False)


def cli_main() -> None:
    """Synchronous entry point for the CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
