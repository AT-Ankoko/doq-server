# src/service/scripts/id_generator.py
from uuid import uuid4

# Session ID 생성 함수 (UUIDv4 hex)
def generate_sid() -> str:
    return f"s-{uuid4().hex}"

# Task ID 생성 함수
def generate_task_id() -> str:
    return str(uuid4())