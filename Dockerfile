FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TIME_CAPSULE_ENV=prod

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p logs cert data

# Copy application code
COPY app/ ./app/
COPY .env.production .env.production
COPY prod_start.sh prod_start.sh
COPY manage_secrets.py manage_secrets.py

# Create a non-root user
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app \
    && chmod +x prod_start.sh

# Set proper permissions
RUN mkdir -p app/data app/secrets \
    && chown -R appuser:appuser app/data app/secrets logs cert \
    && chmod -R 750 app/data app/secrets

# Ensure all scripts are executable
RUN chmod +x app/start.sh manage_secrets.py prod_start.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 443

# Set production healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f https://localhost:443/health || exit 1

# Start command
CMD ["./prod_start.sh"] 