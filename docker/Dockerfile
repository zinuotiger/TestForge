# 后端 Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY backend/ ./backend/
COPY cli/ ./cli/
COPY pyproject.toml .

# 安全: 非 root 用户
RUN useradd -m testforge && chown -R testforge:testforge /app
USER testforge

EXPOSE 9876

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9876/api/health')" || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9876"]
