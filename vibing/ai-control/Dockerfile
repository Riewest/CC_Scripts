FROM node:22-alpine AS web-build
WORKDIR /build/web
COPY web/package*.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/pyproject.toml ./server/pyproject.toml
COPY server/src ./server/src
RUN pip install --no-cache-dir ./server
COPY --from=web-build /build/web/dist ./server/src/aicontrol/static
ENV AIC_WEB_DIST_DIR=/app/server/src/aicontrol/static
EXPOSE 8000
CMD ["python", "-m", "aicontrol.main"]
