# Web Visitor Counter Log

UTS Cloud Computing, case study 5. Group member names/NIMs must be supplied before submission.

## Architecture

Browser → Nginx on localhost:8090 → /api/ reverse proxy → backend:5000 on app-net → visitor-log-data:/var/lib/backend_data/visitor_logs.json.
Windows is the development environment. Jenkins/build/deployment will run on the private server; that stage is not executed.

## Local Windows checks

From this project directory in PowerShell:

```powershell
& '..\.venv-win\Scripts\python.exe' -m unittest discover -s tests -v
node --check frontend/app.js
```

Runtime backend is Python standard library only. Docker uses python:3.11-slim, not the Windows venv. Local interpreter observed Python 3.15.0; support/build suitability must be reviewed before final version pinning.

## Local Docker smoke check

`tests/docker_smoke.py` creates a new ignored .env only when none exists, provisions a random disposable login verifier, builds/starts the stack and checks Nginx/health/login/CRUD/logout. It never removes resources. It deliberately discards the generated password, so its test account is not an interactive user account. Do not overwrite an existing .env to rerun it. Current containers remain running on loopback port 8090.

```powershell
& '..\.venv-win\Scripts\python.exe' tests/docker_smoke.py
```

For interactive use, run `& '..\.venv-win\Scripts\python.exe' .\setup_account.py` locally in PowerShell. Password input is hidden and never sent to chat; an existing .env requires explicit replacement confirmation and a private recovery copy is retained. The tool writes a verifier only; it does not restart/recreate containers. That lifecycle step requires separate approval. This interactive path has been syntax-checked, not exercised with an owner password.

Alternatively provision your own AUTH_USERNAME, AUTH_SALT (at least 16 random bytes as hex), AUTH_PASSWORD_HASH (PBKDF2-HMAC-SHA256, 600000 iterations, UTF-8 password, hex digest) in private .env via an approved secure local workflow. Never commit, print or send a real password. Changes require deliberate backend restart/recreation; not performed automatically. Session TTL is 30 minutes, login limited to 10 attempts per minute globally. Static HTML is public, data/operations are authenticated. HTTPS is mandatory when credentials travel beyond loopback.

## API and counting

- POST /visit: public endpoint accepting only `{ "page": "/" }`; 30 writes/minute globally, no automatic retries. This is a demo limit, not complete bot protection.
- POST /login: username/password → bearer token.
- GET /logs: total_hits and indexed logs.
- POST /logs: page, optional user_agent → add one entry.
- DELETE /logs?index=X: delete current-list index; invalid input 400, nonexistent index 404.
- POST /logout: revoke token.
- GET /health: non-sensitive storage readiness.

Browser uses /api/ paths. Tokens live in sessionStorage, not URLs. Total count is the number of retained logs: deleting one reduces the count. Only opening/reloading the public landing page (`/` or `/index.html`) records a page view through POST /visit. Dashboard `/visitor-log.html` requires login and reads data every 30 seconds; table and chart show only page `/`, preserving original deletion indices. Chart periods use WIB and default to the HTTP server Date. Nginx overwrites X-Real-IP; backend trusts it only when the socket peer resolves to configured TRUSTED_PROXY=frontend. Docker Desktop may expose the gateway/NAT address rather than the device address. Historical IP values are unchanged.

Storage uses a process-local lock and atomic replace. One backend process only. Corruption fails closed. Index-based deletion follows the assignment; concurrent users should refresh before choosing a record because indices can shift.

## Private-server Jenkins setup — pending

Use a dedicated trusted Linux agent with Python3, Docker/Compose, Git, curl and the needed Jenkins Pipeline/GitHub plugins. Docker access grants host administrative capability; never run untrusted PR builds. No server setup/install performed yet.

Create SCM job using root Jenkinsfile/main and repository checkout PAT through Jenkins Credentials. Exam requests a classic PAT with repo/admin:repo_hook and 30/90-day expiration; never put values in source. Configure separate signed GitHub webhook and HTTPS reachability. Configure Jenkins secret-file credential ID visitor-log-env containing application verifier environment configuration, not a hardcoded source secret. Configure DEPLOY_DIR as a dedicated absolute Docker-host path and FRONTEND_URL reachable from the agent. Ensure the agent and host share that bind path if Jenkins is containerized. Check exact app-net/visitor-log-data ownership before the first deployment. The provided pipeline is UNVERIFIED against Jenkins and must be reviewed against the server before enabling it.

Five stages: Checkout → Syntax Check (including tests) → Build Image (commit tag) → Automated Deployment (same image, stable frontend host path) → Health Check. Serialize builds. Backend port is not published. Keep secrets out of complete console output and screenshots.

## Verification status and remaining deliverables

Latest verification: nine unittest tests pass, including trusted proxy, spoofed/invalid/duplicate forwarding headers, DNS refresh/failure, CRUD, auth, rate limits, and storage preservation. Three Node check scripts pass (WIB aggregation, dashboard structure, shared table/chart refresh with original deletion indices). Real Edge root landing records exactly one page view; unauthenticated dashboard redirects to login.

Earlier checks: three unittest groups passed (CRUD/validation, sessions, storage/concurrency/reopened-server persistence). Compose config/build/start, nginx -t, proxied health, login, GET/POST/DELETE count decrement and logout passed. JavaScript syntax previously checked with Windows Node.

Additional executed checks: five stdlib regression tests pass, including login limits and malformed storage preservation. Windows Edge headless rendered the actual login page; desktop screenshot reviewed without clipping/overlap. A temporary host-file update was served through the Bind Mount while frontend image/start time stayed unchanged. Compose force-recreate replaced the backend container and preserved exact existing JSON bytes containing two records; same volume visitor-log-data and proxied health passed. Evidence: evidence/local-checks.json, login-desktop.png, persistence.json. Persistence hash checks do not prove the authenticated UI flow; no explicit docker rm -f video demonstration has been recorded.

Not verified: authenticated browser interactions/mobile dashboard, private-server Jenkins validation/deploy, real push/webhook, negative deployment failure, full security review and coverage target. The earlier browser tool blocked localhost; Windows Edge was the successful render alternative. Do not equate a screenshot render with interactive end-to-end acceptance.

Complete README member metadata/diagram as required by instructor and produce a 5–8 minute video: UI/API, approved backend container removal/recreation preserving exact records, real push through all stages to deployed change. Rubric: backend20/frontend15/Docker25/Jenkins25/docs15 percent. Nothing submitted to LMS.

## Preservation and shutdown

Do not delete named volumes or run global prune. Earlier coursework resources were not modified. Container removal and service shutdown require approval; no shutdown performed. Preserve known image plus corresponding frontend/config before server changes. No automatic rollback/zero downtime promised. On health failure inspect scoped logs/config/storage first, never reset corrupt data.
