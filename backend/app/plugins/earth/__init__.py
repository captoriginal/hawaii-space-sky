from typing import List

from fastapi import APIRouter

from ...models import EarthFrame
from ...services.earth_loop import get_earth_loop


def register(app):
    router = APIRouter(prefix="/api/earth", tags=["earth"])

    @router.get("/loop", response_model=List[EarthFrame])
    async def earth_loop():
        return await get_earth_loop()

    app.include_router(router)
