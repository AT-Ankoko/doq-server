from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt

from src.service.auth import auth_service
from src.service.auth.auth_schema import UserRole


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> dict:
    ctx = request.app.state.ctx
    try:
        payload = jwt.decode(token, ctx.cfg.secret_key, algorithms=[auth_service.ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_email(ctx, email, activeOnly=True)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 인증에만 사용되는 비밀번호 해시는 사용자 조회 응답 컨텍스트로 전달하지 않는다.
    safe_user = dict(user)
    safe_user.pop("password", None)
    return safe_user


def require_user(user: dict = Depends(get_current_user)) -> dict:
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    role = user.get("role")
    if role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privilege required",
        )
    return user


def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    role = user.get("role")
    if role not in (UserRole.SUPER_ADMIN, UserRole.SUPER_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privilege required",
        )
    return user