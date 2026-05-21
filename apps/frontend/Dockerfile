FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
<<<<<<< HEAD
# Increase npm network timeout to survive slow connections
RUN npm ci --network-timeout=120000 --prefer-offline || npm ci --network-timeout=180000
=======
RUN npm ci
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
USER node
CMD ["node", "server.js"]
