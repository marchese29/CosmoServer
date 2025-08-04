"""Plugin loading and management utilities."""

import importlib
import importlib.resources
import json
import logging
from typing import cast

from cosmo.plugin import CosmoPlugin
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..database.models import Plugin as PluginModel
from ..util import AsyncCreatable

logger = logging.getLogger(__name__)


class PluginManifest(BaseModel):
    """Plugin manifest model for cosmo.json."""

    name: str
    plugin_class: str  # e.g. "cosmohubitatplugin.HubitatPlugin"
    description: str
    url_prefix: str | None = None  # e.g. "hubitat" (no leading slash)


def get_plugin_manifest(package_name: str) -> PluginManifest:
    """Load cosmo.json manifest from installed package."""
    try:
        package_files = importlib.resources.files(package_name)
        cosmo_json = package_files / "cosmo.json"

        if not cosmo_json.is_file():
            raise FileNotFoundError(f"cosmo.json not found in {package_name}")

        manifest_data = json.loads(cosmo_json.read_text())
        return PluginManifest(**manifest_data)

    except Exception as e:
        raise ImportError(f"Failed to load manifest for {package_name}: {e}") from e


# Function removed - plugins are now managed through proper CRUD API


def update_plugin_error(db: Session, plugin_id: str, error_message: str | None) -> None:
    """Update plugin error message in database."""
    plugin = db.query(PluginModel).filter(PluginModel.id == plugin_id).first()
    if plugin:
        plugin.error_message = error_message
        db.commit()


async def load_single_plugin(app: FastAPI, plugin_record: PluginModel) -> None:
    """Load a single plugin by importing its class and registering it."""
    from ..main import PLUGIN_SERVICE

    # 1. Get manifest from package resources
    # Use python_package_name if available, otherwise fallback to source
    package_name = plugin_record.python_package_name or plugin_record.source
    manifest = get_plugin_manifest(package_name)

    # 2. Import plugin class dynamically
    module_name, class_name = manifest.plugin_class.rsplit(".", 1)
    module = importlib.import_module(module_name)
    plugin_class = getattr(module, class_name)

    # 3. Create plugin instance using protocol check
    if isinstance(plugin_class, AsyncCreatable):
        plugin_instance: CosmoPlugin = cast(CosmoPlugin, await plugin_class.create())
    else:
        plugin_instance: CosmoPlugin = plugin_class()

    # 4. Register with PluginService (assumes PLUGIN_SERVICE is already initialized)
    PLUGIN_SERVICE.get().register_plugin(plugin_instance)

    # 5. Register routes if URL prefix specified
    if manifest.url_prefix:
        router = APIRouter(
            prefix=f"/{manifest.url_prefix}",
            tags=[manifest.name],  # Use plugin name as tag
        )
        plugin_instance.configure_routes(router)
        app.include_router(router)
        logger.info(f"Registered routes for {manifest.name} at /{manifest.url_prefix}")


async def load_all_plugins_from_database(app: FastAPI) -> None:
    """Load all plugins from database, updating error_message for failures."""
    with SessionLocal() as db:
        # 1. Get ALL plugins from database (regardless of status)
        db_plugins = db.query(PluginModel).all()
        logger.info(f"Found {len(db_plugins)} plugins in database")

        # 3. Attempt to load each plugin - NEVER kill the server
        successful_count = 0
        for plugin_record in db_plugins:
            try:
                await load_single_plugin(app, plugin_record)
                # Clear error message on success
                update_plugin_error(db, plugin_record.id, None)
                logger.info(f"Successfully loaded plugin: {plugin_record.name}")
                successful_count += 1

            except ImportError as e:
                # Module/package not found - likely clean mode
                error_msg = (
                    f"Import failed: {str(e)} "
                    "(may be due to clean mode or missing package)"
                )
                logger.warning(f"Plugin {plugin_record.name}: {error_msg}")
                update_plugin_error(db, plugin_record.id, error_msg)

            except Exception as e:
                # Any other error during loading/construction/registration
                error_details = (
                    str(e) if str(e).strip() else f"{type(e).__name__}: {repr(e)}"
                )
                error_msg = (
                    f"Failed to load plugin: {error_details} "
                    "(plugin misconfiguration or runtime error)"
                )
                logger.warning(f"Plugin {plugin_record.name}: {error_msg}")
                logger.exception(f"Full traceback for {plugin_record.name}")
                update_plugin_error(db, plugin_record.id, error_msg)

        logger.info(
            f"Plugin loading complete: {successful_count}/{len(db_plugins)} "
            "plugins loaded successfully"
        )
