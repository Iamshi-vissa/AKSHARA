# syntax=docker/dockerfile:1.7
# AKSHARA web UI: static build served by nginx, which also proxies /api to the API.
FROM node:22-alpine AS build
WORKDIR /web
COPY infra/docker/with-ca.sh /usr/local/bin/with-ca
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=extra_ca,required=false with-ca npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
