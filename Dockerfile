FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVER_PORT=8001 \
    SERVER_HOST=0.0.0.0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app
COPY tests/ ./tests
COPY pytest.ini run.py .env.example ./

RUN mkdir -p /app/storage_data/facturas /app/storage_data/logos /app/storage_data/remisiones_firmadas /app/storage_data/uploads

EXPOSE 8001

CMD ["python", "run.py"]
