#!/bin/bash
# Setup BigQuery Dataset and Tables for Amazon PPC Optimizer
# This script creates the necessary BigQuery infrastructure

set -e

# Configuration
PROJECT_ID="${1:-amazon-ppc-474902}"
DATASET_ID="${2:-amazon_ppc}"
LOCATION="${3:-us-east4}"

# Create temporary file for schema
SCHEMA_FILE=$(mktemp)

# Ensure cleanup on exit
trap 'rm -f "$SCHEMA_FILE"' EXIT

echo "========================================="
echo "BigQuery Setup for Amazon PPC Optimizer"
echo "========================================="
echo "Project ID: $PROJECT_ID"
echo "Dataset ID: $DATASET_ID"
echo "Location: $LOCATION"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud command not found. Please install Google Cloud SDK."
    exit 1
fi

# Check if bq is installed
if ! command -v bq &> /dev/null; then
    echo "Error: bq command not found. Please install Google Cloud SDK with BigQuery tools."
    exit 1
fi

# Helper function for creating tables with better error handling
create_table_with_error_handling() {
    local output
    output=$(bq mk "$@" 2>&1)
    local status=$?
    
    if [ $status -eq 0 ]; then
        echo "Table created successfully"
        return 0
    elif echo "$output" | grep -q "Already Exists"; then
        echo "Table already exists"
        return 0
    else
        echo "Warning: Table creation failed"
        echo "$output"
        return 1
    fi
}

# Set the project
echo "Setting project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Create dataset if it doesn't exist
echo ""
echo "Creating dataset $DATASET_ID..."
bq mk --location="$LOCATION" \
    --description="Amazon PPC Optimization data" \
    --dataset \
    "$PROJECT_ID:$DATASET_ID" 2>/dev/null || echo "Dataset already exists"

# Create optimization_results table
echo ""
echo "Creating table: optimization_results..."
# Note: For REPEATED fields, we need to use a schema file or create via Python
# The bq command line doesn't support inline REPEATED field definitions well
# So we'll use a secure temporary schema file (already created at top of script)
if ! cat > "$SCHEMA_FILE" << 'EOF'
[
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "run_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "status", "type": "STRING", "mode": "REQUIRED"},
  {"name": "profile_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "dry_run", "type": "BOOLEAN", "mode": "NULLABLE"},
  {"name": "duration_seconds", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "campaigns_analyzed", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "keywords_optimized", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "bids_increased", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "bids_decreased", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "negative_keywords_added", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "budget_changes", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "total_spend", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "total_sales", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "average_acos", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "target_acos", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "lookback_days", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "enabled_features", "type": "STRING", "mode": "REPEATED"},
  {"name": "errors", "type": "STRING", "mode": "REPEATED"},
  {"name": "warnings", "type": "STRING", "mode": "REPEATED"}
]
EOF
then
    echo "Error: Failed to write schema file"
    exit 1
fi

# Create the table with better error handling
create_table_with_error_handling --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Optimization run results and summary metrics" \
    "$PROJECT_ID:$DATASET_ID.optimization_results" \
    "$SCHEMA_FILE"

# Create campaign_details table
echo ""
echo "Creating table: campaign_details..."
create_table_with_error_handling --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Campaign-level performance details" \
    "$PROJECT_ID:$DATASET_ID.campaign_details" \
    timestamp:TIMESTAMP,run_id:STRING,campaign_id:STRING,campaign_name:STRING,spend:FLOAT,sales:FLOAT,acos:FLOAT,impressions:INTEGER,clicks:INTEGER,conversions:INTEGER,budget:FLOAT,status:STRING

# Create optimization_progress table
echo ""
echo "Creating table: optimization_progress..."
create_table_with_error_handling --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Real-time optimization progress updates" \
    "$PROJECT_ID:$DATASET_ID.optimization_progress" \
    timestamp:TIMESTAMP,run_id:STRING,status:STRING,message:STRING,percent_complete:FLOAT,profile_id:STRING

# Create optimization_errors table
echo ""
echo "Creating table: optimization_errors..."
create_table_with_error_handling --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Optimization errors and failures" \
    "$PROJECT_ID:$DATASET_ID.optimization_errors" \
    timestamp:TIMESTAMP,run_id:STRING,status:STRING,profile_id:STRING,error_type:STRING,error_message:STRING,traceback:STRING,context:STRING

# Cleanup handled by trap on EXIT

echo ""
echo "========================================="
echo "✅ BigQuery Setup Complete!"
echo "========================================="
echo ""
echo "Dataset: $PROJECT_ID:$DATASET_ID"
echo "Location: $LOCATION"
echo ""
echo "Tables created:"
echo "  - optimization_results"
echo "  - campaign_details"
echo "  - optimization_progress"
echo "  - optimization_errors"
echo ""
echo "You can now run the optimizer with BigQuery enabled in config.json"
echo ""
echo "To verify the setup:"
echo "  bq ls $PROJECT_ID:$DATASET_ID"
echo ""
echo "To grant permissions to your service account:"
echo "  PROJECT_NUMBER=\$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')"
echo "  SERVICE_ACCOUNT=\"\${PROJECT_NUMBER}-compute@developer.gserviceaccount.com\""
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:\${SERVICE_ACCOUNT}\" \\"
echo "    --role=\"roles/bigquery.dataEditor\""
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:\${SERVICE_ACCOUNT}\" \\"
echo "    --role=\"roles/bigquery.jobUser\""
echo ""
