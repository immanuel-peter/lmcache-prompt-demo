FROM node:22-slim

WORKDIR /app

COPY server.mjs ./

ENV NODE_ENV=production
EXPOSE 8787

CMD ["node", "server.mjs"]