from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Preference, User
from ..schemas import PreferenceOut, PreferenceUpdate
from .deps import get_current_user

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferenceOut | None)
def get_preference(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Preference | None:
    return db.query(Preference).filter(Preference.user_id == user.id).first()


@router.put("", response_model=PreferenceOut)
def upsert_preference(
    payload: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Preference:
    pref = db.query(Preference).filter(Preference.user_id == user.id).first()
    if pref is None:
        pref = Preference(user_id=user.id)
        db.add(pref)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(pref, key, value)
    db.commit()
    db.refresh(pref)
    return pref
