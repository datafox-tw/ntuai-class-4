#!/usr/bin/env bash
set -e

CONTAINER_NAME="agno_pgvector"
IMAGE="pgvector/pgvector:pg16"
DATA_DIR="$(pwd)/tmp/postgres_data"
HOST_PORT="5532"
DB_NAME="ai"
DB_USER="ai"
DB_PASSWORD="ai"

# 先確認 Docker Desktop 有啟動
if ! docker info >/dev/null 2>&1; then
  echo "Docker 還沒啟動，請先打開 Docker Desktop 後再試一次。"
  exit 1
fi

mkdir -p "$DATA_DIR"

# 已在執行就直接結束；有舊容器就啟動；都沒有才新建
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Memory DB 已經在執行中：postgresql://$DB_USER:$DB_PASSWORD@localhost:$HOST_PORT/$DB_NAME"
  exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker start "$CONTAINER_NAME" >/dev/null
else
  docker run -d \
    --name "$CONTAINER_NAME" \
    -e POSTGRES_DB="$DB_NAME" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -p "$HOST_PORT:5432" \
    -v "$DATA_DIR:/var/lib/postgresql/data" \
    "$IMAGE" >/dev/null
fi

# 等資料庫可連線（最多 30 秒）
for i in {1..30}; do
  if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    echo "Memory DB 已啟動：postgresql://$DB_USER:$DB_PASSWORD@localhost:$HOST_PORT/$DB_NAME"
    exit 0
  fi
  sleep 1
done

echo "資料庫容器已啟動，但尚未就緒，請 5 秒後再試一次。"
exit 1