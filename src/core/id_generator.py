# src/service/scripts/id_generator.py
from uuid import uuid4

# Session ID 생성 함수
def generate_sid() -> str:
    return f"s{uuid4().hex[:10]}"

# Task ID 생성 함수
def generate_task_id() -> str:
    return str(uuid4())