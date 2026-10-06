#!/bin/sh
set -e

echo "=========================================="
echo "  4GB SERVER - AI WEB GUI INSTALLER"
echo "  Open WebUI + llama.cpp + ngrok"
echo "=========================================="

# 1. Install dependencies
if command -v apk >/dev/null 2>&1; then
    apk update
    apk add --no-cache docker docker-cli-compose curl wget ca-certificates openssl tar gzip
elif command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y docker.io docker-compose-plugin curl wget ca-certificates openssl
else
    echo "ERROR: Unsupported package manager."
    exit 1
fi

# 2. Make sure Docker is running
service docker start 2>/dev/null || true
sleep 5

# 3. Create persistent directories/network
mkdir -p /opt/ai/models /opt/ai/open-webui /opt/ai/ngrok
docker network inspect ai-network >/dev/null 2>&1 || docker network create ai-network

# 4. Generate persistent WebUI secret
if [ ! -f /opt/ai/.webui-secret ]; then openssl rand -hex 32 > /opt/ai/.webui-secret; fi
WEBUI_SECRET="$(cat /opt/ai/.webui-secret)"

# 5. Remove old containers
docker rm -f open-webui llama-server >/dev/null 2>&1 || true

# 6. Start llama.cpp
docker pull ghcr.io/ggml-org/llama.cpp:server
docker run -d --name llama-server --restart unless-stopped --network ai-network -p 10000:10000 -v /opt/ai/models:/models ghcr.io/ggml-org/llama.cpp:server -hf Qwen/Qwen2.5-1.5B-Instruct-GGUF:Q4_K_M --host 0.0.0.0 --port 10000 --ctx-size 2048 --parallel 1 --threads 2

# 7. Start Open WebUI
docker pull ghcr.io/open-webui/open-webui:main
docker run -d --name open-webui --restart unless-stopped --network ai-network -p 8080:8080 -v /opt/ai/open-webui:/app/backend/data -e WEBUI_SECRET_KEY="$WEBUI_SECRET" ghcr.io/open-webui/open-webui:main

# 8. Install ngrok
ARCH="$(uname -m)"
NGROK_URL="https://bin.ngrok.com/c/bNyj1mQV4Yc/ngrok-v3-stable-linux-amd64.tgz"
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then NGROK_URL="https://bin.ngrok.com/c/bNyj1mQV4Yc/ngrok-v3-stable-linux-arm64.tgz"; fi
if ! command -v ngrok >/dev/null 2>&1; then
    curl -fsSL "$NGROK_URL" | tar -xz && install -m 755 ngrok /usr/local/bin/ngrok
fi

echo "=========================================="
echo " LOCAL AI SYSTEM READY at http://YOUR_SERVER_IP:8080"
echo "=========================================="
