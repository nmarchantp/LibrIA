# syntax=docker/dockerfile:1.7

# Etapa común: fija la versión de Node e instala exactamente package-lock.json.
FROM node:20.19-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
# La caché acelera reconstrucciones sin incorporarse a la imagen final.
RUN --mount=type=cache,target=/root/.npm npm ci

# Desarrollo: incluye el código y ejecuta Vite con recarga automática.
FROM dependencies AS development
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# Construcción: convierte React en HTML, CSS y JavaScript optimizados en /app/dist.
FROM dependencies AS build
COPY . .
RUN npm run build

# Producción: Nginx sirve solamente los archivos compilados; Node no queda incluido.
FROM nginx:1.29-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
# Docker marca el contenedor como no saludable si Nginx deja de responder.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
