# App image (PLAN.md §16.2): build the React dashboard, then the Python app. Build from the repo root.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/ ./
# Until spec 004 adds web/package.json, ship a one-line placeholder so the image still builds.
RUN if [ -f package.json ]; then npm ci && npm run build; \
    else mkdir -p dist && printf '<!doctype html><title>Call Me Back</title><p>Dashboard not built yet (spec 004).</p>' > dist/index.html; fi

FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY core ./core
COPY app ./app
COPY samples ./samples
COPY --from=web /web/dist ./web/dist
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
