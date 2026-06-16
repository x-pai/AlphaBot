from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import check_usage_limit
from app.services.worldcup_service import WorldCupService
from app.utils.response import api_response

router = APIRouter()


@router.get("/overview", response_model=dict)
async def get_worldcup_overview(
    refresh: bool = Query(False, description="是否强制刷新真实数据"),
    _: None = Depends(check_usage_limit),
):
    overview = await WorldCupService.get_overview(refresh=refresh)
    return api_response(data=overview)


@router.get("/matches", response_model=dict)
async def list_worldcup_matches(
    stage: Optional[str] = Query(None, description="赛事阶段"),
    status: Optional[str] = Query(None, description="比赛状态"),
    refresh: bool = Query(False, description="是否强制刷新真实数据"),
    _: None = Depends(check_usage_limit),
):
    matches = await WorldCupService.list_matches(stage=stage, status=status, refresh=refresh)
    return api_response(data=matches)


@router.get("/matches/{match_id}", response_model=dict)
async def get_worldcup_match(
    match_id: str,
    refresh: bool = Query(False, description="是否强制刷新真实数据"),
    _: None = Depends(check_usage_limit),
):
    match = await WorldCupService.get_match_detail(match_id, refresh=refresh)
    if not match:
        return api_response(success=False, error="未找到对应比赛")
    return api_response(data=match)
