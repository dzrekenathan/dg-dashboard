FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifest
COPY pyproject.toml ./

# Install all dependencies into the system Python (no venv, no lock needed)
RUN uv pip install --system --no-cache \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "sqlalchemy[asyncio]>=2.0.36" \
    "asyncpg>=0.30.0" \
    "alembic>=1.14.0" \
    "python-jose[cryptography]>=3.3.0" \
    "bcrypt>=4.0.1,<5" \
    "python-multipart>=0.0.18" \
    "openpyxl>=3.1.5" \
    "pydantic-settings>=2.6.0" \
    "websockets>=13.0"

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

EXPOSE 8000

# Call uvicorn directly — no uv run needed, deps are in system Python
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
