# syntax=docker/dockerfile:1

FROM node:20-bullseye-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies only
RUN npm install --production

# Copy application code
COPY index.js ./

# Run the application
CMD ["node", "index.js"]
