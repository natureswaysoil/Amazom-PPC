# Dashboard Integration Guide

This document explains the comprehensive dashboard integration features added to the Amazon PPC Optimizer.

## Overview

The optimizer now includes a robust `DashboardClient` module that provides:

- **Enhanced Results Reporting**: Detailed metrics and structured payload
- **Real-time Progress Updates**: Live status updates during optimization
- **Error Reporting**: Automatic error notification with full context
- **Retry Logic**: Exponential backoff for reliable communication
- **API Key Authentication**: Secure authentication with dashboard
- **Health Checks**: Verify connectivity and system status
- **Dashboard Triggers**: Allow dashboard to initiate optimization runs

## Architecture

### Components

1. **dashboard_client.py**: Core module handling all dashboard communication
2. **main.py**: Integrates DashboardClient into the Cloud Function
3. **config.json**: Dashboard configuration settings

### Flow

```
Optimization Run
├── Start Run (generate unique run_id)
├── Progress Update: "Initializing optimizer..." (10%)
├── Progress Update: "Starting optimization..." (20%)
├── Run Optimization Features
├── Progress Update: "Processing results..." (90%)
├── Send Enhanced Results Payload
└── Progress Update: "Completed successfully" (100%)
```

## Configuration

### Basic Configuration

```json
{
  "dashboard": {
    "url": "https://ppc-dashboard.abacusai.app",
    "api_key": "",
    "enabled": true,
    "send_real_time_updates": true,
    "timeout": 30
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `url` | string | Required | Dashboard base URL |
| `api_key` | string | "" | API key for authentication (optional but recommended) |
| `enabled` | boolean | true | Enable/disable dashboard communication |
| `send_real_time_updates` | boolean | true | Enable real-time progress updates |
| `timeout` | integer | 30 | Request timeout in seconds |

### Environment Variables

For production, set dashboard configuration via environment variables:

```bash
# In Google Cloud Functions deployment
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

# If this prints "(unset)", set your active project first:
# gcloud config set project YOUR_PROJECT_ID

gcloud functions deploy amazon-ppc-optimizer \
  --project="$PROJECT_ID" \
  --set-env-vars \
    DASHBOARD_URL="https://ppc-dashboard.abacusai.app",\
    DASHBOARD_API_KEY="your_api_key_here"
```

Or include in the `PPC_CONFIG` JSON environment variable.

## API Endpoints

### 1. Optimization Results

**Endpoint**: `POST /api/optimization-results`

**Purpose**: Send completed optimization results with enhanced metrics

**Payload Structure**:
```json
{
  "timestamp": "2025-10-14T05:54:00.000Z",
  "run_id": "uuid-string",
  "status": "success",
  "profile_id": "1780498399290938",
  "dry_run": false,
  "duration_seconds": 125.5,
  
  "summary": {
    "campaigns_analyzed": 10,
    "keywords_optimized": 150,
    "bids_increased": 75,
    "bids_decreased": 60,
    "negative_keywords_added": 25,
    "budget_changes": 3,
    "total_spend": 1234.56,
    "total_sales": 2345.67,
    "average_acos": 0.45
  },
  
  "features": {
    "bid_optimization": { ... },
    "dayparting": { ... },
    "keyword_discovery": { ... },
    "campaign_management": { ... },
    "negative_keywords": { ... }
  },
  
  "campaigns": [
    {
      "campaign_id": "123456",
      "campaign_name": "Product Campaign",
      "spend": 123.45,
      "sales": 234.56,
      "acos": 0.52,
      "keywords_count": 50,
      "changes_made": 12
    }
  ],
  
  "top_performers": [
    {
      "keyword_text": "organic soil",
      "clicks": 120,
      "sales": 345.67,
      "acos": 0.35,
      "bid_change": 0.15
    }
  ],
  
  "errors": [],
  "warnings": [],
  
  "config_snapshot": {
    "target_acos": 0.45,
    "lookback_days": 14,
    "enabled_features": ["bid_optimization", "dayparting"]
  }
}
```

### 2. Progress Updates

**Endpoint**: `POST /api/optimization-status`

**Purpose**: Send real-time progress updates during optimization

**Payload Structure**:
```json
{
  "timestamp": "2025-10-14T05:54:00.000Z",
  "run_id": "uuid-string",
  "status": "running",
  "profile_id": "1780498399290938",
  "message": "Analyzing keywords...",
  "percent_complete": 50.0
}
```

**Progress Messages**:
- "Initializing optimizer..." (10%)
- "Starting optimization..." (20%)
- "Processing optimization results..." (90%)
- "Optimization completed successfully" (100%)

### 3. Error Reporting

**Endpoint**: `POST /api/optimization-error`

**Purpose**: Report errors that occur during optimization

**Payload Structure**:
```json
{
  "timestamp": "2025-10-14T05:54:00.000Z",
  "run_id": "uuid-string",
  "status": "failed",
  "profile_id": "1780498399290938",
  "error": {
    "type": "ValueError",
    "message": "Invalid configuration parameter",
    "traceback": "Full Python traceback...",
    "context": {
      "function": "run_optimizer",
      "timestamp": "2025-10-14T05:54:00.000Z",
      "dry_run": false
    }
  }
}
```

### 4. Health Check

**Endpoint**: `GET /api/health`

**Purpose**: Verify optimizer is alive and reachable

**Response**:
```json
{
  "status": "healthy",
  "service": "amazon-ppc-optimizer",
  "timestamp": "2025-10-14T05:54:00.000Z",
  "version": "2.0.0"
}
```

## Authentication

### API Key Authentication

The dashboard client supports API key authentication via Bearer token:

**Headers**:
```
Authorization: Bearer YOUR_API_KEY_HERE
Content-Type: application/json
X-Profile-ID: 1780498399290938
```

**Configuration**:
```json
{
  "dashboard": {
    "api_key": "your_dashboard_api_key"
  }
}
```

### Dashboard Trigger Authentication

When the dashboard triggers an optimization run, it must provide a valid API key:

```bash
curl -X POST "https://YOUR-FUNCTION-URL?trigger=dashboard" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

The optimizer validates the API key matches the configured dashboard API key.

## Retry Logic

### Exponential Backoff

The dashboard client includes automatic retry logic with exponential backoff:

```python
@retry_with_backoff(max_attempts=3, initial_delay=2, max_delay=10)
def send_results(...):
    # Send request with automatic retries
```

**Retry Parameters**:
- **max_attempts**: 3 attempts before giving up
- **initial_delay**: 2 seconds before first retry
- **max_delay**: 10 seconds maximum delay between retries

**Retry Behavior**:
1. First attempt fails → Wait 2 seconds
2. Second attempt fails → Wait 4 seconds
3. Third attempt fails → Give up and log error

### Error Handling

Dashboard communication errors **do not stop optimization**:

```python
try:
    dashboard_client.send_results(...)
except Exception as e:
    logger.error(f"Dashboard update failed: {e}")
    # Optimization continues regardless
```

## Usage Examples

### Basic Usage

```python
from dashboard_client import DashboardClient

# Initialize client
client = DashboardClient(config)

# Start optimization run
run_id = client.start_run(dry_run=False)

# Send progress updates
client.send_progress("Analyzing keywords...", 25.0)
client.send_progress("Applying bid changes...", 50.0)

# Send final results
client.send_results(
    results=optimization_results,
    config=config,
    duration_seconds=125.5,
    dry_run=False
)
```

### Error Reporting

```python
try:
    # Run optimization
    results = optimizer.run()
except Exception as e:
    # Report error to dashboard
    context = {
        'function': 'run_optimizer',
        'timestamp': datetime.now().isoformat()
    }
    client.send_error(e, context)
    raise
```

### Health Check

```python
# Check dashboard connectivity
is_healthy = client.health_check()
if is_healthy:
    print("Dashboard is reachable")
else:
    print("Dashboard is not reachable")
```

## Testing

### Local Testing

Test the dashboard client locally:

```python
import json
from dashboard_client import DashboardClient

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

# Create client
client = DashboardClient(config)

# Test features
run_id = client.start_run(dry_run=True)
client.send_progress("Testing...", 50.0)
```

### Production Testing

Test dashboard integration in Cloud Functions:

```bash
# Test with dry run
curl "https://YOUR-FUNCTION-URL?dry_run=true"

# Test dashboard trigger
curl -X POST "https://YOUR-FUNCTION-URL?trigger=dashboard" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Test health check
curl "https://YOUR-FUNCTION-URL?health=true"
```

## Monitoring

### Logs to Monitor

The dashboard client logs all interactions:

```
INFO: Dashboard POST /api/optimization-results: HTTP 200
INFO: Dashboard updated successfully with optimization results
WARNING: Dashboard rate limit exceeded
ERROR: Dashboard connection error: Connection timeout
```

### Key Metrics

Monitor these metrics in Cloud Logging:

- Dashboard request success rate
- Dashboard request latency
- Dashboard error rate
- Retry frequency

### Troubleshooting

**Dashboard requests failing**:
1. Check dashboard URL is correct
2. Verify API key is configured
3. Check network connectivity
4. Review dashboard logs for errors

**Rate limiting**:
1. Dashboard returns HTTP 429
2. Check `Retry-After` header
3. Reduce optimization frequency
4. Contact dashboard administrator

**Timeouts**:
1. Increase timeout in config
2. Check dashboard performance
3. Verify network connectivity

## Best Practices

1. **Always configure API key** for production environments
2. **Enable real-time updates** for better visibility
3. **Monitor logs** for dashboard communication errors
4. **Test in dry-run mode** before production deployment
5. **Use retry logic** to handle transient failures
6. **Don't block optimization** on dashboard failures
7. **Log all interactions** for debugging

## Security Considerations

1. **Protect API keys**: Never commit to Git, use environment variables
2. **Use HTTPS**: Dashboard URL must use HTTPS
3. **Validate responses**: Check response status and content
4. **Rate limiting**: Respect dashboard rate limits
5. **Timeout configuration**: Set reasonable timeouts
6. **Error handling**: Don't expose sensitive data in errors

## Future Enhancements

Potential future improvements:

- WebSocket support for real-time bidirectional communication
- Batch updates to reduce API calls
- Caching to reduce redundant requests
- Compression for large payloads
- Dashboard response commands (pause, adjust settings)
- Historical data synchronization

## Support

For issues with dashboard integration:

1. Check Cloud Function logs
2. Verify dashboard configuration
3. Test with curl/postman
4. Review this documentation
5. Contact: james@natureswaysoil.com

---

**Version**: 1.0.0  
**Last Updated**: October 14, 2025  
**Author**: Nature's Way Soil
