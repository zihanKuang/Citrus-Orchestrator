# python:3.12-slim — smaller than full Python, keeps C-extension wheels working
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server/ /app/mcp_server/

USER 65532:65532
ENV PYTHONUNBUFFERED=1

CMD ["python3", "-m", "mcp_server.server"]
