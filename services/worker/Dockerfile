FROM node:24-alpine
WORKDIR /app
COPY package.json tsconfig.json ./
RUN npm install
COPY src ./src
RUN npm run build && npm prune --omit=dev
EXPOSE 8081
CMD ["node", "dist/server.js"]
