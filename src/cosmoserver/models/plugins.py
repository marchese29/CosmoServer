from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..database.models import PluginInstallStatus, PluginSourceType


class PluginBase(BaseModel):
    """Base schema for Plugin with common fields."""

    name: str
    source: str
    source_type: PluginSourceType


class PluginCreate(PluginBase):
    """Schema for creating a new Plugin."""

    updated_version: str | None = None


class PluginUpdate(BaseModel):
    """Schema for updating a Plugin - restricted to safe fields."""

    updated_version: str | None = None


class Plugin(PluginBase):
    """Schema for Plugin responses with full details."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    installed_version: str | None = None
    updated_version: str | None = None
    install_status: PluginInstallStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class PluginManifest(BaseModel):
    """Schema for plugin manifest (cosmo.json) parsing."""

    name: str
    version: str
    plugin_class: str
    description: str
    url_prefix: str | None = None
