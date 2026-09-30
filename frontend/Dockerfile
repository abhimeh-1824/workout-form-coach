# ==============================================================================
# Workout Form Coach - Frontend Production Dockerfile
# Multi-stage build: Node.js (Vite Build) -> NGINX Alpine (Static Serving)
# ==============================================================================

# Stage 1: Build React 19 SPA
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

COPY . .
RUN npm run build

# Stage 2: Serve with NGINX
FROM nginx:alpine

# Remove default nginx configs
RUN rm -rf /etc/nginx/conf.d/*

# Copy custom NGINX configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
