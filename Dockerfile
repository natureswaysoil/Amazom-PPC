# syntax=docker/dockerfile:1

FROM node:20-bullseye-slim AS builder

WORKDIR /app

# Copy package definition files first for better caching
COPY package*.json ./

# Install dependencies including devDependencies for building TypeScript
RUN npm install

# Copy source files
COPY tsconfig.json ./
COPY src ./src
COPY index.js ./

# Build the TypeScript sources
RUN npm run build

FROM node:20-bullseye-slim

WORKDIR /app
ENV NODE_ENV=production

# Copy only the runtime artifacts
COPY --from=builder /app/dist ./dist
COPY index.js ./
COPY package.json ./

# Use the compiled server entrypoint by default
CMD ["node", "dist/server.js"]
