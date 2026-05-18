# Copilot Instructions

This project is a Kubernetes-native FastAPI backend.

## Stack

- Python 3.11
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Postgres
- Celery
- RabbitMQ
- Valkey/Redis
- Helm for Kubernetes deployments

## Coding style

- Prefer simple, explicit code.
- Use typed functions where practical.
- Use Pydantic v2 patterns.
- Do not introduce large framework changes without asking.
- Do not create new architectural layers unless necessary.
- Prefer boring, maintainable solutions.

## Testing

- For backend changes, suggest relevant pytest tests.
- For DB changes, consider Alembic migrations.
- Do not assume `Base.metadata.create_all()` is used in runtime code.

## Kubernetes / Helm

- Keep manifests environment-aware.
- Avoid committing real secrets.
- Prefer values files for environment-specific config.

## AI behavior

- Act as an assistant, not an autonomous agent.
- Prefer suggestions, explanations, and small focused edits.
- Do not rewrite large files unless explicitly asked.
