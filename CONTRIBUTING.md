# Contributing Guide

Thanks for your interest in contributing.

## Development Setup

1. Fork the repository.
2. Create a feature branch:
   - `git checkout -b feat/short-name`
3. Copy env file:
   - Linux/Mac: `cp .env.example .env`
   - Windows PowerShell: `Copy-Item .env.example .env`
4. Run the project:
   - Docker: `docker compose up --build`
   - or local Python setup + `python manage.py migrate`

## Code Standards

- Keep changes focused and small.
- Use clear commit messages.
- Add tests for behavioral changes when possible.
- Avoid breaking public routes and JSON response contracts.

## Pull Request Checklist

- [ ] Code builds and runs locally.
- [ ] `python manage.py check` passes.
- [ ] Tests are updated or added where needed.
- [ ] README/docs are updated for user-facing changes.
- [ ] PR description explains what changed and why.

## Branch and Commit Naming

- Branch examples:
  - `feat/lightbox-accessibility`
  - `fix/infinite-scroll-loop`
  - `chore/docs-update`
- Commit style (recommended):
  - `feat: ...`
  - `fix: ...`
  - `refactor: ...`
  - `chore: ...`
