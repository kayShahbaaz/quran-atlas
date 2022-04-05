FROM python:3.8-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project
COPY . .

# Create cache directory for sentence-transformers model
RUN mkdir -p /root/.cache/huggingface

# Expose port
EXPOSE 7860

# Set environment variables
ENV DASH_HOST=0.0.0.0
ENV DASH_PORT=7860
ENV DASH_DEBUG=False
ENV DB_PATH=./db/quran.db
ENV EMBEDDINGS_PATH=./embeddings/verse_embeddings.npy

# Run the app
CMD ["python", "app.py"]
