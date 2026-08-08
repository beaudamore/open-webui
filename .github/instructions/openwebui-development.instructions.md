---
description: "Use when modifying Open WebUI code, tests, Docker/build config, frontend SvelteKit files, backend Python/FastAPI files, or development workflow. Summarizes verified Open WebUI development requirements."
name: "Open WebUI Development Requirements"
applyTo:
  - "backend/**"
  - "src/**"
  - "test/**"
  - "static/**"
  - "Dockerfile"
  - "docker*.sh"
  - "docker-compose*.yaml"
  - "package.json"
  - "package-lock.json"
  - "pyproject.toml"
  - "vite.config.ts"
  - "svelte.config.js"
  - "tailwind.config.js"
  - "postcss.config.js"
---
# Open WebUI Development Requirements

Source: Open WebUI docs, "Developing Open WebUI": https://docs.openwebui.com/getting-started/advanced-topics/development/  
Verified: 2026-07-18.

- Use Python 3.11 or 3.12 for development. Python 3.13 is not supported by the documented requirements.
- Use Node.js 22.10+ and a recent Git version.
- Keep development data separate from production data; do not share a database or data directory between dev and production.
- Frontend development runs from the repository root: copy `.env.example` to `.env`, run `npm install`, run `npm run build`, then `npm run dev`.
- If `npm install` reports compatibility warnings, the docs say to use `npm install --force`.
- Backend development runs from `backend/`: create a Python 3.11 or 3.12 environment, install with `pip install -r requirements.txt -U`, then start with `sh dev.sh`.
- The documented dev URLs are frontend `http://localhost:5173`, backend `http://localhost:8080`, and backend API docs `http://localhost:8080/docs`.
- For frontend heap-limit build failures, set `NODE_OPTIONS="--max-old-space-size=4096"` before frontend commands.
- Backend changes may require manually restarting `sh dev.sh`; frontend hot reload may require a hard browser refresh.
- For upstream contribution workflow, the docs say to open a GitHub Discussion before writing code, branch from `dev`, keep the branch synced with `dev`, and submit pull requests to `dev`.
- Before stating or changing development requirements, re-check the source doc above because these requirements can change.