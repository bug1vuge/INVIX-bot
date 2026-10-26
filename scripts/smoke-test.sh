#!/usr/bin/env bash
# End-to-end check of the whole stack in Docker: routing, product creation,
# idempotency, image delivery, webhook and failover of every stateless service.
#
#   ./scripts/smoke-test.sh          # expects .env next to compose.yaml
#
# Uses only the public gateway port and the internal docker network, the
# Telegram token may be fake (the bot never needs to reach Telegram here).
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a

PROJECT=catalog
BASE="http://localhost:${HTTP_PORT:-80}"
NETWORK="${PROJECT}_default"
CURL_IMAGE=curlimages/curl:8.11.1
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

step() { printf '\n==> %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

expect_status() {
  local expected=$1 actual=$2 what=$3
  [[ "$actual" == "$expected" ]] || fail "$what: expected HTTP $expected, got $actual"
  echo "ok  $what -> $actual"
}

# curl inside the compose network, for the internal gateway listener.
internal_curl() {
  docker run --rm --network "$NETWORK" -v "$WORKDIR:/data:ro" "$CURL_IMAGE" -sS "$@"
}

wait_for() {
  local url=$1 timeout=${2:-180} started=$SECONDS
  until [[ "$(curl -s -o /dev/null -w '%{http_code}' "$url")" == "200" ]]; do
    (( SECONDS - started > timeout )) && fail "$url did not become ready in ${timeout}s"
    sleep 2
  done
  echo "ok  $url is ready after $(( SECONDS - started ))s"
}

webhook_update() {
  local update_id=$1
  printf '{"update_id":%s,"message":{"message_id":%s,"date":%s,"chat":{"id":1,"type":"private"},"from":{"id":1,"is_bot":false,"first_name":"Smoke"},"text":"/start"}}' \
    "$update_id" "$update_id" "$(date +%s)"
}

post_webhook() {
  curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE${WEBHOOK_PATH:-/bot/webhook}" \
    -H 'Content-Type: application/json' \
    -H "X-Telegram-Bot-Api-Secret-Token: $2" \
    -d "$(webhook_update "$1")"
}

# A real 4x3 PNG built with the standard library only.
python3 - "$WORKDIR/product.png" <<'PY'
import struct, sys, zlib
w, h = 4, 3
raw = b"".join(b"\x00" + b"\xd0\x40\x40" * w for _ in range(h))
def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) \
    + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
open(sys.argv[1], "wb").write(png)
PY

step "Start the stack"
docker compose -p "$PROJECT" up -d --build gateway api bot web
wait_for "$BASE/api/v1/products"
wait_for "$BASE/healthz"

step "Replicas"
for service in api bot web; do
  running=$(docker compose -p "$PROJECT" ps --status running -q "$service" | wc -l)
  (( running >= 2 )) || fail "$service has $running running replicas, expected at least 2"
  echo "ok  $service: $running replicas"
done
migrate_exit=$(docker inspect -f '{{.State.ExitCode}}' "${PROJECT}-migrate-1")
[[ "$migrate_exit" == "0" ]] || fail "migrate job exited with code $migrate_exit"
echo "ok  migrate job finished with code 0"

step "Public API is read-only"
status=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/v1/products" -F name=x -F image=@"$WORKDIR/product.png")
expect_status 403 "$status" "POST /api/v1/products from outside"

step "Create a product through the internal listener"
created=$(docker run --rm --network "$NETWORK" -v "$WORKDIR:/data" "$CURL_IMAGE" -sS \
  -o /data/created.json -w '%{http_code}' -X POST http://gateway:8081/api/v1/products \
  -H "Authorization: Bearer $SERVICE_TOKEN" -H "Idempotency-Key: smoke:1" \
  -F "name=Smoke test product" -F "image=@/data/product.png")
expect_status 201 "$created" "create product"
replayed=$(docker run --rm --network "$NETWORK" -v "$WORKDIR:/data" "$CURL_IMAGE" -sS \
  -o /data/replayed.json -w '%{http_code}' -X POST http://gateway:8081/api/v1/products \
  -H "Authorization: Bearer $SERVICE_TOKEN" -H "Idempotency-Key: smoke:1" \
  -F "name=Smoke test product" -F "image=@/data/product.png")
expect_status 200 "$replayed" "repeat with the same Idempotency-Key"
product_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$WORKDIR/created.json")
replay_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$WORKDIR/replayed.json")
[[ "$product_id" == "$replay_id" ]] || fail "replay created a second product"
echo "ok  same product returned: $product_id"
unauthorized=$(internal_curl -o /dev/null -w '%{http_code}' -X POST http://gateway:8081/api/v1/products \
  -F name=x -F "image=@/data/product.png")
expect_status 401 "$unauthorized" "create without service token"

step "Catalog shows the product"
image_url=$(curl -s "$BASE/api/v1/products/$product_id" | python3 -c 'import json,sys; print(json.load(sys.stdin)["image_url"])')
image_type=$(curl -s -o /dev/null -w '%{content_type}' "$BASE$image_url")
[[ "$image_type" == "image/png" ]] || fail "image $image_url served as '$image_type'"
echo "ok  $image_url -> $image_type"
page=$(curl -s "$BASE/")
grep -q "Каталог" <<<"$page" || fail "page has no title"
grep -q "Smoke test product" <<<"$page" || fail "page does not list the product"
echo "ok  / renders the catalog with the product"

step "Webhook"
expect_status 401 "$(post_webhook 100 wrong-secret)" "webhook with wrong secret"
expect_status 200 "$(post_webhook 101 "$WEBHOOK_SECRET")" "webhook with valid secret"

step "Load is spread across replicas"
docker compose -p "$PROJECT" up -d --no-recreate --scale api=3 api
sleep 8
for _ in $(seq 1 30); do curl -s -o /dev/null "$BASE/api/v1/products?limit=1"; done
upstreams=$(docker compose -p "$PROJECT" logs --no-log-prefix --since 30s gateway \
  | grep '"uri":"/api/v1/products?limit=1"' \
  | python3 -c 'import json,sys; print(len({json.loads(l)["upstream"] for l in sys.stdin if l.startswith("{")}))')
(( upstreams >= 3 )) || fail "requests reached only $upstreams api replicas"
echo "ok  30 requests reached $upstreams api replicas"

step "Failover: kill one replica of every service"
docker kill "${PROJECT}-api-1" "${PROJECT}-bot-1" "${PROJECT}-web-1" >/dev/null
errors=0
for i in $(seq 1 30); do
  for url in "$BASE/api/v1/products" "$BASE/"; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url")
    [[ "$code" == "200" ]] || { echo "  $url -> $code"; errors=$((errors + 1)); }
  done
  code=$(post_webhook $((200 + i)) "$WEBHOOK_SECRET")
  [[ "$code" == "200" ]] || { echo "  webhook -> $code"; errors=$((errors + 1)); }
done
(( errors == 0 )) || fail "$errors failed requests after killing replicas"
echo "ok  90 requests after the kill, all succeeded"

step "Killed replicas come back"
docker start "${PROJECT}-api-1" "${PROJECT}-bot-1" "${PROJECT}-web-1" >/dev/null
wait_for "$BASE/api/v1/products" 60

printf '\nAll smoke checks passed.\n'
