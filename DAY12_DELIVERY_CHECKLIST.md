# Delivery Checklist - Day 12 Lab Submission

> **Student Name:** Nguyen Tai Khoa  
> **Student ID:** 2A202600682  
> **Date:** 2026-06-12

---

## Submission Requirements

Submit a GitHub repository containing the completed mission answers, final production agent, and deployment information.

Repository:

```text
https://github.com/Omelettia/batch02-day12_202600682_Nguyen_Tai_Khoa
```

## 1. Mission Answers (40 points)

- [x] `MISSION_ANSWERS.md` exists.
- [x] Part 1 answers completed: localhost anti-patterns and comparison table.
- [x] Part 2 answers completed: Dockerfile questions, multi-stage notes, image size.
- [x] Part 3 notes completed: Railway chosen as deployment target.
- [x] Part 4 answers completed: API key auth, JWT notes, rate limiting, cost guard.
- [x] Part 5 answers completed: health/readiness, graceful shutdown, Redis stateless design, load balancing.
- [x] Local test evidence included.

Local validation recorded:

```text
Production checker: 20/20
Docker image size: 220MB
Rate limit result: 10 successful requests, then 429
Load balancing: requests served by all 3 agent replicas
```

## 2. Full Source Code - Lab 06 Complete (60 points)

Final project:

```text
06-lab-complete/
```

Required files:

- [x] `app/main.py`
- [x] `app/config.py`
- [x] `app/auth.py`
- [x] `app/rate_limiter.py`
- [x] `app/cost_guard.py`
- [x] `app/legal_rag.py`
- [x] `app/static/index.html`
- [x] `app/static/styles.css`
- [x] `app/static/app.js`
- [x] `utils/mock_llm.py`
- [x] `Dockerfile`
- [x] `docker-compose.yml`
- [x] `requirements.txt`
- [x] `.env.example`
- [x] `.dockerignore`
- [x] `railway.toml`
- [x] `README.md`

Requirements:

- [x] All code compiles without errors.
- [x] Multi-stage Dockerfile.
- [x] Docker image is under 500 MB (`220MB`).
- [x] API key authentication.
- [x] Rate limiting (`10 req/min`).
- [x] Cost guard (`$10/month`).
- [x] Health and readiness checks.
- [x] Graceful shutdown.
- [x] Stateless design using Redis.
- [x] No hardcoded secrets.
- [x] Gemini key and model are configured by environment variables.
- [x] Uses previous Day 9 project as product base: Vietnamese legal RAG corpus and cited legal answers.

## 3. Service Domain Link

- [x] `DEPLOYMENT.md` exists.
- [x] Railway deployment instructions documented.
- [x] Local test commands documented.
- [x] Public Railway URL added after successful deploy.
- [x] Public URL `/health` tested from outside local machine.
- [x] Public URL `/ready` tested after Railway Redis is connected.
- [x] Public frontend `/demo/ask` tested successfully with Gemini model response and source citation.
- [x] Public protected `/ask` authentication gate tested: returns HTTP 401 without `X-API-Key`.
- [ ] Screenshots added to repository after successful Railway deploy.

Public deployment:

```text
Public URL: https://batch02-day12202600682nguyentaikhoa-production.up.railway.app
GET /health -> HTTP 200
GET /ready -> HTTP 200, {"ready": true, "storage": "redis"}
POST /demo/ask -> HTTP 200, model gemini-3.5-flash, source 73_2021_QH14_445185.md
POST /ask without X-API-Key -> HTTP 401
```

## Pre-Submission Checklist

- [ ] Repository is public, or instructor has access.
- [x] `MISSION_ANSWERS.md` completed with all exercises.
- [x] `DEPLOYMENT.md` has public Railway URL.
- [x] Final source code is in `06-lab-complete/app/`.
- [x] `06-lab-complete/README.md` has setup instructions.
- [x] No `.env` file committed, only `.env.example`.
- [x] No hardcoded secrets in code.
- [x] Public URL `/health` is accessible and working.
- [x] Public `/ready` is working after Redis variable fix.
- [x] Public frontend demo is working with Gemini and cited source.
- [x] Protected `/ask` endpoint rejects missing API key on Railway.
- [ ] Screenshots included in `screenshots/` folder.
- [x] Repository has clear commit history.

## Self-Test

Local Docker tests completed:

```bash
cd 06-lab-complete
docker compose up --build --scale agent=3 -d
```

Health check:

```bash
curl http://localhost:8080/health
# HTTP/1.1 200 OK
```

Readiness check:

```bash
curl http://localhost:8080/ready
# HTTP/1.1 200 OK
```

Authentication required:

```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# HTTP/1.1 401 Unauthorized
```

Authenticated API test:

```bash
curl -X POST http://localhost:8080/ask \
  -H "X-API-Key: local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"legal-test","question":"Luật Phòng, chống ma túy quy định những hành vi nào bị nghiêm cấm?"}'
# HTTP/1.1 200 OK
# Answer cites 73_2021_QH14_445185.md
```

Rate limiting:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

## Railway Deployment Checklist

- [x] `railway.toml` uses Dockerfile builder.
- [x] Railway start command wraps `$PORT` in `/bin/sh -c`.
- [x] Dockerfile command also supports `${PORT:-8000}`.
- [x] Push latest commits to GitHub.
- [x] Railway project connected to GitHub repo.
- [x] Railway service root set to `06-lab-complete`.
- [x] Railway Redis service added.
- [x] Web service variables set:

```text
ENVIRONMENT=production
APP_NAME=Vietnam Drug Law RAG Agent
AGENT_API_KEY=<secret>
JWT_SECRET=<secret>
LLM_PROVIDER=gemini
GEMINI_API_KEY=<secret>
GEMINI_MODEL=gemini-3.5-flash
RATE_LIMIT_PER_MINUTE=10
MONTHLY_BUDGET_USD=10.0
REDIS_URL=${{Redis.REDIS_URL}}
```

- [x] Railway domain generated.
- [x] `/health` tested on Railway domain.
- [x] `/ready` tested on Railway domain after Redis variable fix.
- [x] `/demo/ask` tested on Railway domain with Gemini response.
- [x] `/ask` auth gate tested on Railway domain without API key.

## Submission

Submit the GitHub repository URL:

```text
https://github.com/Omelettia/batch02-day12_202600682_Nguyen_Tai_Khoa
```

Deadline from original checklist: `17/4/2026`.
