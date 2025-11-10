import service.ai.asset.prompts.bantori_prompts as bantori_prompts

# 시스템 프롬프트 
SYSTEM_PROMPTS = [
    bantori_prompts.INITIAL_PROMPT,   
    bantori_prompts.ANALYSIS_CRITERIA,   
]

# 일일 평가 프롬프트
DAILY_REPORT_PROMPTS = [
    bantori_prompts.INITIAL_PROMPT,
    bantori_prompts.ANALYSIS_CRITERIA,
    bantori_prompts.GENERATE_DAILY_REPORT,
    bantori_prompts.JSON_OUTPUT_PROMPT
]

# 월별 평가 프롬프트
MONTHLY_REPORT_PROMPTS = [
    bantori_prompts.GENERATE_MONTHLY_REPORT,
    bantori_prompts.JSON_OUTPUT_PROMPT
]

# 일별 카테고리 프롬프트
TIP_REPORT_PROMPTS = [
    bantori_prompts.GENERATE_TIP_REPORT,
    bantori_prompts.JSON_OUTPUT_PROMPT
]