from fastapi import APIRouter, Depends, HTTPException

from ..database import get_globals
from ..database.globals import GlobalVariables
from ..models.globals import GlobalVariableResponse, GlobalVariableUpdate

router = APIRouter(prefix="/globals", tags=["Global Variables"])


@router.get("/", response_model=list[GlobalVariableResponse])
def get_global_variables(globals_mgr: GlobalVariables = Depends(get_globals)):
    """List all global variables."""
    all_globals = globals_mgr.get_all()
    return [
        GlobalVariableResponse(key=key, value=value) for key, value in all_globals.items()
    ]


@router.get("/{key}", response_model=GlobalVariableResponse)
def get_global_variable(key: str, globals_mgr: GlobalVariables = Depends(get_globals)):
    """Get a specific global variable by key."""
    value = globals_mgr.get(key)

    if value is None:
        raise HTTPException(status_code=404, detail=f"Global variable '{key}' not found")

    return GlobalVariableResponse(key=key, value=value)


@router.put("/{key}", response_model=GlobalVariableResponse)
def set_global_variable(
    key: str,
    update: GlobalVariableUpdate,
    globals_mgr: GlobalVariables = Depends(get_globals),
):
    """Set or update a global variable value."""
    try:
        globals_mgr.set(key, update.value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return GlobalVariableResponse(key=key, value=update.value)


@router.delete("/{key}")
def delete_global_variable(key: str, globals_mgr: GlobalVariables = Depends(get_globals)):
    """Delete a global variable."""
    if not globals_mgr.delete(key):
        raise HTTPException(status_code=404, detail=f"Global variable '{key}' not found")

    return {"message": f"Global variable '{key}' deleted successfully"}
