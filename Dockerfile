FROM node:20-alpine

WORKDIR /app

# ⬇️ FORCE correct paths, no globbing
COPY tenderBackend/package.json tenderBackend/package-lock.json ./
RUN npm ci --omit-dev

COPY tenderBackend/ ./

ENV NODE_ENV=production
CMD ["node", "src/index.js"]
