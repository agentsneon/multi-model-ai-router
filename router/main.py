import os, json, time, signal, subprocess, asyncio
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

APP = Path(os.getcwd())
CONFIG = APP / "config" / "models.json"
LOG = APP / "logs" / "llama.log"

MODELS = {
    "chat": {"hf": "ggml-org/Qwen3-1.7B-GGUF:Q4_K_M", "description": "General chat and reasoning"},
    "fast": {"hf": "ggml-org/Qwen3-0.6B-GGUF:Q4_0", "description": "Ultra-light fast chat"},
    "coding": {"hf": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K_M", "description": "Main coding model"},
    "light-coding": {"hf": "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF:Q4_K_M", "description": "Lightweight coding"},
    "math-science": {"hf": "ggml-org/SmolLM3-3B-GGUF:Q4_K_M", "description": "Math, science and harder reasoning"}
}

API_KEY = "123456789"
PUBLIC_PORT = 8081
BACKEND_PORT = 8090

process = None
current_model = None
model_lock = asyncio.Lock()

app = FastAPI(title="Multi-Model AI Router", version="1.0.0", description="OpenAI-compatible multi-model llama.cpp router")

def auth(request: Request):
    supplied = request.headers.get("authorization", "")
    if supplied.startswith("Bearer "): supplied = supplied[7:]
    if supplied != API_KEY: raise HTTPException(status_code=401, detail="Invalid API key")

def stop_backend():
    global process, current_model
    if process is not None:
        try: process.terminate(); process.wait(timeout=8)
        except Exception:
            try: process.kill()
            except Exception: pass
    process = None; current_model = None

def backend_alive():
    if process is None: return False
    return process.poll() is None

async def wait_backend():
    for _ in range(120):
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                r = await client.get(f"http://127.0.0.1:{BACKEND_PORT}/health")
                if r.status_code == 200: return True
        except Exception: pass
        await asyncio.sleep(1)
    return False

async def start_model(model_name):
    global process, current_model
    if model_name not in MODELS: raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")
    async with model_lock:
        if current_model == model_name and backend_alive(): return
        stop_backend()
        hf = MODELS[model_name]["hf"]
        LOG.parent.mkdir(parents=True, exist_ok=True)
        logfile = open(LOG, "a")
        process = subprocess.Popen(["llama", "serve", "-hf", hf, "--host", "127.0.0.1", "--port", str(BACKEND_PORT), "--ctx-size", "2048", "--parallel", "1", "--metrics"], stdout=logfile, stderr=subprocess.STDOUT)
        current_model = model_name
        ok = await wait_backend()
        if not ok:
            stop_backend()
            raise HTTPException(status_code=503, detail=f"Failed to start model: {model_name}")

@app.post("/v1/chat/completions")
async def completions(request: Request):
    auth(request)
    data = await request.json()
    model = data.get("model", "chat")
    await start_model(model)
    async with httpx.AsyncClient(timeout=600) as client:
        response = await client.post(f"http://127.0.0.1:{BACKEND_PORT}/v1/chat/completions", json=data)
    return JSONResponse(content=response.json(), status_code=response.status_code)
