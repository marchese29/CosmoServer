from enum import Enum

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDTimestampMixin


class PluginSourceType(str, Enum):
    """Enum for plugin source types."""

    PYPI = "pypi"
    GIT = "git"


class PluginInstallStatus(str, Enum):
    """Enum for plugin installation status."""

    UNINSTALLED = "uninstalled"  # Found in directory but not in bundled env
    PENDING = "pending"  # Added to DB, needs restart to install
    INSTALLED = "installed"  # Currently active in bundled env
    FAILED = "failed"  # Installation failed


class Action(Base, UUIDTimestampMixin):
    """SQLAlchemy model for automation actions."""

    __tablename__ = "actions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_code: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship to rules that use this action
    rules: Mapped[list["Rule"]] = relationship("Rule", back_populates="action")


class Rule(Base, UUIDTimestampMixin):
    """SQLAlchemy model for automation rules."""

    __tablename__ = "rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    action_id: Mapped[str] = mapped_column(
        String, ForeignKey("actions.id"), nullable=False
    )
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship to the action this rule uses
    action: Mapped[Action] = relationship("Action", back_populates="rules")


class Plugin(Base, UUIDTimestampMixin):
    """SQLAlchemy model for plugins."""

    __tablename__ = "plugins"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # PyPI package or git URL
    source_type: Mapped[PluginSourceType] = mapped_column(
        SQLEnum(PluginSourceType), nullable=False
    )
    installed_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    updated_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    install_status: Mapped[PluginInstallStatus] = mapped_column(
        SQLEnum(PluginInstallStatus), default=PluginInstallStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    python_package_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
