# Container for any host that runs a Docker image (Render, Koyeb, Hugging Face Spaces, Fly, …).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY prompt.txt ./

# Hosts inject $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# exec form via sh so ${PORT} expands
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
