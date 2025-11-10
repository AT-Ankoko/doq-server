# src/service/scripts/id_generator.py
from uuid import uuid4

# Task ID 생성 함수
def generate_task_id() -> str:
    return str(uuid4())