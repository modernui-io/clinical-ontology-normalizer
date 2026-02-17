# Deployment Plan — sulci.ai

**Created**: 2026-02-15
**Status**: Planned (target: week of 2026-02-16)
**Domain**: sulci.ai (purchased on Cloudflare)
**Stack**: Vercel (frontend) + Railway (backend + Postgres + Redis)

---

## Task Order & Dependencies

```
[1] Deploy frontend to Vercel
 └──▶ [2] Connect sulci.ai domain (Cloudflare → Vercel)

[3] Deploy backend to Railway
 └──▶ [6] Choose & configure LLM API provider (HIPAA-eligible)

[1] + [3] ──▶ [4] Connect frontend to backend (CORS + env vars)

[5] HIPAA compliance setup (parallel)

[2] + [4] + [5] + [6] ──▶ [7] Smoke test full stack with demo data
```

---

## Task 1: Deploy Frontend to Vercel

- [ ] Create Vercel project, connect GitHub repo
- [ ] Set root directory to `frontend/`
- [ ] Add env vars: `BACKEND_URL`, `NEXT_PUBLIC_API_URL` (Railway backend URL)
- [ ] Deploy and verify investor page loads at Vercel preview URL
- [ ] Enable Vercel Pro plan ($20/mo)

## Task 2: Connect sulci.ai Domain (Cloudflare → Vercel)

**Blocked by**: Task 1

- [ ] In Cloudflare DNS, add CNAME: `sulci.ai` → `cname.vercel-dns.com`
- [ ] Add CNAME: `www.sulci.ai` → `cname.vercel-dns.com`
- [ ] In Vercel, add sulci.ai as custom domain
- [ ] Set Cloudflare SSL to "Full (Strict)"
- [ ] Verify DNS propagation and HTTPS working

## Task 3: Deploy Backend to Railway

- [ ] Create Railway project
- [ ] Deploy FastAPI app from `backend/`
- [ ] Add PostgreSQL service
- [ ] Add Redis service
- [ ] Set all env vars from `backend/app/core/config.py` (DATABASE_URL, REDIS_URL, SECRET_KEY, etc.)
- [ ] Railway Teams plan for BAA eligibility ($20/user/mo)
- [ ] Verify `/api/v1/health` endpoint responds

## Task 4: Connect Frontend to Backend (CORS + env vars)

**Blocked by**: Tasks 1, 3

- [ ] Update Vercel env vars with Railway backend URL
- [ ] Configure CORS in FastAPI to allow `sulci.ai` origin
- [ ] Test API proxy: `sulci.ai/api/*` → Railway backend `/api/v1/*`
- [ ] Verify end-to-end: frontend loads, API calls succeed, dashboard functional

## Task 5: HIPAA Compliance Setup

- [ ] Sign BAA with Railway (available on Teams plan)
- [ ] Verify Postgres encryption at rest (Railway default)
- [ ] Verify TLS everywhere (Vercel + Railway both enforce HTTPS)
- [ ] Confirm tenant isolation in backend auth middleware
- [ ] De-identify data before Anthropic API calls (strip names, MRNs, dates)
- [ ] Document HIPAA controls for pilot customer security questionnaire

> **Note**: Vercel does NOT need BAA — frontend never handles PHI
> **Note**: SOC 2 is in process separately — not required for initial pilot

## Task 6: Choose & Configure LLM API Provider (HIPAA-eligible)

**Blocked by**: Task 3
**Status**: Decision pending — do not need to pick until backend is deployed

Options researched (all offer BAAs):
- **GCP Vertex AI** — leading option, customers are GCP-native, Claude available on Vertex
- **AWS Bedrock** — instant self-service BAA, Claude + other models, strong data isolation
- **Azure OpenAI** — automatic BAA, GPT-4o, best if Azure ecosystem
- **Anthropic Direct** — Claude for Healthcare (Jan 2026), sales-negotiated BAA
- **OpenAI Direct** — email baa@openai.com, zero-data-retention endpoints

Only 4 files touch the LLM API (swap is small):
1. `backend/app/services/llm_service.py` (core abstraction layer)
2. `backend/app/services/nlp_claude_api.py` (hybrid reasoner)
3. `backend/app/services/agent_chat_service.py` (Q&A agent)
4. `backend/app/services/narrative_extractor.py` (clinical narratives)

- [ ] Decide on provider based on customer infra + pricing
- [ ] Sign BAA with chosen provider
- [ ] Swap API client in llm_service.py (+ 3 other files if needed)
- [ ] Set API keys as env vars on Railway
- [ ] Set usage limits/alerts to control costs
- [ ] Test clinical NLP pipeline end-to-end

## Task 7: Smoke Test Full Stack

**Blocked by**: Tasks 2, 4, 5, 6

- [ ] Load demo clinical documents through the app
- [ ] Verify NLP extraction pipeline works
- [ ] Verify knowledge graph builds correctly
- [ ] Test Q&A agent with sample queries
- [ ] Confirm investor page at `sulci.ai/investors` renders correctly
- [ ] Confirm dashboard at `sulci.ai/dashboard` is functional
- [ ] Test on mobile for responsive layout

---

## Cost Estimate (Monthly)

| Service | Plan | Cost |
|---------|------|------|
| Vercel | Pro | $20/mo |
| Railway | Teams + usage | $30-80/mo |
| Neo4j AuraDB | Free tier | $0 |
| LLM API (TBD) | Usage-based | $50-500/mo |
| Cloudflare | Free (DNS only) | $0 |
| **Total** | | **$100-600/mo** |

---

## Resume Instructions

If this session breaks, start a new session and say:
```
Read tasks/25_deployment_plan_sulci_ai.md and continue the deployment plan from where we left off.
```
