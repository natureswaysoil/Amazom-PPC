#!/usr/bin/env python3
"""
Generate Sample Data for Dashboard Demo
========================================

This script generates realistic sample PPC optimization data and writes it to BigQuery
so you can see the dashboard working without running the actual optimizer.

Usage:
    python generate_sample_data.py

Requirements:
    - BigQuery credentials configured (GOOGLE_APPLICATION_CREDENTIALS or GCP_CREDENTIALS_JSON)
    - GCP_PROJECT_ID environment variable set
"""

import os
import sys
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add parent directory to path to import bigquery_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bigquery_client import BigQueryClient

# Sample campaign names
CAMPAIGN_NAMES = [
    "Organic Fertilizer - Exact Match",
    "Garden Soil - Broad Match",
    "Potting Mix - Phrase Match",
    "Plant Food - Auto Campaign",
    "Compost - Brand Defense",
    "Mulch Products - Sponsored Brand",
    "Soil Amendments - Display",
    "Worm Castings - High Intent",
]

# Sample keyword texts
KEYWORDS = [
    "organic fertilizer",
    "garden soil",
    "potting mix",
    "plant food",
    "compost",
    "mulch",
    "soil amendment",
    "worm castings",
    "organic potting soil",
    "raised bed soil",
    "vegetable garden soil",
    "indoor plant food",
]


def generate_optimization_results(num_runs: int = 5) -> List[Dict[str, Any]]:
    """Generate sample optimization results"""
    results = []
    
    for i in range(num_runs):
        # Generate timestamp going back in time
        timestamp = datetime.now() - timedelta(days=i * 3, hours=random.randint(0, 23))
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        
        # Generate realistic metrics
        keywords_optimized = random.randint(50, 200)
        campaigns_analyzed = random.randint(5, 15)
        bids_increased = random.randint(20, 80)
        bids_decreased = random.randint(15, 60)
        
        total_spend = round(random.uniform(500, 2000), 2)
        total_sales = round(total_spend * random.uniform(3, 8), 2)  # ROAS 3-8x
        average_acos = round(total_spend / total_sales, 4) if total_sales > 0 else 0.25
        
        status = "success" if random.random() > 0.1 else "completed_with_warnings"
        
        result = {
            "timestamp": timestamp.isoformat(),
            "run_id": run_id,
            "status": status,
            "profile_id": "1780498399290938",
            "dry_run": False,
            "duration_seconds": round(random.uniform(45, 180), 2),
            "campaigns_analyzed": campaigns_analyzed,
            "keywords_optimized": keywords_optimized,
            "bids_increased": bids_increased,
            "bids_decreased": bids_decreased,
            "negative_keywords_added": random.randint(5, 25),
            "budget_changes": random.randint(1, 8),
            "total_spend": total_spend,
            "total_sales": total_sales,
            "average_acos": average_acos,
            "target_acos": 0.25,
            "lookback_days": 30,
            "enabled_features": ["bid_optimization", "dayparting", "negative_keywords"],
            "errors": [] if status == "success" else ["Minor API timeout recovered"],
            "warnings": ["Campaign ABC paused due to low performance"] if random.random() > 0.7 else [],
            "campaigns": "{}",  # JSON placeholder
            "top_performers": "{}",  # JSON placeholder
            "features": "{}",  # JSON placeholder
            "config_snapshot": "{}",  # JSON placeholder
        }
        
        results.append(result)
    
    return results


def generate_campaign_details(num_runs: int = 5) -> List[Dict[str, Any]]:
    """Generate sample campaign details"""
    campaigns = []
    
    for i in range(num_runs):
        timestamp = datetime.now() - timedelta(days=i * 3, hours=random.randint(0, 23))
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        
        # Generate data for each campaign
        for campaign_name in random.sample(CAMPAIGN_NAMES, random.randint(4, 7)):
            spend = round(random.uniform(50, 400), 2)
            sales = round(spend * random.uniform(2.5, 9), 2)
            acos = round(spend / sales, 4) if sales > 0 else 0.30
            
            campaign = {
                "timestamp": timestamp.isoformat(),
                "run_id": run_id,
                "campaign_id": f"camp_{uuid.uuid4().hex[:8]}",
                "campaign_name": campaign_name,
                "spend": spend,
                "sales": sales,
                "acos": acos,
                "impressions": random.randint(5000, 50000),
                "clicks": random.randint(100, 1000),
                "conversions": random.randint(10, 100),
                "budget": round(random.uniform(100, 500), 2),
                "status": random.choice(["enabled", "enabled", "enabled", "paused"]),
            }
            
            campaigns.append(campaign)
    
    return campaigns


def generate_optimization_progress(num_runs: int = 5) -> List[Dict[str, Any]]:
    """Generate sample optimization progress entries"""
    progress_entries = []
    
    for i in range(num_runs):
        timestamp = datetime.now() - timedelta(days=i * 3, hours=random.randint(0, 23))
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        
        # Progress stages
        stages = [
            ("initializing", 0, "Initializing optimizer"),
            ("fetching_data", 20, "Fetching campaign data from Amazon API"),
            ("analyzing_campaigns", 40, "Analyzing campaign performance"),
            ("optimizing_bids", 60, "Optimizing keyword bids"),
            ("applying_changes", 80, "Applying optimization changes"),
            ("completing", 100, "Optimization completed successfully"),
        ]
        
        for stage, progress, message in stages:
            entry = {
                "timestamp": (timestamp + timedelta(minutes=random.randint(1, 5))).isoformat(),
                "run_id": run_id,
                "stage": stage,
                "progress_percent": progress,
                "message": message,
            }
            progress_entries.append(entry)
    
    return progress_entries


def generate_optimization_errors(num_errors: int = 3) -> List[Dict[str, Any]]:
    """Generate sample optimization errors"""
    errors = []
    
    error_types = [
        ("api_timeout", "Amazon API request timeout after 30 seconds", "Retrying with exponential backoff"),
        ("rate_limit", "Rate limit exceeded for Amazon Advertising API", "Waiting 60 seconds before retry"),
        ("invalid_bid", "Bid value $0.15 below minimum for keyword 'organic soil'", "Adjusting to minimum bid $0.25"),
    ]
    
    for i in range(num_errors):
        timestamp = datetime.now() - timedelta(days=i * 5, hours=random.randint(0, 23))
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        error_type, message, context = random.choice(error_types)
        
        error = {
            "timestamp": timestamp.isoformat(),
            "run_id": run_id,
            "error_type": error_type,
            "error_message": message,
            "context": context,
            "resolved": True,
        }
        
        errors.append(error)
    
    return errors


def generate_optimizer_run_events(num_runs: int = 5) -> List[Dict[str, Any]]:
    """Generate sample optimizer run events"""
    events = []
    
    for i in range(num_runs):
        timestamp = datetime.now() - timedelta(days=i * 3, hours=random.randint(0, 23))
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        
        # Start event
        events.append({
            "timestamp": timestamp.isoformat(),
            "run_id": run_id,
            "status": "started",
            "details": "Optimization run started"
        })
        
        # Complete event
        events.append({
            "timestamp": (timestamp + timedelta(minutes=random.randint(2, 10))).isoformat(),
            "run_id": run_id,
            "status": "completed" if random.random() > 0.1 else "completed_with_warnings",
            "details": "Optimization run completed successfully"
        })
    
    return events


def main():
    """Main function to generate and write sample data"""
    print("=" * 60)
    print("Dashboard Sample Data Generator")
    print("=" * 60)
    print()
    
    # Check for required environment variables
    project_id = os.getenv('GCP_PROJECT_ID', 'nature-way-soils')
    dataset_id = os.getenv('BIGQUERY_DATASET', 'amazon_ppc')
    
    print(f"Project ID: {project_id}")
    print(f"Dataset ID: {dataset_id}")
    print()
    
    # Check for credentials
    if not any([
        os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
        os.getenv('GCP_CREDENTIALS_JSON'),
        os.getenv('GCP_CREDENTIALS_BASE64')
    ]):
        print("⚠️  WARNING: No BigQuery credentials found!")
        print("   Set one of:")
        print("   - GOOGLE_APPLICATION_CREDENTIALS")
        print("   - GCP_CREDENTIALS_JSON")
        print("   - GCP_CREDENTIALS_BASE64")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    try:
        # Initialize BigQuery client
        print("Initializing BigQuery client...")
        client = BigQueryClient(project_id=project_id, dataset_id=dataset_id)
        print("✓ BigQuery client initialized")
        print()
        
        # Generate data
        print("Generating sample data...")
        num_runs = 10  # Generate data for 10 optimization runs
        
        optimization_results = generate_optimization_results(num_runs)
        campaign_details = generate_campaign_details(num_runs)
        optimization_progress = generate_optimization_progress(num_runs)
        optimization_errors = generate_optimization_errors(5)
        run_events = generate_optimizer_run_events(num_runs)
        
        print(f"✓ Generated {len(optimization_results)} optimization results")
        print(f"✓ Generated {len(campaign_details)} campaign details")
        print(f"✓ Generated {len(optimization_progress)} progress entries")
        print(f"✓ Generated {len(optimization_errors)} error entries")
        print(f"✓ Generated {len(run_events)} run events")
        print()
        
        # Write to BigQuery
        print("Writing data to BigQuery...")
        
        # Write optimization results
        for result in optimization_results:
            success = client.write_optimization_results(result)
            if not success:
                print(f"⚠️  Failed to write optimization result: {result['run_id']}")
        print(f"✓ Wrote {len(optimization_results)} optimization results")
        
        # Write campaign details (using internal method)
        # Note: We'll directly insert to BigQuery since the public API expects specific format
        from google.cloud import bigquery as bq
        table_ref = f"{project_id}.{dataset_id}.campaign_details"
        errors = client.client.insert_rows_json(table_ref, campaign_details)
        if errors:
            print(f"⚠️  Errors writing campaign details: {errors}")
        else:
            print(f"✓ Wrote {len(campaign_details)} campaign details")
        
        # Write progress entries
        table_ref = f"{project_id}.{dataset_id}.optimization_progress"
        errors = client.client.insert_rows_json(table_ref, optimization_progress)
        if errors:
            print(f"⚠️  Errors writing progress: {errors}")
        else:
            print(f"✓ Wrote {len(optimization_progress)} progress entries")
        
        # Write errors
        table_ref = f"{project_id}.{dataset_id}.optimization_errors"
        errors = client.client.insert_rows_json(table_ref, optimization_errors)
        if errors:
            print(f"⚠️  Errors writing errors: {errors}")
        else:
            print(f"✓ Wrote {len(optimization_errors)} error entries")
        
        # Write run events
        table_ref = f"{project_id}.{dataset_id}.optimizer_run_events"
        errors = client.client.insert_rows_json(table_ref, run_events)
        if errors:
            print(f"⚠️  Errors writing run events: {errors}")
        else:
            print(f"✓ Wrote {len(run_events)} run events")
        
        print()
        print("=" * 60)
        print("✓ Sample data generation complete!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Start the dashboard: cd dashboard && python app.py")
        print("2. Open http://localhost:8080")
        print("3. You should now see populated charts and data!")
        print()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Error generating sample data")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print()
        print("Troubleshooting:")
        print("1. Check BigQuery credentials are set")
        print("2. Verify project ID and dataset exist")
        print("3. Ensure service account has BigQuery Data Editor role")
        import traceback
        print()
        print("Full error:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
