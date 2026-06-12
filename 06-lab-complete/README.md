# Lab 12 — Production Legal RAG Agent

Final project được xây từ project Day 9 `Omelettia/Batch02-Day9_2A202600682_Nguyen_Tai_Khoa`: legal/RAG assistant về pháp luật phòng, chống ma túy và tin tức liên quan. Day 12 bổ sung lớp production: Docker, Redis state, auth, rate limiting, cost guard, health checks và cloud deployment.

## Checklist Deliverable

- [x] Dockerfile (multi-stage, < 500 MB)
- [x] docker-compose.yml (agent + redis + nginx)
- [x] .dockerignore
- [x] Health check endpoint (`GET /health`)
- [x] Readiness endpoint (`GET /ready`)
- [x] API Key authentication
- [x] Rate limiting
- [x] Cost guard
- [x] Config từ environment variables
- [x] Structured logging
- [x] Graceful shutdown
- [x] Public URL ready (Railway / Render config)

---

## Cấu Trúc

```
06-lab-complete/
├── app/
│   ├── main.py         # FastAPI entry point
│   ├── config.py       # 12-factor config
│   ├── auth.py         # API Key auth
│   ├── rate_limiter.py # Redis rate limiting
│   ├── cost_guard.py   # Redis budget protection
│   └── legal_rag.py    # Day 9 legal RAG core
├── data/
│   └── standardized/   # Day 9 legal/news markdown corpus
├── Dockerfile          # Multi-stage, production-ready
├── docker-compose.yml  # Full stack: agent + redis + nginx
├── nginx/
│   └── nginx.conf      # Load balancer
├── railway.toml        # Deploy Railway
├── render.yaml         # Deploy Render
├── .env.example        # Template
├── .dockerignore
└── requirements.txt
```

---

## Chạy Local

```bash
# 1. Setup
cp .env.example .env

# 2. Chạy với Docker Compose
docker compose up --build

# Hoặc test scale-out
docker compose up --build --scale agent=3

# 3. Test
curl http://localhost:8080/health

# 4. Lấy API key từ .env, test endpoint
API_KEY=$(grep AGENT_API_KEY .env | cut -d= -f2)
curl -H "X-API-Key: $API_KEY" \
     -X POST http://localhost:8080/ask \
     -H "Content-Type: application/json" \
     -d '{"user_id": "local-test", "question": "Luật Phòng, chống ma túy quy định những hành vi nào bị nghiêm cấm?"}'
```

---

## Deploy Railway (< 5 phút)

```bash
# Cài Railway CLI
npm i -g @railway/cli

# Login và deploy
railway login
railway init
railway variables set AGENT_API_KEY=your-secret-key
railway variables set JWT_SECRET=your-jwt-secret
railway variables set REDIS_URL=redis://...
railway up

# Nhận public URL
railway domain
```

Railway dashboard path:

1. New Project → Deploy from GitHub repo.
2. Set service root directory to `06-lab-complete`.
3. Add Redis from `+ New`.
4. Set web service `REDIS_URL` to the Redis service variable.
5. Generate a Railway domain and test `/health`.

---

## Deploy Render

1. Push repo lên GitHub
2. Render Dashboard → New → Blueprint
3. Connect repo → Render đọc `render.yaml`
4. Set secrets: `OPENAI_API_KEY`, `AGENT_API_KEY`
5. Deploy → Nhận URL!

---

## Kiểm Tra Production Readiness

```bash
python check_production_ready.py
```

Script này kiểm tra tất cả items trong checklist và báo cáo những gì còn thiếu.
