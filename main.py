import logging
from contextlib import asynccontextmanager

from cosmo.engine.core import ConditionEngine
from cosmo.plugin.service import PluginService
from cosmo.rules.manager import RuleManager
from cosmohubitatplugin import HubitatPlugin
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI

from database import engine
from database.base import Base
from routes.crud import router as crud_router
from util import AsyncCreatable, InitItem

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

    logger.info("Setting up CRUD routers")
    # Register our custom CRUD router
    app.include_router(crud_router)
    logger.info("CRUD routers registered")

    logger.info("Initializing Core Cosmo Components")
    cosmo_engine = ConditionEngine()
    PLUGIN_SERVICE.initialize(PluginService(cosmo_engine))
    RULE_MANAGER.initialize(RuleManager(cosmo_engine, PLUGIN_SERVICE.get()))
    logger.info("Core components initialized")

    logger.info("Initializing plugins")

    # For now, the hubitat plugin is special and loaded directly
    logger.info("Initializing Hubitat Plugin")
    if isinstance(HubitatPlugin, AsyncCreatable):
        he_plugin = await HubitatPlugin.create()
    else:
        he_plugin = HubitatPlugin()  # type: ignore
    PLUGIN_SERVICE.get().register_plugin(he_plugin)

    logger.info("Registering Hubitat Plugin's Routes")
    he_router = APIRouter(prefix="/hubitat")
    he_plugin.configure_routes(he_router)
    app.include_router(he_router)
    logger.info("Hubitat Plugin Initialized")

    logger.info("All plugins initialized")

    logger.info("Initialization Complete, Starting Server...")
    yield

    # TODO: Cleanup


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root() -> str:
    return "🐇🤖 Cosmo Server"


@app.get("/hello")
def introduce_cosmo() -> str:
    return (
        "Hello, my name is Cosmo - I am the AI brain of your smart home. I can control "
        "the devices in your smart home, curate scenes, and manage automations."
    )
