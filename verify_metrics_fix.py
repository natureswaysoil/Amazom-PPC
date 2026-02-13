#!/usr/bin/env python3
"""
Quick verification script to check if dashboard metrics are being calculated correctly.
This can be run after deployment to ensure the fixes are working.

Usage:
    python verify_metrics_fix.py [--config config.json] [--dry-run]
"""

import argparse
import json
import sys

def verify_results(results: dict) -> bool:
    """Verify that results contain expected metrics and no obvious issues"""
    
    print("\n" + "=" * 80)
    print("VERIFYING METRICS FIX")
    print("=" * 80)
    
    issues = []
    warnings = []
    
    # Check bid_optimization metrics
    if 'bid_optimization' in results:
        bid_opt = results['bid_optimization']
        spend = bid_opt.get('total_spend', 0)
        sales = bid_opt.get('total_sales', 0)
        keywords = bid_opt.get('keywords_analyzed', 0)
        
        print(f"\n✓ Bid Optimization:")
        print(f"  - Keywords analyzed: {keywords}")
        print(f"  - Total spend: ${spend:.2f}")
        print(f"  - Total sales: ${sales:.2f}")
        
        if keywords > 0 and spend == 0:
            issues.append("Bid optimization has keywords but $0 spend - possible aggregation bug")
        
        if spend > 0 and sales == 0:
            warnings.append("Bid optimization has spend but $0 sales - may be normal if no conversions")
    
    # Check campaign_management metrics
    if 'campaign_management' in results:
        camp_mgmt = results['campaign_management']
        spend = camp_mgmt.get('total_spend', 0)
        sales = camp_mgmt.get('total_sales', 0)
        campaigns = camp_mgmt.get('campaigns_analyzed', 0)
        
        print(f"\n✓ Campaign Management:")
        print(f"  - Campaigns analyzed: {campaigns}")
        print(f"  - Total spend: ${spend:.2f}")
        print(f"  - Total sales: ${sales:.2f}")
        
        if campaigns > 0 and spend == 0:
            issues.append("Campaign management has campaigns but $0 spend - possible aggregation bug")
    
    # Check for double-counting (spend from both features should be similar)
    if 'bid_optimization' in results and 'campaign_management' in results:
        bid_spend = results['bid_optimization'].get('total_spend', 0)
        camp_spend = results['campaign_management'].get('total_spend', 0)
        
        # They should be similar (within 10% tolerance) since they measure the same data
        if bid_spend > 0 and camp_spend > 0:
            diff_pct = abs(bid_spend - camp_spend) / max(bid_spend, camp_spend)
            
            if diff_pct > 0.1:
                warnings.append(
                    f"Spend differs significantly between bid_opt (${bid_spend:.2f}) "
                    f"and campaign_mgmt (${camp_spend:.2f}) - {diff_pct*100:.1f}% difference"
                )
    
    # Check keyword_discovery metrics
    if 'keyword_discovery' in results:
        kd = results['keyword_discovery']
        discovered = kd.get('keywords_discovered', 0)
        added = kd.get('keywords_added', 0)
        
        print(f"\n✓ Keyword Discovery:")
        print(f"  - Keywords discovered: {discovered}")
        print(f"  - Keywords added: {added}")
        
        if added > discovered:
            issues.append("More keywords added than discovered - data inconsistency")
    else:
        warnings.append("No keyword_discovery results found")
    
    # Check dayparting metrics
    if 'dayparting' in results:
        dp = results['dayparting']
        updated = dp.get('keywords_updated', 0)
        current_hour = dp.get('current_hour')
        current_day = dp.get('current_day')
        multiplier = dp.get('multiplier')
        
        print(f"\n✓ Dayparting:")
        print(f"  - Keywords updated: {updated}")
        print(f"  - Current time: {current_day} {current_hour}:00")
        print(f"  - Multiplier: {multiplier}")
    else:
        warnings.append("No dayparting results found")
    
    # Check negative_keywords metrics
    if 'negative_keywords' in results:
        nk = results['negative_keywords']
        added = nk.get('negative_keywords_added', 0)
        
        print(f"\n✓ Negative Keywords:")
        print(f"  - Negative keywords added: {added}")
    else:
        warnings.append("No negative_keywords results found")
    
    # Print summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    
    if issues:
        print(f"\n❌ ISSUES FOUND ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not issues and not warnings:
        print("\n✅ ALL CHECKS PASSED - Metrics look correct!")
        return True
    elif not issues:
        print("\n✅ NO CRITICAL ISSUES - Some warnings noted above")
        return True
    else:
        print("\n❌ CRITICAL ISSUES FOUND - Review results above")
        return False


def main():
    parser = argparse.ArgumentParser(description='Verify dashboard metrics are correct')
    parser.add_argument('--results-file', help='Path to results JSON file to verify')
    parser.add_argument('--results-json', help='Results JSON as a string')
    
    args = parser.parse_args()
    
    if args.results_file:
        with open(args.results_file, 'r') as f:
            results = json.load(f)
    elif args.results_json:
        results = json.loads(args.results_json)
    else:
        print("Usage: python verify_metrics_fix.py --results-file results.json")
        print("   or: python verify_metrics_fix.py --results-json '{...}'")
        print("\nRun the optimizer and save results to a JSON file, then verify:")
        print("   python optimizer_core.py --config config.json --dry-run > results.json")
        print("   python verify_metrics_fix.py --results-file results.json")
        return 1
    
    success = verify_results(results)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
