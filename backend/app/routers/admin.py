from fastapi import APIRouter, BackgroundTasks, Depends

from app.auth import require_auth
from app.scraper.cyber_scraper import run_scrape

router = APIRouter(dependencies=[Depends(require_auth)], tags=["admin"])


@router.post("/admin/scrape/run", status_code=202)
async def trigger_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scrape)
    return {"status": "scrape triggered"}
