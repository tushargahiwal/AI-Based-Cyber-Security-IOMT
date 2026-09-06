# --- build ---------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Lockfile first: npm ci is reproducible and this layer survives source edits.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- serve ---------------------------------------------------------------
FROM nginx:1.27-alpine

# The SPA needs two things nginx does not do by default: every unknown path must
# fall back to index.html (React Router owns the routes), and /api/v1 must reach
# the backend — including the WebSocket upgrade the live monitor depends on.
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null || exit 1
