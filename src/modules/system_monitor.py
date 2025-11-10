# src/modules/system_monitor.py

import os
import time
import threading
import psutil
from typing import Optional, Any


class SystemMonitor:
    """시스템 리소스 모니터링 클래스"""
    
    def __init__(self, log: Any, interval: int = 10):
        self.log = log
        self.interval = interval
        self.process = psutil.Process(os.getpid())
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self) -> None:
        """모니터링 시작"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self.log.warning("Manager", "-- System monitor is already running")
            return
        
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        self.log.info("Manager", f"-- System monitor started (interval: {self.interval}s)")
    
    def stop(self) -> None:
        """모니터링 중지"""
        if not self._monitor_thread or not self._monitor_thread.is_alive():
            return
        
        self._stop_event.set()
        self._monitor_thread.join(timeout=5)
        
        self.log.info("Manager", "-- system monitor stopped")
    
    def _monitor_loop(self) -> None:
        """모니터링 루프"""
        while not self._stop_event.is_set():
            try:
                self._log_system_stats()
                time.sleep(self.interval)
            except Exception as e:
                self.log.error("Manager", f"!! Error in system monitoring: {e}")
                time.sleep(self.interval)
    
    def _log_system_stats(self) -> None:
        """시스템 통계 로깅"""
        try:
            # 메모리 정보
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # CPU 정보
            cpu_percent = self.process.cpu_percent()
            
            # 스레드 수
            num_threads = self.process.num_threads()
            
            # 파일 디스크립터 수 (Unix 계열만)
            try:
                num_fds = self.process.num_fds()
            except AttributeError:
                num_fds = "N/A"
            
            self.log.debug(
                f"SYSTEM STATS - "
                f"Memory {memory_info.rss / (1024 * 1024):.2f}MB "
                f"({memory_percent:.2f}%), "
                f"CPU: {cpu_percent:.2f}%, "
                f"Threads: {num_threads}, "
                f"FDs: {num_fds}"
            )
            
        except psutil.NoSuchProcess:
            self.log.warning("Manager", "!! Process no longer exists for monitoring")
            self._stop_event.set()
        except Exception as e:
            self.log.error("Manager", f"!! Error collecting system stats: {e}")
    
    def get_current_stats(self) -> dict:
        """현재 시스템 통계 반환"""
        try:
            memory_info = self.process.memory_info()
            return {
                'memory_rss_mb': memory_info.rss / (1024 * 1024),
                'memory_vms_mb': memory_info.vms / (1024 * 1024),
                'memory_percent': self.process.memory_percent(),
                'cpu_percent': self.process.cpu_percent(),
                'num_threads': self.process.num_threads(),
                'pid': self.process.pid,
            }
        except Exception as e:
            self.log.error("Manager", f"!! Error getting current stats: {e}")
            return {}