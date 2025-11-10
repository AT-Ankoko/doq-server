# api 기본 예제
# service/api/analyze_api.py

from fastapi import APIRouter, HTTPException, Request

import src.common.common_codes as codes
from src.service.ai.asset.prompts.prompts_cfg import (SYSTEM_PROMPTS, 
                                                      DAILY_REPORT_PROMPTS, 
                                                      MONTHLY_REPORT_PROMPTS, 
                                                      TIP_REPORT_PROMPTS)

# 라우터 등록은 여기서 하고 실제 로직은 service에서 관리
# http://localhost:8000/

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

# GET /api/analyze/dailyReport
@router.get("/dailyReport")
async def daily_report(request: Request):
    return 0