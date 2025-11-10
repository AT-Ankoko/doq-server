# db_handler.py

import pymysql
import threading

class DBHandler:
    def __init__(self, config):
        self._config = config
        self._local = threading.local()

    def init_connection(self):
        """스레드 로컬에 DB 연결 초기화"""
        if not hasattr(self._local, "conn"):
            self._local.conn = pymysql.connect(**self._config)

    def get_connection(self):
        """현재 스레드의 커넥션 반환 (없으면 init)"""
        if not hasattr(self._local, "conn"):
            self.init_connection()
        return self._local.conn

    def close_connection(self):
        """커넥션 종료 및 제거"""
        if hasattr(self._local, "conn"):
            try:
                self._local.conn.close()
            except:
                pass
            del self._local.conn

