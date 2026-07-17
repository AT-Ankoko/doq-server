# SQL 쿼리 실행 등 DB 관련 유틸리티 함수들

def execute_query(handler, query, params=None):
    """편의용 쿼리 실행 함수"""
    conn = handler.get_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchall()