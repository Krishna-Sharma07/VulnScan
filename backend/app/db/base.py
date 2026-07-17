"""Import all models here so Alembic's autogenerate can discover them
via Base.metadata, even though nothing in this file references them directly."""

from app.db.base_class import Base  # noqa: F401
from app.models.domain import Domain  # noqa: F401
from app.models.finding import Finding  # noqa: F401
from app.models.scan_job import ScanJob  # noqa: F401
from app.models.user import User  # noqa: F401
