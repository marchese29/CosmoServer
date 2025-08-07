"""CosmoServerPlugin - Built-in plugin providing access to server internals."""

import asyncio
from collections.abc import AsyncGenerator

from cosmo.plugin import CosmoPlugin
from cosmo.plugin.model import AbstractCondition
from fastapi import APIRouter

from .cosmo_utils import CosmoUtils


class CosmoServerPlugin(CosmoPlugin):
    """
    Built-in plugin that provides access to CosmoServer internals through CosmoUtils.
    """

    def __init__(self):
        """Initialize the plugin with a never-fired event."""
        self._shutdown_event = asyncio.Event()
        self._cosmo_utils = CosmoUtils()

    def configure_routes(self, router: APIRouter) -> None:
        """Configure routes for the plugin. No routes needed for this plugin."""
        # No routes to register - this plugin only provides utilities for rules
        pass

    def get_rule_utility(self) -> CosmoUtils:
        """Return the CosmoUtils instance for use in rules."""
        return self._cosmo_utils

    async def run(self) -> AsyncGenerator[list[AbstractCondition], None]:
        """Run method that waits on an event that never gets fired."""
        try:
            # Wait for an event that will never be set - keeps the task alive
            # until it gets cancelled
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            # Plugin is being shut down
            return
        # This should never be reached
        return
        yield  # pragma: no cover
