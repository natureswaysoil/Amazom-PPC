# syntax=docker/dockerfile:1

FROM node:20-bullseye-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies only
RUN npm install --production

# Copy application code
COPY index.js ./
COPY server.js ./

# Run the HTTP server
CMD ["node", "server.js"]
