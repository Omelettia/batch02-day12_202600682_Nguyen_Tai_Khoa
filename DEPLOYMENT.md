# Deployment Information

## Public URL

https://batch02-day12202600682nguyentaikhoa-production.up.railway.app

## Platform

Deployed: Railway.

Railway health, readiness, and frontend demo verified on 2026-06-12. Redis is connected through the Railway Redis service, and the frontend demo returns a Gemini model response with a cited Day 9 legal source.

Local Docker validation completed with `docker compose up --build --scale agent=3 -d`.

Local URL:

```text
http://localhost:8080
```

## Test Commands

Public URL:

```text
https://batch02-day12202600682nguyentaikhoa-production.up.railway.app
```

### Health Check

```bash
curl https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/health
```

Expected: HTTP 200 with `"status": "ok"`.

Local result:

```text
HTTP/1.1 200 OK
{"status":"ok", ...}
```

Railway result:

```text
HTTP/2 200
{"status":"ok","version":"1.0.0","environment":"production", ...}
```

### Readiness Check

```bash
curl https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/ready
```

Expected: HTTP 200 with `"ready": true`.

Railway result:

```text
HTTP/2 200
{"ready":true,"storage":"redis","instance_id":"agent-996d5c26"}
```

Local result:

```text
HTTP/1.1 200 OK
{"ready":true,"storage":"redis", ...}
```

### API Test Without Authentication

```bash
curl -X POST https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Luật Phòng, chống ma túy quy định gì?"}'
```

Expected: HTTP 401.

Local result:

```text
HTTP/1.1 401 Unauthorized
{"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}
```

### API Test With Authentication

```bash
curl -X POST https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Luật Phòng, chống ma túy quy định gì?"}'
```

Expected: HTTP 200 with a cited legal RAG answer. If `GEMINI_API_KEY` is set, the `model` field shows the configured Gemini model; otherwise it uses the local extractive fallback.

Local result: HTTP 200 with a cited legal RAG answer.

### Legal RAG Citation Test

```bash
curl -X POST https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "legal-test", "question": "Những hành vi nào bị nghiêm cấm theo Luật Phòng, chống ma túy?"}'

curl -X POST https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "legal-test", "question": "Câu trước có liên quan gì tới cai nghiện ma túy?"}'
```

Expected: responses include cited sources from the local Day 9 legal/news corpus.

### Example Legal Query

```bash
curl -X POST https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "question": "Luật Phòng, chống ma túy quy định những hành vi nào bị nghiêm cấm?"}'
```

Expected: answer cites `73_2021_QH14_445185.md`.

### Public Frontend API Test

```bash
curl -X POST https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/demo/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "question": "Luật Phòng, chống ma túy quy định những hành vi nào bị nghiêm cấm?"}'
```

Expected: HTTP 200. This route is for the browser UI and is still rate limited/cost guarded server-side.

Railway result:

```text
HTTP/2 200
model: gemini-3.5-flash
source: 73_2021_QH14_445185.md
```

### Frontend

Open:

```text
https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/
```

`/` serves the browser UI and `/api` serves machine-readable service metadata.

### Rate Limit Test

```bash
for i in {1..15}; do
  curl -X POST https://batch02-day12202600682nguyentaikhoa-production.up.railway.app/ask \
    -H "X-API-Key: YOUR_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"rate-test\",\"question\":\"test $i\"}"
  echo
done
```

Expected: eventually returns HTTP 429.

Local result:

```text
200 200 200 200 200 200 200 200 200 200 429 429
```

## Environment Variables Set

- `PORT`
- `REDIS_URL`
- `AGENT_API_KEY`
- `JWT_SECRET`
- `LLM_PROVIDER=gemini`
- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-3.5-flash`
- `LOG_LEVEL`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10.0`
- `ENVIRONMENT=production`

## Railway Setup Notes

1. Create a new Railway project from the GitHub repository.
2. Set the service root directory to `06-lab-complete`.
3. Railway should use `railway.toml` and the Dockerfile build.
4. Add a Redis database service in the same Railway project.
5. In the web service variables, set:

```text
ENVIRONMENT=production
APP_NAME=Vietnam Drug Law RAG Agent
AGENT_API_KEY=<generated-secret>
JWT_SECRET=<generated-secret>
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL=gemini-3.5-flash
RATE_LIMIT_PER_MINUTE=10
MONTHLY_BUDGET_USD=10.0
REDIS_URL=${{Redis.REDIS_URL}}
```

Railway provides `REDIS_URL` from the Redis service. `GEMINI_MODEL` is configurable; use the model name available in your Gemini API account.

## Screenshots

Included after deployment:

- `screenshots/test.png`: Railway frontend demo with Gemini response and legal source citation.
- `screenshots/test.svg`: source file used to render the PNG artifact.
