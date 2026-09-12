# Dashboard + Integration (Person 5)

Investigator dashboard for SIH26152 — Next.js + TypeScript + Tailwind, reading
from the team's versioned JSON contracts via `backend/api/dashboard.py`
(Person 5's API composition layer). Never imports another person's internal
Python modules — only their published contracts.

## Run it

Backend (composition API only, no Postgres required):

```bash
python -m backend.dashboard_dev_server   # http://127.0.0.1:8000
```

Frontend:

```bash
npm install
npm run dev                              # http://localhost:3000
```

Once Person 1's full stack (Postgres + ingestion + graph) is up, point
`NEXT_PUBLIC_API_BASE` in `.env.local` at `main.py`'s server instead — same
routes, same contracts, no frontend changes needed.

## Views

Overview · Timeline · Narratives (topic drill-down) · Network · Audience ·
Investigation (cross-dimensional explanation + report + audit trail).

## Tests

```bash
npm run lint
npx tsc --noEmit
npm run test:e2e     # Playwright; spins up its own backend+frontend on 8011/3100
```

Backend contract tests (fixtures + composition API against the published
JSON contracts) live in `../tests/contract/`:

```bash
python -m pytest tests/contract/ -v
```
