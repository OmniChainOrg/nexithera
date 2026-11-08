# ChronoThera: Formulation Add-on
# $2k/mo - Requires Forge or Forge Plus parent

FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY Backend/app ./app
COPY Backend/apps/chronothera/app ./chronothera_app

# Copy manifests for validation
COPY app_manifests ./app_manifests

# Set environment
ENV PYTHONUNBUFFERED=1
ENV APP_TIER=chronothera
ENV APP_ADDON=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8030/health').raise_for_status()"

# Run ChronoThera app
CMD ["python", "-m", "uvicorn", "chronothera_app.main:app", "--host", "0.0.0.0", "--port", "8030"]
