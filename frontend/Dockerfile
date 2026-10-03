# Dev-mode image for docker-compose only. Render deploys this as a static
# site instead (npm ci && npm run build, publish dist/) - see render.yaml.
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
