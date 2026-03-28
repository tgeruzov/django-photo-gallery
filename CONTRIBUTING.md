# Contributing Guide

Thanks for taking the time to improve the project.

This repository is small on purpose, so the best contributions are usually focused, well-tested, and easy to review.

## Good Contribution Fits

These are especially welcome:

- bug fixes
- performance improvements
- gallery UX polish
- accessibility improvements
- image pipeline reliability work
- test coverage improvements
- documentation cleanup

## Local Workflow

### 1. Start from `main`

Create a focused branch from the latest `main`.

Recommended branch prefixes:

- `feat/...`
- `fix/...`
- `refactor/...`
- `docs/...`
- `chore/...`

Examples:

- `feat/lightbox-zoom`
- `fix/upload-validation`
- `refactor/image-pipeline`

### 2. Create your local environment

```bash
# Linux / macOS
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

### 3. Run the project

Docker:

```bash
docker compose up --build
```

Local Python:

```bash
python -m venv .venv
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 4. Install dev tooling

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## Daily Checks

Before opening a PR, run:

```bash
pre-commit run --all-files
python manage.py check
python manage.py test
```

If you work through Docker, run the Django commands inside the web container.

## What Makes a Change Easier to Merge

- Keep the diff scoped to one idea.
- Avoid unrelated reformatting.
- Preserve public routes and JSON response contracts unless the change explicitly updates them.
- Add or update tests when behavior changes.
- Update docs when setup, API behavior, or deployment behavior changes.
- Call out tradeoffs clearly in the PR description.

## Pull Request Checklist

- [ ] The change solves one clearly defined problem.
- [ ] The branch is based on current `main`.
- [ ] `pre-commit run --all-files` passes.
- [ ] `python manage.py check` passes.
- [ ] Tests were added or updated where appropriate.
- [ ] Docs were updated if users or contributors will notice the change.
- [ ] The PR description explains what changed, why it changed, and how it was verified.

## Commit Style

Simple conventional-style commits work well here:

- `feat: add lightbox zoom support`
- `fix: prevent duplicate infinite-scroll requests`
- `refactor: move image processing into service layer`
- `docs: clarify production setup`
- `chore: add pre-commit hooks`

## A Note on Scope

Small, thoughtful PRs almost always move faster than giant rewrites.

If a change touches setup, deployment, image processing, and frontend behavior all at once, it is usually better to split it into separate reviewable pieces.
