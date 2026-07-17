# SQL 쿼리 실행 등 DB 관련 유틸리티 함수들

from pathlib import Path


def execute_query(handler, query, params=None):
    """편의용 쿼리 실행 함수"""
    conn = handler.get_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchall()


def _run_sql_file(conn, sql_path: Path, log=None) -> None:
    """SQL 파일을 읽어 문장 단위로 실행한다."""
    sql_text = sql_path.read_text(encoding="utf-8")

    # 세미콜론으로 분리 후 빈 문장 제거
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]

    with conn.cursor() as cursor:
        for stmt in statements:
            try:
                cursor.execute(stmt)
            except Exception as e:
                if log:
                    log.warning(f"     - db_init: skip statement ({e}): {stmt[:80]!r}")
    conn.commit()


def run_init_schema(handler, log=None) -> None:
    """테이블 스키마를 초기화한다 (tryangle-init.sql)."""
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "init" / "tryangle-init.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"init SQL not found: {sql_path}")
    if log:
        log.info(f"     - db_init: running schema init → {sql_path.name}")
    conn = handler.get_connection()
    _run_sql_file(conn, sql_path, log)
    if log:
        log.info("     - db_init: schema init complete")


def run_seed_data(handler, log=None) -> None:
    """기본 시드 데이터를 삽입한다 (tryangle-seed.sql).  이미 존재하는 행은 무시."""
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "init" / "tryangle-seed.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"seed SQL not found: {sql_path}")
    if log:
        log.info(f"     - db_init: running seed data → {sql_path.name}")
    conn = handler.get_connection()
    _run_sql_file(conn, sql_path, log)
    if log:
        log.info("     - db_init: seed data complete")


def is_initialized(handler) -> bool:
    """핵심 테이블(tb_user)이 이미 존재하면 True를 반환한다."""
    conn = handler.get_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'tb_user'"
        )
        row = cursor.fetchone()
        return bool(row and row[0] > 0)


def init_db(handler, log=None) -> None:
    """스키마 생성 → 시드 데이터 순으로 DB를 초기화한다."""
    run_init_schema(handler, log)
    run_seed_data(handler, log)


def init_db_if_needed(handler, log=None) -> None:
    """최초 실행(테이블 미존재) 시에만 스키마·시드를 실행한다."""
    if is_initialized(handler):
        if log:
            log.info("     - db_init: tables already exist, skipping init")
        return
    if log:
        log.info("     - db_init: first run detected, initializing DB...")
    init_db(handler, log)