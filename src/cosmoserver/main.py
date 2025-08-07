import logging
from contextlib import asynccontextmanager

from cosmo.engine.core import ConditionEngine
from cosmo.plugin.service import PluginService
from cosmo.rules.manager import RuleManager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from .database import engine, get_prefs
from .database.base import Base
from .database.prefs import PreferenceKeys, Preferences
from .plugins.loader import load_all_plugins_from_database
from .routes.crud import router as crud_router
from .routes.globals import router as globals_router
from .routes.preferences import router as preferences_router
from .routes.rpc import router as rpc_router
from .startup import auto_install_database_rules
from .util import InitItem

load_dotenv()
logger = logging.getLogger(__name__)

PLUGIN_SERVICE: InitItem[PluginService] = InitItem()
RULE_MANAGER: InitItem[RuleManager] = InitItem()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Database")
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")

    logger.info("Initializing Core Cosmo Components")
    cosmo_engine = ConditionEngine()
    PLUGIN_SERVICE.initialize(PluginService(cosmo_engine))
    RULE_MANAGER.initialize(RuleManager(cosmo_engine, PLUGIN_SERVICE.get()))
    logger.info("Core components initialized")

    logger.info("Loading CosmoServerPlugin")
    from .plugins.cosmo_server.cosmo_server_plugin import CosmoServerPlugin

    cosmo_server_plugin = CosmoServerPlugin()
    PLUGIN_SERVICE.get().register_plugin(cosmo_server_plugin)
    logger.info("CosmoServerPlugin loaded")

    # Auto-install database rules
    auto_install_database_rules(RULE_MANAGER.get())

    logger.info("Loading dynamic plugins from database")
    await load_all_plugins_from_database(app)
    logger.info("All plugins loaded")

    logger.info("Initialization Complete, Starting Server...")
    yield

    # TODO: Cleanup


app = FastAPI(lifespan=lifespan)

# Register routers
app.include_router(rpc_router)
app.include_router(crud_router)
app.include_router(preferences_router)
app.include_router(globals_router)


@app.get("/", tags=["General"])
def root() -> str:
    return "🐇🤖 Cosmo Server"


@app.get("/hello", tags=["General"])
def introduce_cosmo(prefs: Preferences = Depends(get_prefs)) -> str:
    user_name = prefs.get(PreferenceKeys.USER_NAME)
    if user_name:
        return (
            f"Hello {user_name}, my name is Cosmo - I am the AI brain of your smart home."
            " I can control the devices in your smart home, curate scenes, "
            "and manage automations."
        )
    else:
        return (
            "Hello, my name is Cosmo - I am the AI brain of your smart home. "
            "I can control the devices in your smart home, curate scenes, "
            "and manage automations."
        )
