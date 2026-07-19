from src.core.id_generator import generate_sid
from src.core.responses import ResponseStatus, build_response_body, build_success_response
import src.utils.redis_basic_utils as ru
import orjson


async def connect_session(ctx, body):
    user_id = body.userId.strip()

    if not user_id:
        return build_response_body(ResponseStatus.BAD_REQUEST, {"detail": "userId는 필수입니다."})

    sid = generate_sid()

    session_info = {
        "userId": user_id,
        "client_name": body.client_name,
        "provider_name": body.provider_name,
        "contract_date": body.contract_date,
        "client_business_number": body.client_business_number,
        "client_contact": body.client_contact,
        "provider_business_number": body.provider_business_number,
        "provider_contact": body.provider_contact,
        "createdAt": None,
    }

    try:
        session_key = f"session:info:{sid}"
        await ru.redis_set(
            ctx,
            session_key,
            orjson.dumps(session_info).decode(),
            ex=86400,
        )
    except Exception as e:
        ctx.log.warning(f"[AUTH] Failed to save session info to Redis: {e}")
        if not hasattr(ctx, "sessions"):
            ctx.sessions = {}
        ctx.sessions[sid] = session_info

    return build_success_response({"sid": sid})
