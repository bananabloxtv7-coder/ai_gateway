FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Install dependencies first
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt

# Copy backend python files explicitly
COPY backend/main.py ./main.py
COPY backend/auth.py ./auth.py
COPY backend/config.py ./config.py
COPY backend/routes.py ./routes.py
COPY backend/forwarder.py ./forwarder.py
COPY backend/no_limit.py ./no_limit.py

# Copy example/template configs (optional reference)
COPY backend/keys.example.json ./keys.example.json

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
