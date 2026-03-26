#!/usr/bin/env bash
set -e

CONTAINER_NAME="qdrant"
STORAGE_DIR="$(pwd)/tmp/qdrant_storage"

# 先確認 Docker Desktop 有啟動
if ! docker info >/dev/null 2>&1; then
  echo "Docker 還沒啟動，請先打開 Docker Desktop 後再試一次。"
  exit 1
fi

mkdir -p "$STORAGE_DIR"

# 已在執行就直接結束；有舊容器就啟動；都沒有才新建
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Qdrant 已經在執行中：http://localhost:6333"
  exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker start "$CONTAINER_NAME" >/dev/null
  echo "Qdrant 已啟動：http://localhost:6333"
  exit 0
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  -p 6333:6333 \
  -p 6334:6334 \
  -v "$STORAGE_DIR:/qdrant/storage:z" \
  qdrant/qdrant >/dev/null

echo "Qdrant 已啟動：http://localhost:6333"