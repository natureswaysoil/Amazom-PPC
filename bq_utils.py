import os
import json
from google.cloud import bigquery
from datetime import datetime

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
DATASET_ID = "amazon_ppc" # As requested
TABLE_ID = "optimization_log"

def get_bq_client():
    """Initialize BigQuery Client using existing GCP credentials"""
    try:
        return bigquery.Client(project=PROJECT_ID)
    except Exception as e:
        print(f"Error initializing BigQuery client: {e}")
        return None

def ensure_dataset_and_table(client):
    """Checks if dataset/table exists, creates them if not"""
    dataset_ref = client.dataset(DATASET_ID)
    
    # 1. Create Dataset if not exists
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        print(f"Creating dataset {DATASET_ID}...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US" # Adjust location if needed (e.g., us-east4)
        client.create_dataset(dataset)

    # 2. Create Table if not exists
    table_ref = dataset_ref.table(TABLE_ID)
    
    schema = [
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("profile_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("campaign_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("keyword_text", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("old_bid", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("new_bid", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("acos", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("action_taken", "STRING", mode="NULLABLE"), # e.g., "INCREASE_BID", "PAUSE"
        bigquery.SchemaField("raw_data", "JSON", mode="NULLABLE") # Stores the full context
    ]

    try:
        client.get_table(table_ref)
    except Exception:
        print(f"Creating table {TABLE_ID}...")
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)

def log_optimization_results(results_payload, profile_id):
    """
    Parses the optimizer results and writes them to BigQuery.
    """
    client = get_bq_client()
    if not client:
        return

    # Ensure DB exists
    ensure_dataset_and_table(client)

    rows_to_insert = []
    timestamp = datetime.utcnow().isoformat()
    run_id = f"{profile_id}-{int(datetime.utcnow().timestamp())}"

    # Logic to parse your specific results payload
    # Assuming 'results_payload' contains a list of changes or a summary
    # You may need to adjust this parsing logic based on your exact dictionary structure
    
    if "changes" in results_payload:
        for change in results_payload["changes"]:
            row = {
                "run_id": run_id,
                "timestamp": timestamp,
                "profile_id": str(profile_id),
                "campaign_name": change.get("campaign_name", "N/A"),
                "keyword_text": change.get("keyword", "N/A"),
                "old_bid": change.get("old_bid"),
                "new_bid": change.get("new_bid"),
                "acos": change.get("acos"),
                "action_taken": change.get("action"),
                "raw_data": json.dumps(change)
            }
            rows_to_insert.append(row)
    
    # If no granular changes, log the summary
    else:
         rows_to_insert.append({
            "run_id": run_id,
            "timestamp": timestamp,
            "profile_id": str(profile_id),
            "action_taken": "RUN_COMPLETED",
            "raw_data": json.dumps(results_payload)
        })

    if rows_to_insert:
        errors = client.insert_rows_json(f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}", rows_to_insert)
        if errors == []:
            print("✅ Successfully wrote results to BigQuery.")
        else:
            print(f"❌ Encounted errors inserting rows: {errors}")
