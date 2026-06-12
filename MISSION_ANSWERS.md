# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

In `01-localhost-vs-production/develop/app.py`:

1. Hardcoded `OPENAI_API_KEY` in source code.
2. Hardcoded `DATABASE_URL` with username and password in source code.
3. Debug mode is always enabled with `DEBUG = True` and `reload=True`.
4. The app logs sensitive information with `print(f"[DEBUG] Using key: ...")`.
5. No `/health` endpoint, so a cloud platform cannot reliably restart unhealthy containers.
6. Host is fixed to `localhost`, which is not reachable from outside a container.
7. Port is fixed to `8000` instead of using the platform-provided `PORT` environment variable.
8. Configuration values are scattered in code instead of being loaded from environment variables.
9. No graceful shutdown handling for SIGTERM.
10. Uses `print()` instead of structured logging.

### Exercise 1.2: Basic version observation

The basic version can run locally and answer a request, but it is not production-ready because it depends on localhost-only settings, hardcoded secrets, debug reload, and has no health/readiness behavior.

Expected test:

```bash
cd 01-localhost-vs-production/develop
python app.py
curl -X POST "http://localhost:8000/ask?question=hello"
```

Expected result: HTTP 200 with a mock LLM answer.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Config | Hardcoded constants | Centralized config from environment | Cloud platforms inject settings through env vars, so the same image can run in dev/staging/prod. |
| Secrets | API key and DB password in code | Secrets read from env vars | Prevents leaking credentials in GitHub and allows rotation without code changes. |
| Host | `localhost` | `0.0.0.0` | Containers must listen on all interfaces so reverse proxies and cloud routers can reach them. |
| Port | Fixed `8000` | Uses `PORT` env var | Railway/Render/Cloud Run choose the runtime port dynamically. |
| Health check | Missing | `GET /health` | Platforms need a liveness probe to restart failed instances. |
| Readiness check | Missing | `GET /ready` | Load balancers should only send traffic after startup dependencies are ready. |
| Logging | `print()` and logs secrets | Structured JSON logs, no secrets | JSON logs are searchable and safe for production log systems. |
| Shutdown | Abrupt process stop | SIGTERM/lifespan shutdown handling | Lets in-flight requests finish during deploys or scale-down. |
| Debug mode | Always on | Controlled by `DEBUG` | Debug reload is unsafe and wasteful in production. |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image: `python:3.11`.
2. Working directory: `/app`.
3. `COPY requirements.txt` happens before copying the app code so Docker can reuse the dependency-install layer when only source code changes.
4. `CMD` supplies the default command for the container and can be overridden at runtime. `ENTRYPOINT` defines the main executable and is harder to override; it is useful when the image should always run one program.

### Exercise 2.2: Build and run

Expected commands:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
docker images my-agent:develop
```

Result captured locally with the final project image:

```bash
docker images 06-lab-complete-agent:latest --format '{{.Repository}}:{{.Tag}} {{.Size}}'
# 06-lab-complete-agent:latest 220MB
```

The image is under the 500 MB target.

### Exercise 2.3: Multi-stage build

In `02-docker/production/Dockerfile`:

- Stage 1, `builder`: starts from `python:3.11-slim`, installs build dependencies, and installs Python packages into `/root/.local`.
- Stage 2, `runtime`: starts from a clean `python:3.11-slim`, creates a non-root user, copies only installed packages and application files, and runs Uvicorn.
- The image is smaller because compiler tools, apt cache, and other build-only layers are left behind in the builder stage.

Expected comparison:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images | grep my-agent
```

Final project image size after optimization: `220 MB`. This is below the 500 MB production target.

### Exercise 2.4: Docker Compose stack

Architecture:

```text
Client
  |
  v
Nginx reverse proxy / load balancer
  |
  v
Agent service
  |
  v
Redis / supporting services
```

Services started by the production stack include the agent, Redis, and Nginx. Nginx receives public HTTP traffic and proxies it to the internal agent service. The agent uses Redis for shared state such as session/history, rate limiting, or cache data.

Final Docker Compose stack result:

```bash
cd 06-lab-complete
docker compose up --build --scale agent=3 -d
docker compose ps
```

Observed services:

- `agent`: 3 healthy replicas.
- `redis`: healthy.
- `nginx`: running on `localhost:8080`.

Health check:

```bash
curl -i http://localhost:8080/health
# HTTP/1.1 200 OK
# {"status":"ok", ...}
```

Agent endpoint:

```bash
curl -i -X POST http://localhost:8080/ask \
  -H "X-API-Key: local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"legal-test","question":"Luật Phòng, chống ma túy quy định những hành vi nào bị nghiêm cấm?"}'
# HTTP/1.1 200 OK
# Answer cites 73_2021_QH14_445185.md.
```

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

Planned platform command flow:

```bash
cd 03-cloud-deployment/railway
railway login
railway init
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
railway up
railway domain
```

Status: not deployed yet. We will use Railway for the final public deployment because the user already has a Railway Hobby account.

### Exercise 3.2: Render comparison

`railway.toml` is a small app-level deployment config. It defines the builder/start command, health check path, and restart policy. Secrets and service wiring are usually configured through Railway project variables and attached services.

`render.yaml` is a fuller infrastructure-as-code blueprint. It can define the web service, runtime, region, plan, build command, start command, health check path, generated secrets, and Redis service in one file.

Key difference: Render's blueprint can declare multiple services together, while Railway's config is lighter and relies more on project resources and environment variables configured in the Railway dashboard/CLI.

### Exercise 3.3: Optional GCP Cloud Run

The Cloud Run files show a production CI/CD style deployment: Cloud Build builds the container and applies a Cloud Run service definition. This is more production-oriented than Railway/Render but needs more setup: GCP project, billing, IAM, build config, and service YAML.

## Part 4: API Security

### Exercise 4.1: API key authentication

In `04-api-gateway/develop/app.py`, API key checking happens in the `verify_api_key` dependency:

- It reads the `X-API-Key` header using `APIKeyHeader`.
- Missing key returns HTTP 401.
- Wrong key returns HTTP 403.
- Valid key allows the `/ask` endpoint to run.

Key rotation approach: set a new `AGENT_API_KEY` environment variable in the deployment platform and redeploy/restart. For zero downtime, support two keys temporarily, then remove the old key after clients migrate.

Expected tests:

```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 401

curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 200
```

### Exercise 4.2: JWT authentication

In `04-api-gateway/production/auth.py`, the JWT flow is:

1. User posts username/password to `/auth/token`.
2. `authenticate_user` validates credentials.
3. `create_token` signs a JWT with `sub`, `role`, `iat`, and `exp`.
4. Protected endpoints use `verify_token` to decode and validate the bearer token.
5. Expired tokens return 401; invalid tokens return 403.

### Exercise 4.3: Rate limiting

The production security example uses a sliding-window rate limiter backed by timestamp deques:

- User tier: 10 requests per 60 seconds.
- Admin tier: 100 requests per 60 seconds.
- Admin bypass is implemented by selecting `rate_limiter_admin` for users with role `admin`.
- When the limit is exceeded, the API returns HTTP 429 with rate-limit headers.

### Exercise 4.4: Cost guard implementation

The final project implements a Redis-backed monthly cost guard in `06-lab-complete/app/cost_guard.py`:

- Budget key format: `budget:{user_id}:{YYYY-MM}`.
- Budget limit: `$10/month` per user by default.
- Token cost is estimated before recording usage.
- If estimated usage would exceed budget, the API returns HTTP 402.
- Redis keys expire after 32 days so monthly usage resets automatically.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

The final project implements:

- `GET /health`: liveness probe, returns process status and uptime.
- `GET /ready`: readiness probe, checks Redis connectivity and returns 503 if the service is not ready.

### Exercise 5.2: Graceful shutdown

The app uses FastAPI lifespan shutdown and a SIGTERM handler:

- Marks the service as not ready.
- Lets Uvicorn handle graceful shutdown with `timeout_graceful_shutdown=30`.
- Closes the Redis client during lifespan cleanup.

### Exercise 5.3: Stateless design

The final project stores state in Redis:

- Conversation history: Redis list `history:{user_id}`.
- Rate limiting: Redis sorted set `rate:{user_id}`.
- Monthly budget: Redis key `budget:{user_id}:{YYYY-MM}`.

This allows any scaled agent instance to serve the next request for the same user.

### Exercise 5.4: Load balancing

The final `06-lab-complete/docker-compose.yml` runs:

- `agent`: internal FastAPI service, scalable with `--scale agent=3`.
- `redis`: shared state store.
- `nginx`: public reverse proxy/load balancer on port 80.

Expected command:

```bash
cd 06-lab-complete
docker compose up --build --scale agent=3 -d
```

Observed `served_by` values across six requests:

```text
agent-ef85469d
agent-c92d44b1
agent-c401e666
agent-ef85469d
agent-c92d44b1
agent-c401e666
```

This confirms Nginx distributes requests across the three replicas.

### Exercise 5.5: Test stateless

The stateless test should:

1. Send a request with `user_id`.
2. Send a follow-up request for the same `user_id`.
3. Confirm the second response can use prior conversation history even if a different agent instance serves it.

The final project stores conversation history in Redis under `history:{user_id}`. During local Compose testing, all three replicas were serving traffic while using the same Redis instance.

Rate limit state is also Redis-backed. Local test result for 12 requests with the same `user_id`:

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

## Part 6: Final Project

### Implementation summary

The final project uses the previous Day 9 legal RAG/multi-agent work (`Omelettia/Batch02-Day9_2A202600682_Nguyen_Tai_Khoa`) as the product base. Instead of submitting a generic mock chatbot, the completed service is a production-ready Vietnamese drug-law RAG assistant using the Day 9 standardized legal/news markdown corpus.

The completed production agent is in `06-lab-complete` and includes:

- `app/main.py`: FastAPI entry point.
- `app/config.py`: environment-based configuration.
- `app/auth.py`: API key authentication.
- `app/rate_limiter.py`: Redis sliding-window rate limiting.
- `app/cost_guard.py`: Redis monthly budget guard.
- `app/legal_rag.py`: lightweight RAG core adapted from Day 9, with optional Gemini generation from retrieved sources.
- `app/static/`: browser frontend for the public Railway URL.
- `utils/mock_llm.py`: retained offline mock utility from the lab template.
- `data/standardized/legal`: copied Day 9 legal markdown corpus.
- `data/standardized/news`: copied Day 9 news markdown corpus.
- `Dockerfile`: multi-stage build with non-root runtime user.
- `docker-compose.yml`: agent, Redis, and Nginx stack.
- `nginx/nginx.conf`: reverse proxy/load balancer.
- `.env.example`: environment template.
- `railway.toml` and `render.yaml`: deployment configs.

The `/ask` endpoint now returns a legal RAG answer with source citations and source metadata, while still satisfying all Day 12 production requirements.

### Local validation completed

```bash
python -m compileall 06-lab-complete/app 06-lab-complete/utils
# Result: all files compiled successfully.

python 06-lab-complete/check_production_ready.py
# Result: 20/20 checks passed (100%).

docker compose up --build --scale agent=3 -d
# Result: 3 healthy agent replicas + healthy Redis + Nginx on localhost:8080.
```

### Remaining validation

Public cloud deployment still needs environment setup:

- Railway project connected to the GitHub repository.
- Railway Redis service added to the same project and `REDIS_URL` referenced by the web service.
- Public URL and screenshots for final submission.
