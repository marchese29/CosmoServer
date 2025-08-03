from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, UUIDTimestampMixin


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
