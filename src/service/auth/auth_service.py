from datetime import datetime, timedelta
import json as _json
import time as _time
from typing import Optional
import jwt  # Using PyJWT or python-jose
from fastapi import HTTPException
from passlib.context import CryptContext

from src.app_context import AppContext
from src.utils.db_utils import execute_query
from src.service.auth.auth_schema import UserCreate, UserRole, UserState

# 비밀번호 해싱 설정
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plainPassword: str, hashedPassword: str) -> bool:
    if not hashedPassword:
        return False
    return pwd_context.verify(plainPassword, hashedPassword)


def create_access_token(ctx: AppContext, data: dict, expiresDelta: Optional[timedelta] = None) -> str:
    toEncode = data.copy()
    if expiresDelta:
        expire = datetime.utcnow() + expiresDelta
    else:
        expireMinutes = getattr(ctx.cfg, "access_token_expire_minutes", 60)
        expire = datetime.utcnow() + timedelta(minutes=expireMinutes)
    
    toEncode.update({"exp": expire})
    secretKey = ctx.cfg.secret_key
    encodedJwt = jwt.encode(toEncode, secretKey, algorithm=ALGORITHM)
    return encodedJwt


def get_user_by_email(ctx: AppContext, email: str, activeOnly: bool = True) -> Optional[dict]:
    """
    이메일로 사용자 정보 조회
    - tb_user.fileId에 저장된 경로를 스키마의 filePath 필드로 깔끔하게 매핑합니다.
    """
    sql = """
        SELECT id, email, password, name, nickname, phone, 
               emailConf, `desc`, fileId, role, state, extra
        FROM tb_user
        WHERE email = %s
    """
    params = [email]
    if activeOnly:
        sql += " AND state = %s"
        params.append(UserState.ACTIVE.value)

    if not ctx.db_handler:
        return None

    rows = execute_query(ctx.db_handler, sql, tuple(params))
    if not rows:
        return None

    row = rows[0]
    extra = row[11] or {}
    if isinstance(extra, str):
        extra = _json.loads(extra)

    return {
        "id": row[0],
        "email": row[1],
        "password": row[2],
        "name": row[3],
        "nickname": row[4],
        "phone": row[5],
        "emailConf": row[6],
        "desc": row[7],
        "filePath": row[8],  # 명세서 기준 컬럼인 fileId에 담긴 경로 문자열을 할당
        "role": row[9],
        "state": row[10],
        "extra": extra,
        "provider": extra.get("provider", "email"),
        "providerId": extra.get("providerId")
    }

def check_user_exists(ctx: AppContext, userId: int) -> bool:
    sql = "SELECT COUNT(*) FROM tb_user WHERE id = %s"
    rows = execute_query(ctx.db_handler, sql, (userId,))
    if rows and rows[0][0] > 0:
        return True
    return False


def check_email_exists(ctx: AppContext, email: str) -> bool:
    sql = "SELECT COUNT(*) FROM tb_user WHERE email = %s"
    rows = execute_query(ctx.db_handler, sql, (email,))
    if rows and rows[0][0] > 0:
        return True
    return False


def authenticate_user(ctx: AppContext, email: str, password: str) -> Optional[dict]:
    user = get_user_by_email(ctx, email, activeOnly=True)
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    return user


def create_user(ctx: AppContext, userDto: UserCreate) -> dict:
    if check_email_exists(ctx, userDto.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashedPassword = get_password_hash(userDto.password) if userDto.password else None
    
    extraData = userDto.extra or {}
    extraData["provider"] = userDto.provider
    if userDto.providerId:
        extraData["providerId"] = userDto.providerId

    now = int(_time.time())

    sql = """
        INSERT INTO tb_user 
        (email, password, name, nickname, phone, emailConf, `desc`, fileId, role, state, extra, cDate, uDate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        userDto.email,
        hashedPassword,
        userDto.name,
        userDto.nickname,
        userDto.phone,
        userDto.emailConf,
        userDto.desc,
        userDto.filePath,  # fileId 컬럼 자리에 경로 문자열 직접 타겟팅
        UserRole.CLIENT.value,
        UserState.ACTIVE.value,
        _json.dumps(extraData, ensure_ascii=False),
        now,
        now
    )

    conn = ctx.db_handler.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            newId = cursor.lastrowid
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {
        "id": newId,
        "email": userDto.email,
        "name": userDto.name,
        "nickname": userDto.nickname,
        "phone": userDto.phone,
        "emailConf": userDto.emailConf,
        "desc": userDto.desc,
        "filePath": userDto.filePath,
        "role": UserRole.CLIENT.value,
        "state": UserState.ACTIVE.value,
        "extra": extraData,
        "provider": userDto.provider,
        "providerId": userDto.providerId
    }

def update_user(ctx: AppContext, userId: int, data: dict) -> bool:
    """
    사용자 정보 수정
    - 클라이언트가 filePath 키로 전달한 이미지 경로를 유저 테이블의 fileId 컬럼에 직접 동기화합니다.
    """
    if data.get("passwordNew"):
        sql = "SELECT id, email, password FROM tb_user WHERE id = %s"
        rows = execute_query(ctx.db_handler, sql, (userId,))
        if not rows:
            raise HTTPException(status_code=404, detail="User not found")
        if data.get("password") and not verify_password(data["password"], rows[0][2]):
            raise HTTPException(status_code=400, detail="Current password incorrect")
        data["password"] = get_password_hash(data["passwordNew"])

    fields = []
    params = []
    
    # 기본 입력 데이터 매핑
    for key in ["name", "nickname", "phone", "desc", "password"]:
        if data.get(key) is not None:
            colName = "`desc`" if key == "desc" else key
            fields.append(f"{colName} = %s")
            params.append(data[key])
            
    # filePath 가 수정 키셋에 포함되어 있다면, 유저 테이블의 fileId 컬럼에 곧바로 매핑 적재
    if "filePath" in data:
        fields.append("fileId = %s")
        params.append(data["filePath"])

    if data.get("extra") is not None:
        fields.append("extra = %s")
        params.append(_json.dumps(data["extra"], ensure_ascii=False))

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    now = int(_time.time())
    fields.append("uDate = %s")
    params.append(now)
    params.append(userId)

    sql = f"UPDATE tb_user SET {', '.join(fields)} WHERE id = %s"
    conn = ctx.db_handler.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")