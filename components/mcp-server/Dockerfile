# python:3.12-slim — smaller than full Python, keeps C-extension wheels working
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py auth.py http_transport.py /app/
COPY tools/ /app/tools/

USER 65532:65532
ENV PYTHONUNBUFFERED=1

CMD ["python3", "/app/server.py"]
