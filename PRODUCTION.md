# Time Capsule Production Setup Guide

This guide explains how to set up Time Capsule for production deployment with TLS/SSL security.

## Prerequisites

- Docker and Docker Compose
- SSL/TLS certificate and private key
- Domain name pointing to your server (recommended)

## Setting up TLS Certificates

Place your SSL/TLS certificate and private key in the `cert` directory:

```
cert/
  fullchain.pem    # Your SSL certificate including intermediate certs
  privkey.pem      # Your SSL private key
```

### Using Let's Encrypt

If you don't have SSL certificates, you can obtain free ones from Let's Encrypt:

```bash
apt-get update
apt-get install certbot
certbot certonly --standalone -d yourdomain.com

# Copy the certificates to the cert directory
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./cert/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./cert/
chmod 600 ./cert/privkey.pem
```

### Using Self-Signed Certificates (Not Recommended for Production)

If you just want to test your setup, you can generate self-signed certificates:

```bash
./scripts/generate_test_certs.sh
```

## Environment Configuration

1. Set up the admin password (required for production):

   ```bash
   ./scripts/set_admin_password.sh
   ```
   
   This script will:
   - Create a `.env.production` file if it doesn't exist
   - Prompt you for an admin password
   - Save the password in the configuration file

2. Edit `.env.production` to customize other settings:

   ```
   # Required settings
   TIME_CAPSULE_ENV=prod
   PORT=443
   
   # Database settings (if using PostgreSQL)
   DB_PASSWORD=your_secure_password
   
   # Security settings
   ADMIN_PASSWORD=already_set_by_script
   ENCRYPTION_KEY=your_secure_encryption_key
   
   # API keys (if using LLM features)
   DEEPSEEK_API_KEY=your_api_key
   ```

## Running in Production

### Quick Start

The easiest way to start in production mode:

```bash
./scripts/run_production.sh
```

This script will:
1. Check for the necessary configuration and certificates
2. Load settings from `.env.production`
3. Start the application with TLS enabled

### Manual Start

If you need more control, use:

```bash
./scripts/start.sh -e prod -h 0.0.0.0 -p 443
```

## Deployment with Docker Compose

1. Create a `.env` file for Docker Compose:

   ```bash
   # Required for Docker Compose
   DB_PASSWORD=your_secure_password
   ADMIN_PASSWORD=your_admin_password
   ENCRYPTION_KEY=your_secure_encryption_key
   DEEPSEEK_API_KEY=your_api_key
   ```

2. Build and start the services:

   ```bash
   docker-compose up -d
   ```

3. Check the application logs:

   ```bash
   docker-compose logs -f app
   ```

## Manual Deployment (without Docker)

If you prefer to deploy without Docker:

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Make sure your PostgreSQL database is running and configured in `.env.production`

3. Start the application:

   ```bash
   ./scripts/run_production.sh
   ```

## Securing Your Deployment

For enhanced security:

1. Use a firewall to restrict access to necessary ports only (443 for HTTPS)

2. Consider using Nginx as a reverse proxy for additional security features:
   - Uncomment the nginx service in docker-compose.yml
   - Add proper Nginx configuration in ./nginx/conf/

3. Regularly update your SSL certificates

4. Back up your database regularly:

   ```bash
   # With Docker
   docker-compose exec db pg_dump -U timecapsule > backup_$(date +%Y%m%d).sql
   
   # Without Docker
   pg_dump -U timecapsule -h localhost timecapsule > backup_$(date +%Y%m%d).sql
   ```

## Monitoring and Maintenance

- Access the application's health endpoint: https://yourdomain.com/health
- Check application logs in the `logs` directory
- Monitor the database for performance issues

## Troubleshooting

If the application fails to start:

1. Check the logs: `docker-compose logs app` or `cat logs/timecapsule_*.log`
2. Verify TLS certificate paths and permissions
3. Ensure database connection settings are correct
4. Check if required environment variables are set

### Common Errors

#### Admin Password Not Set

If you see:
```
ERROR: Admin password is not set for production environment.
```

Run:
```bash
./scripts/set_admin_password.sh
```

#### Missing TLS Certificates

If you see certificate path errors:
```
ERROR: SSL certificates not found at cert/fullchain.pem and cert/privkey.pem
```

Either generate test certificates:
```bash
./scripts/generate_test_certs.sh
```

Or obtain proper certificates as described in the "Setting up TLS Certificates" section. 