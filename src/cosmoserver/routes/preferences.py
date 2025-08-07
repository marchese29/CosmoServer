from fastapi import APIRouter, Depends, HTTPException

from ..database import get_prefs
from ..database.prefs import PreferenceKeys, Preferences
from ..models.preferences import PreferenceResponse, PreferenceUpdate

router = APIRouter(prefix="/preferences", tags=["Preferences"])


def _get_preference_key(key: str) -> PreferenceKeys:
    """Get PreferenceKeys enum value from string, raise 404 if not found."""
    try:
        return PreferenceKeys[key.upper()]
    except KeyError as e:
        # Try to find by value instead of name
        for pref_key in PreferenceKeys:
            if pref_key.value.key == key:
                return pref_key
        raise HTTPException(
            status_code=404, detail=f"Preference key '{key}' not found"
        ) from e


@router.get("/", response_model=list[PreferenceResponse])
def get_preferences(prefs: Preferences = Depends(get_prefs)):
    """List all preferences."""
    all_prefs = prefs.get_all()
    return [PreferenceResponse(key=key, value=value) for key, value in all_prefs.items()]


@router.get("/{key}", response_model=PreferenceResponse)
def get_preference(key: str, prefs: Preferences = Depends(get_prefs)):
    """Get a specific preference by key."""
    pref_key = _get_preference_key(key)
    value = prefs.get(pref_key)

    if value is None:
        raise HTTPException(status_code=404, detail=f"Preference '{key}' not set")

    return PreferenceResponse(key=pref_key.value.key, value=value)


@router.put("/{key}", response_model=PreferenceResponse)
def set_preference(
    key: str, update: PreferenceUpdate, prefs: Preferences = Depends(get_prefs)
):
    """Set or update a preference value."""
    pref_key = _get_preference_key(key)

    try:
        prefs.set(pref_key, update.value)
    except TypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return PreferenceResponse(key=pref_key.value.key, value=update.value)


@router.delete("/{key}")
def delete_preference(key: str, prefs: Preferences = Depends(get_prefs)):
    """Delete a preference."""
    pref_key = _get_preference_key(key)

    if not prefs.delete(pref_key):
        raise HTTPException(status_code=404, detail=f"Preference '{key}' not found")

    return {"message": f"Preference '{key}' deleted successfully"}
