# Import every model here so Alembic can "see" them via Base.metadata.
from app.models.business import Business  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
