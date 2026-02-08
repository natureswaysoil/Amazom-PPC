# syntax=docker/dockerfile:1

FROM node:20-bullseye-slim

WORKDIR /app

# Install Python 3 and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python-is-python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install dependencies
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy Node.js package files
COPY package*.json ./

# Install Node.js production dependencies
RUN npm install --production

# Copy application code (both Node.js and Python)
COPY index.js ./
COPY server.js ./
COPY *.py ./
COPY config.json ./

# Set environment variable to use python3
ENV PYTHON_PATH=python3
ENV PYTHONUNBUFFERED=1

# Run the HTTP server
CMD ["node", "server.js"]
