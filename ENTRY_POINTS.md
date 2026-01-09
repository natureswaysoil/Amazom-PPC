# Cloud Function Entry Points

This document describes the available entry points for deploying the Amazon PPC Optimizer as a Google Cloud Function.

## Available Entry Points

The `main.py` file provides three HTTP entry points that can be used when deploying to Google Cloud Functions:

### 1. `run_optimizer` (Recommended)

The primary entry point for the optimizer.

**Usage:**
```bash
gcloud functions deploy amazon-ppc-optimizer \
  --entry-point=run_optimizer \
  --runtime=python311 \
  --trigger-http \
  ...
```

**Description:** This is the main entry point that handles all optimizer functionality including:
- Health checks (`?health=true`)
- Profile listing (`?list_profiles=true`)
- Connection verification (`?verify_connection=true`)
- Permission health checks (`?permission_health=true`)
- Full optimization runs (default)

### 2. `optimizePPC` (Legacy)

Legacy entry point for backward compatibility.

**Usage:**
```bash
gcloud functions deploy amazon-ppc-optimizer \
  --entry-point=optimizePPC \
  --runtime=python311 \
  --trigger-http \
  ...
```

**Description:** An alias to `run_optimizer` maintained for backward compatibility with older deployments that used this naming convention.

### 3. `run_pipeline` (Cloud Run Job Compatible)

Entry point designed for Cloud Run Job compatibility.

**Usage:**
```bash
gcloud functions deploy amazon-ppc-optimizer \
  --entry-point=run_pipeline \
  --runtime=python311 \
  --trigger-http \
  ...
```

**Description:** Another alias to `run_optimizer` that uses naming conventions common in Cloud Run Jobs and data pipeline contexts.

## Verification

Before deploying, verify that all entry points are correctly defined:

```bash
python3 verify_entry_points.py
```

This script checks that:
- All required entry points exist in `main.py`
- Each entry point is properly decorated with `@functions_framework.http`
- The Python syntax is valid

## Entry Point Implementation

All three entry points are implemented as aliases in `main.py`:

```python
@functions_framework.http
def run_optimizer(request) -> Tuple[Dict[str, Any], int]:
    """Main Cloud Function entry point"""
    # Full implementation
    ...

@functions_framework.http
def optimizePPC(request) -> Tuple[Dict[str, Any], int]:
    """Alias for run_optimizer for backward compatibility"""
    return run_optimizer(request)

@functions_framework.http
def run_pipeline(request) -> Tuple[Dict[str, Any], int]:
    """Alias for run_optimizer to support Cloud Run Job compatibility"""
    return run_optimizer(request)
```

## Common Deployment Issues

### Issue: `MissingTargetException: File /app/main.py is expected to contain a function named 'X'`

**Cause:** The deployed code is outdated or the entry point name is misspelled.

**Solution:**
1. Verify the entry point name is one of: `run_optimizer`, `optimizePPC`, or `run_pipeline`
2. Redeploy with the latest code from the repository
3. Run `verify_entry_points.py` before deploying to catch issues early

### Issue: `gcloud run jobs update ... --update-args="--target=X"` fails

**Cause:** Incorrect command syntax. The `--target` flag is for `functions-framework`, not `gcloud` commands.

**Solution:** 
For Cloud Functions, use:
```bash
gcloud functions deploy FUNCTION_NAME \
  --entry-point=ENTRY_POINT_NAME \
  ...
```

For Cloud Run Jobs, use:
```bash
gcloud run jobs update JOB_NAME \
  --region=REGION \
  --args="--target=ENTRY_POINT_NAME"
```

## CI/CD Integration

All GitHub Actions workflows automatically verify entry points before deployment:

1. `deploy-gen2.yml` - Runs `verify_entry_points.py` before Gen2 deployment
2. `deploy-optimizer.yml` - Runs verification before standard deployment
3. `deploy-to-cloud.yml` - Runs verification before full cloud deployment

## Testing Locally

To test the entry points locally with functions-framework:

```bash
# Install functions-framework
pip install functions-framework

# Test with run_optimizer
functions-framework --target=run_optimizer --port=8080

# Test with optimizePPC
functions-framework --target=optimizePPC --port=8080

# Test with run_pipeline
functions-framework --target=run_pipeline --port=8080
```

Then test with:
```bash
# Health check
curl "http://localhost:8080?health=true"

# Dry run
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}' \
  "http://localhost:8080"
```

## References

- [Google Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [functions-framework-python](https://github.com/GoogleCloudPlatform/functions-framework-python)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
