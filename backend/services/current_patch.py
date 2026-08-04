from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Patch


def get_current_patch_version(db: Session) -> str | None:
    """patches.is_current=true인 버전을 반환한다. 없으면 None(호출측이 처리)."""
    current = db.execute(
        select(Patch).where(Patch.is_current.is_(True))
    ).scalar_one_or_none()
    return current.version if current is not None else None
