
FROM python:3.12-slim AS base

FROM base AS builder
RUN apt-get -qq update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt && pip install --prefix=/install aiohttp

FROM base
ENV PYTHONUNBUFFERED=1
WORKDIR /shoppingassistantservice

COPY --from=builder /install /usr/local

COPY . .

ENV PORT "8080"
EXPOSE 8080

ENTRYPOINT ["python", "shoppingassistantservice.py"]