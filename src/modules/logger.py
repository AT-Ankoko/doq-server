import os
import re
import time
import sys

from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler

SUFFIX = "%Y%m%d"

class TimeSizeRotatingFileHandler(TimedRotatingFileHandler):
    def getFilesToDelete(self):
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName) if os.path.exists(dirName) else []
        result = []

        for fileName in fileNames:
            m = self.extMatch.search(fileName)
            if m:
                result.append(os.path.join(dirName, fileName))
        
        if len(result) > self.backupCount:
            result.sort()
            to_delete = result[:-self.backupCount]
            return to_delete
        return []
    
    def doRollover(self):
        # get the time that this sequence started at and make it a TimeTuple
        currentTime = int(time.time())
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstNow = time.localtime(currentTime)[-1]
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)

        # 백업 파일명 생성
        timestamp = datetime.now().strftime(self.suffix)
        dfn = f"{self.baseFilename}.{timestamp}"

        if os.path.exists(dfn):
            return

        if self.stream:
            self.stream.close()
            self.stream = None
            
        self.rotate(self.baseFilename, dfn)
        
        if self.backupCount > 0:
            files_to_delete = self.getFilesToDelete()
            for s in files_to_delete:
                os.remove(s)
                
        if not self.delay:
            self.stream = self._open()
            
        self.rolloverAt = self.computeRollover(currentTime)

class NoErrorFilter(logging.Filter):
    """ ERROR 이상의 로그를 제외하는 필터 """
    def filter(self, record):
        return record.levelno < logging.ERROR

class CustomLogger:
    def __init__(self, logger):
        self.logger = logger

    def _format(self, *args):
        if len(args) == 1:
            return args[0]
        elif len(args) >= 2:
            tag, msg = args[0], args[1]
            tag_str = f"[{tag}]"
            padding = " " * max(12 - len(tag_str), 1)
            return f"{tag_str}{padding}{msg}"
        else:
            return ""

    def debug(self, *args, **kwargs):
        self.logger.debug(self._format(*args), **kwargs)

    def info(self, *args, **kwargs):
        self.logger.info(self._format(*args), **kwargs)

    def warning(self, *args, **kwargs):
        self.logger.warning(self._format(*args), **kwargs)

    def error(self, *args, **kwargs):
        self.logger.error(self._format(*args), **kwargs)

    def critical(self, *args, **kwargs):
        self.logger.critical(self._format(*args), **kwargs)

def setup_logger(log_level, log_path, log_max_files):
    logger = logging.getLogger('general_logger')

    # 기존 핸들러 제거
    if logger.hasHandlers():
        logger.handlers.clear()

    # 로깅 레벨 설정
    log_level = getattr(logging, log_level.upper())
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        datefmt='%m/%d %H:%M:%S'
    )

    log_filename = log_path.replace("-%DATE%", "")
    backup_count = int(log_max_files.replace("d", ""))

    # 하루 단위 로테이션 설정 (테스트용)
    fileHandler = TimeSizeRotatingFileHandler(
        log_filename,
        when="midnight", 
        interval=1,
        backupCount=backup_count,
        encoding="utf-8"
    )
    
    # 백업 파일 매칭 정규식 설정
    base_log_name = os.path.basename(log_filename)
    escaped_base = re.escape(base_log_name)
    fileHandler.extMatch = re.compile(rf"{escaped_base}\.\d{{8}}$")
    fileHandler.suffix = SUFFIX
    
    fileHandler.setFormatter(formatter)
    fileHandler.setLevel(log_level)
    
    # stdout 핸들러 (DEBUG 이상)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(NoErrorFilter())

    # stderr 핸들러 (ERROR 이상)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.ERROR)

    logger.addHandler(fileHandler)
    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)

    # 로거 전파 방지
    logger.propagate = False

    return CustomLogger(logger)


