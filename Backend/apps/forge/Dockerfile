# Forge: EpistemicOS Standard Tier
# $500/mo - Single-zone reasoning, no swarms

FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY Backend/app ./app
COPY Backend/apps/forge/app ./forge_app

# Copy manifests for validation
COPY app_manifests ./app_manifests

# Set environment
ENV PYTHONUNBUFFERED=1
ENV APP_TIER=forge
ENV KERNEL_BACKEND=epistemicos

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8010/health').raise_for_status()"

# Run Forge app
CMD ["python", "-m", "uvicorn", "forge_app.main:app", "--host", "0.0.0.0", "--port", "8010"]
