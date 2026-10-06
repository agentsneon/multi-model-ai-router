#!/bin/sh
set -eu
export API_KEY="123456789"
exec uvicorn router.main:app --host 0.0.0.0 --port 8081
