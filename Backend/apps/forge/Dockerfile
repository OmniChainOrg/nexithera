FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Backend/app ./app
COPY Backend/apps/forge ./apps/forge

EXPOSE 8000

CMD ["uvicorn", "apps.forge.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
