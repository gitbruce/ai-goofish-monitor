#!/bin/bash
# 快速启动脚本（跳过环境检查，适合已配置好的环境）

cd "$(dirname "${BASH_SOURCE[0]}")"

# 从 .env 读取端口，默认 8000
SERVER_PORT=$(grep -E "^SERVER_PORT=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' "')
SERVER_PORT=${SERVER_PORT:-8000}

echo "快速启动服务..."

# 可选：重新构建前端（注释掉这行如果前端没变化）
cd web-ui && npm run build >/dev/null 2>&1 && cd ..

echo "访问地址: http://localhost:${SERVER_PORT}"
python3 -m src.app
