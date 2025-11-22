"""
 Copyright (c) 2025. Ebee1205(wavicle) all rights reserved.

 The copyright of this software belongs to Ebee1205(wavicle).
 All rights reserved.
"""

# main.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import traceback
import asyncio

from src.app_context import AppContext

from service.basic.basic_api import router as basic_router

class AppFactory:
    """애플리케이션 팩토리 클래스"""
    
    @staticmethod
    def create_app() -> FastAPI:
        """FastAPI 애플리케이션 생성 및 설정"""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            ctx = None
            try:
                ctx = app.state.ctx
                await AppFactory._startup(app)
                yield
            except asyncio.CancelledError:
                if ctx and hasattr(ctx, 'log'):
                    ctx.log.warning("     - Application interrupted by user (CancelledError)")
                else:
                    print("     Application interrupted by user (CancelledError)")
                raise  # shutdown 호출을 위해 재전파 필요
            except Exception as e:
                if ctx and hasattr(ctx, 'log'):
                    ctx.log.error(f"     - Unexpected error during startup: {e}")
                else:
                    print(f"     Unexpected error during startup: {e}")
                traceback.print_exc()
                raise
            finally:
                if ctx and hasattr(ctx, 'log'):
                    ctx.log.info("     - Starting graceful shutdown")
                else:
                    print("     Starting graceful shutdown")
                await AppFactory._shutdown(app)

        
        app = FastAPI(lifespan=lifespan)
        
        # 컨텍스트 초기화
        ctx = AppContext()
        app.state.ctx = ctx
        
        # 설정 로드
        ctx.load_config("src/service/conf/doq_be.local.cfg.json")

        # CORS 설정
        AppFactory._setup_cors(app, ctx)
        
        # 라우터 등록
        AppFactory._register_routes(app)
        
        return app
    
    @staticmethod
    def _setup_cors(app: FastAPI, ctx: AppContext) -> None:
        """CORS 미들웨어 설정"""
        cors_config = ctx.cfg.http_config
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_config.allow_origins,
            allow_credentials=cors_config.allow_credentials,
            allow_methods=cors_config.allow_methods,
            allow_headers=cors_config.allow_headers,
        )
        print(f"CORS configuration complete: {cors_config.allow_origins}")
    
    @staticmethod
    def _register_routes(app: FastAPI) -> None:
        """라우터 등록"""
        routers = [
            basic_router,
        ]
        for router in routers:
            app.include_router(router)
    
    @staticmethod
    async def _startup(app: FastAPI) -> None:
        """애플리케이션 시작 시 초기화"""
        try:
            print("     - Initializing application...")
            ctx = app.state.ctx

            # 초기화 후 연결 설정
            await AppFactory._initialize_managers(ctx)
            await AppFactory._initialize_handlers(ctx)
            await AppFactory._initialize_algorithms(ctx)
            await AppFactory._setup_connections(ctx)
            
            ctx.log.info("     == Initialization complete")

        except Exception as e:
            if hasattr(app.state, 'ctx') and hasattr(app.state.ctx, 'log'):
                app.state.ctx.log.error(f"     -- Initialization error: {str(e)}")
            else:
                print(f"     -- Initialization error: {str(e)}")
            traceback.print_exc()
            raise
        
    @staticmethod
    async def _initialize_managers(ctx: AppContext) -> None:
        """매니저 초기화"""
        print("     - Initializing handlers...")   
        ctx._init_logger()
        AppFactory._test_logging(ctx.log)
        
        ctx._init_system_manager()

    @staticmethod
    async def _initialize_handlers(ctx: AppContext) -> None:
        """핸들러 초기화"""    
        ctx.log.info("     - Initializing handlers...")
        ctx._init_websocket()
        ctx._init_redis()
        ctx._init_redis_consumer()

    @staticmethod
    async def _initialize_algorithms(ctx: AppContext) -> None:
        """알고리즘 초기화"""
        print("     - Initializing algorithms...")   
        ctx._init_llms()

    @staticmethod
    async def _setup_connections(ctx: AppContext) -> None:
        """외부 서비스 연결 설정"""
        # Redis 연결
        await ctx.redis_handler.connect()
        await ctx.redis_consumer.init_group()
        
        ctx.redis_consumer_task = asyncio.create_task(ctx.redis_consumer.consume())
        await asyncio.sleep(0)  # 태스크가 시작되도록 제어권 양보   

    
    @staticmethod
    async def _shutdown(app: FastAPI) -> None:
        """애플리케이션 종료 시 정리"""
        ctx = app.state.ctx

        if hasattr(ctx, 'log') and ctx.log:
            ctx.log.info("     -- Shutting down application")

        # Redis 종료
        if hasattr(ctx, "redis_consumer") and ctx.redis_consumer:
            try:
                await ctx.redis_consumer.stop()
                ctx.log.info("     -- RedisStreamConsumer stopped")
            except Exception as e:
                ctx.log.warning(f"     - RedisStreamConsumer stop failed: {e}")
        if ctx.redis_handler:
            try:
                await ctx.redis_handler.disconnect()
                ctx.log.info("     -- Redis handler closed")
            except Exception as e:
                ctx.log.warning(f"     - Redis close failed: {e}")

        # WebSocket 종료
        if ctx.ws_handler:
            try:
                await ctx.ws_handler.disconnect_all()
                ctx.log.info("     -- WebSocket handler closed")
            except Exception as e:
                ctx.log.warning(f"     - WebSocket close failed: {e}")

        # 모니터링 종료
        if ctx.system_monitor:
            try:
                ctx.system_monitor.stop()
                ctx.log.info("     -- system monitor stopped")
            except Exception as e:
                ctx.log.warning(f"     - system monitor stop failed: {e}")

        # LLM 모델 정리
        # if hasattr(ctx, "llm_models") and ctx.llm_models:
        #     try:
        #         for name, model in ctx.llm_models.items():
        #             ctx.log.info(f"     -- LLM model '{name}' unloaded (model={getattr(model, 'model', 'unknown')})")
        #         ctx.llm_models.clear()
        #     except Exception as e:
        #         ctx.log.warning(f"     - LLM models cleanup failed: {e}")

    @staticmethod
    def _test_logging(logger) -> None:
        """로깅 테스트"""
        logger.info("===FILE LOG TEST START===")
        logger.debug("   -test debug level")
        logger.info("   -test info level")
        logger.warning("   -test warn level")
        logger.error("   -test error level")
        logger.info("===FILE LOG TEST END===")

# 애플리케이션 인스턴스 생성
app = AppFactory.create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.doq_be:app", host="0.0.0.0", port=9571, reload=True)