from fastapi import APIRouter

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("")
async def list_contracts() -> dict:
    return {"message": "contracts endpoint — not yet implemented"}
