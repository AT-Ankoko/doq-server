#!/bin/bash
# 빠른 테스트 스크립트 - WebSocket 채팅 시뮬레이션

set -e

PROJECT_DIR="/Users/eunbee/Documents/GitHub/doq-server"
TEST_DIR="$PROJECT_DIR/test"
cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         WebSocket Chat 테스트 - 빠른 시작                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. 가상환경 활성화 확인
echo "📦 Python 환경 확인..."
if [ ! -d "py_env" ]; then
    echo "❌ py_env 디렉토리를 찾을 수 없습니다."
    exit 1
fi

source py_env/bin/activate
echo "✓ Python 환경 활성화됨"
echo ""

# 2. Redis 연결 확인
echo "🔴 Redis 연결 확인..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis가 실행 중이 아닙니다."
    echo "    Redis를 시작하세요: redis-server"
    echo ""
    read -p "계속하시겠습니까? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ Redis 연결 성공"
fi
echo ""

# 3. 서버 상태 확인
echo "🚀 서버 상태 확인..."
if lsof -i :3000 > /dev/null 2>&1; then
    echo "✓ 서버가 이미 포트 3000에서 실행 중입니다."
    read -p "새로운 서버를 시작하시겠습니까? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔄 기존 프로세스 종료..."
        lsof -ti :3000 | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
else
    echo "ℹ️  포트 3000이 비어있습니다."
fi
echo ""

# 4. 테스트 선택
echo "테스트 방법을 선택하세요:"
echo "1) Python 자동 테스트 (권장)"
echo "2) Redis 메시지 확인만 하기"
echo "3) wscat 수동 테스트 (별도 터미널 필요)"
echo "4) 모두 실행"
read -p "선택 (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🧪 Python 테스트 시작..."
        echo ""
        python "$TEST_DIR/test_websocket_chat.py"
        ;;
    2)
        echo ""
        echo "📊 Redis 메시지 확인..."
        echo ""
        python "$TEST_DIR/check_redis_chat.py" test_room_001
        ;;
    3)
        echo ""
        echo "📝 wscat 수동 테스트 준비..."
        echo ""
        echo "wscat 설치 확인..."
        if ! command -v wscat &> /dev/null; then
            echo "wscat을 설치하시겠습니까? (y/n) "
            read -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                npm install -g wscat
            else
                echo "wscat 설치를 건너뜁니다."
                exit 0
            fi
        fi
        
        echo ""
        echo "✓ wscat 명령어를 실행하세요 (별도 터미널):"
        echo ""
        echo "  터미널 1:"
        echo "    wscat -c 'ws://localhost:3000/v1/session/chat?sid=room001'"
        echo ""
        echo "  메시지 입력 예:"
        echo '    {"hd": {"event": "chat.message", "role": "A"}, "bd": {"text": "안녕"}}'
        echo ""
        echo "  다른 터미널에서:"
        echo "    wscat -c 'ws://localhost:3000/v1/session/chat?sid=room001'"
        echo ""
        ;;
    4)
        echo ""
        echo "🧪 모든 테스트 실행..."
        echo ""
        
        echo "1️⃣  Python 테스트..."
        python "$TEST_DIR/test_websocket_chat.py"
        echo ""
        
        echo "2️⃣  Redis 메시지 확인..."
        python "$TEST_DIR/check_redis_chat.py" test_room_001
        echo ""
        
        echo "✓ 모든 테스트 완료!"
        ;;
    *)
        echo "❌ 잘못된 선택입니다."
        exit 1
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    테스트 완료                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📖 더 자세한 정보: test/TEST_GUIDE.md 참고"
echo ""
