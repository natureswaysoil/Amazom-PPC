#!/bin/bash
# Setup BigQuery Dataset and Tables for Amazon PPC Optimizer
# This script creates the necessary BigQuery infrastructure

set -e

# Configuration
PROJECT_ID="${1:-amazon-ppc-474902}"
DATASET_ID="${2:-amazon_ppc}"
LOCATION="${3:-us-east4}"

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
bq mk --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Optimization run results and summary metrics" \
    "$PROJECT_ID:$DATASET_ID.optimization_results" \
    timestamp:TIMESTAMP,run_id:STRING,status:STRING,profile_id:STRING,dry_run:BOOLEAN,duration_seconds:FLOAT,campaigns_analyzed:INTEGER,keywords_optimized:INTEGER,bids_increased:INTEGER,bids_decreased:INTEGER,negative_keywords_added:INTEGER,budget_changes:INTEGER,total_spend:FLOAT,total_sales:FLOAT,average_acos:FLOAT,target_acos:FLOAT,lookback_days:INTEGER,enabled_features:STRING,errors:STRING,warnings:STRING \
    2>/dev/null || echo "Table already exists"

# Create campaign_details table
echo ""
echo "Creating table: campaign_details..."
bq mk --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Campaign-level performance details" \
    "$PROJECT_ID:$DATASET_ID.campaign_details" \
    timestamp:TIMESTAMP,run_id:STRING,campaign_id:STRING,campaign_name:STRING,spend:FLOAT,sales:FLOAT,acos:FLOAT,impressions:INTEGER,clicks:INTEGER,conversions:INTEGER,budget:FLOAT,status:STRING \
    2>/dev/null || echo "Table already exists"

# Create optimization_progress table
echo ""
echo "Creating table: optimization_progress..."
bq mk --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Real-time optimization progress updates" \
    "$PROJECT_ID:$DATASET_ID.optimization_progress" \
    timestamp:TIMESTAMP,run_id:STRING,status:STRING,message:STRING,percent_complete:FLOAT,profile_id:STRING \
    2>/dev/null || echo "Table already exists"

# Create optimization_errors table
echo ""
echo "Creating table: optimization_errors..."
bq mk --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    --description="Optimization errors and failures" \
    "$PROJECT_ID:$DATASET_ID.optimization_errors" \
    timestamp:TIMESTAMP,run_id:STRING,status:STRING,profile_id:STRING,error_type:STRING,error_message:STRING,traceback:STRING,context:STRING \
    2>/dev/null || echo "Table already exists"

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
