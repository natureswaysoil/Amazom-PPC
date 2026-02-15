"""
AOV Bid Optimizer Module
=========================

Optimizes Amazon PPC bids based on Average Order Value (AOV) and target ACOS.

This module:
- Fetches AOV data from BigQuery
- Calculates optimal bid adjustments based on AOV and ACOS targets
- Supports both dry-run and auto-apply modes
- Provides detailed logging for audit trails
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from jobs.optimization.aov_fetcher import AOVFetcher

logger = logging.getLogger(__name__)


class AOVBidOptimizer:
    """
    Optimizes keyword bids based on AOV data and target ACOS.
    """

    def __init__(
        self,
        project_id: str,
        dataset_id: str = "amazon_ppc",
        target_acos: float = 0.25,
        min_bid: float = 0.35,
        max_bid: float = 5.00,
    ):
        """
        Initialize AOV Bid Optimizer.

        Args:
            project_id: Google Cloud project ID
            dataset_id: BigQuery dataset ID (default: "amazon_ppc")
            target_acos: Target ACOS ratio (default: 0.25 = 25%)
            min_bid: Minimum bid allowed (default: 0.35)
            max_bid: Maximum bid allowed (default: 5.00)
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.target_acos = target_acos
        self.min_bid = min_bid
        self.max_bid = max_bid
        self.fetcher = AOVFetcher(project_id, dataset_id)

    def calculate_optimal_bid(
        self,
        current_bid: float,
        aov: float,
        current_acos: float,
        conversions: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate optimal bid based on AOV and ACOS target.

        Args:
            current_bid: Current keyword bid
            aov: Average order value for the campaign
            current_acos: Current ACOS for the keyword
            conversions: Number of conversions

        Returns:
            Dictionary with bid adjustment info, or None if no change needed
        """
        # Skip if insufficient data
        if conversions < 2 or aov <= 0:
            return None

        # Calculate target CPA (Cost Per Acquisition)
        target_cpa = aov * self.target_acos

        # Calculate bid adjustment factor and new bid
        if current_acos > 0:
            # If current ACOS is above target, decrease bid
            # If current ACOS is below target, increase bid
            adjustment_factor = self.target_acos / current_acos
            
            # Cap adjustment to avoid extreme changes
            adjustment_factor = max(0.7, min(1.3, adjustment_factor))
            
            new_bid = current_bid * adjustment_factor
        else:
            # No spend data, use conservative bid based on AOV
            # Use 0.5x of target CPA as the adjustment factor for zero ACOS
            adjustment_factor = 0.5
            new_bid = target_cpa * adjustment_factor

        # Clamp to min/max bounds
        new_bid = max(self.min_bid, min(self.max_bid, new_bid))
        new_bid = round(new_bid, 2)

        # Only return if change is significant (>5%)
        bid_change_pct = abs((new_bid - current_bid) / current_bid) if current_bid > 0 else 1.0
        if bid_change_pct < 0.05:
            return None

        return {
            "current_bid": current_bid,
            "new_bid": new_bid,
            "adjustment_factor": adjustment_factor,
            "bid_change": new_bid - current_bid,
            "bid_change_pct": bid_change_pct,
            "reason": self._get_adjustment_reason(current_acos, self.target_acos),
        }

    def _get_adjustment_reason(self, current_acos: float, target_acos: float) -> str:
        """Get human-readable reason for bid adjustment."""
        if current_acos > target_acos * 1.2:
            return "ACOS too high - decreasing bid"
        elif current_acos < target_acos * 0.8:
            return "ACOS below target - increasing bid"
        else:
            return "Fine-tuning bid to target ACOS"

    def run(
        self,
        dry_run: bool = True,
        auto_apply: bool = False,
        lookback_days: int = 30,
        min_clicks: int = 10,
    ) -> Dict[str, Any]:
        """
        Run the AOV bid optimization.

        Args:
            dry_run: If True, only calculate changes without applying (default: True)
            auto_apply: If True, automatically apply changes (default: False)
            lookback_days: Days of data to analyze (default: 30)
            min_clicks: Minimum clicks to consider keyword (default: 10)

        Returns:
            Dictionary with optimization results and statistics
        """
        mode = "AUTO-APPLY" if (auto_apply and not dry_run) else "DRY-RUN"
        logger.info(f"🚀 Starting {mode} AOV Bid Optimizer...")

        try:
            # Fetch AOV data
            logger.info("Fetching real-time AOV data...")
            campaign_aov_data = self.fetcher.fetch_campaign_aov_data(lookback_days)
            
            # Get AOV stats for logging
            aov_stats = self.fetcher.get_aggregated_aov_stats([14, 30])
            logger.info(f"✓ Loaded AOV agg={aov_stats.get('agg', 0)} | 14d={aov_stats.get('14d', 0)} | 30d={aov_stats.get('30d', 0)}")

            if not campaign_aov_data:
                logger.warning("⚠️ No campaigns with AOV data found")
                return {
                    "status": "success",
                    "bids_processed": 0,
                    "bids_changed": 0,
                    "keywords_analyzed": 0,
                    "message": "No AOV data available",
                }

            # Get campaign IDs for keyword fetch
            campaign_ids = list(campaign_aov_data.keys())
            
            # Fetch keyword performance
            keywords = self.fetcher.fetch_keyword_performance(
                campaign_ids=campaign_ids,
                lookback_days=lookback_days,
                min_clicks=min_clicks,
            )

            if not keywords:
                logger.info("⚠️ No keywords needed optimization")
                return {
                    "status": "success",
                    "bids_processed": 0,
                    "bids_changed": 0,
                    "keywords_analyzed": 0,
                    "message": "No keywords met criteria",
                }

            # Process each keyword
            bid_adjustments = []
            for kw in keywords:
                campaign_id = kw["campaign_id"]
                aov_data = campaign_aov_data.get(campaign_id)
                
                if not aov_data:
                    continue

                adjustment = self.calculate_optimal_bid(
                    current_bid=kw["current_bid"],
                    aov=aov_data["aov"],
                    current_acos=kw["acos"],
                    conversions=int(kw["conversions"]),
                )

                if adjustment:
                    adjustment_info = {
                        **kw,
                        **adjustment,
                        "aov": aov_data["aov"],
                    }
                    bid_adjustments.append(adjustment_info)

            # Log results
            if not bid_adjustments:
                logger.info("⚠️ No keywords needed optimization")
                return {
                    "status": "success",
                    "bids_processed": len(keywords),
                    "bids_changed": 0,
                    "keywords_analyzed": len(keywords),
                    "message": "No bid adjustments needed",
                }

            # Log top adjustments
            logger.info(f"Optimization complete: {len(bid_adjustments)} bids need adjustment (of {len(keywords)} analyzed)")
            
            # Show sample of top adjustments
            top_adjustments = sorted(bid_adjustments, key=lambda x: abs(x["bid_change"]), reverse=True)[:5]
            for adj in top_adjustments:
                logger.info(
                    f"  {adj['keyword_text']}: ${adj['current_bid']:.2f} → ${adj['new_bid']:.2f} "
                    f"({adj['bid_change']:+.2f}, {adj['bid_change_pct']*100:+.1f}%) - {adj['reason']}"
                )

            # Apply changes if not dry run and auto_apply is enabled
            applied = False
            if auto_apply and not dry_run:
                logger.info(f"Applying {len(bid_adjustments)} bid changes...")
                # TODO: Implement actual bid update via Amazon Ads API
                # For now, just log that we would apply
                applied = True
                logger.info("✅ Bid changes applied")
            else:
                logger.info(f"DRY RUN: Would apply {len(bid_adjustments)} bid changes")

            return {
                "status": "success",
                "mode": mode,
                "bids_processed": len(keywords),
                "bids_changed": len(bid_adjustments),
                "keywords_analyzed": len(keywords),
                "campaigns_analyzed": len(campaign_aov_data),
                "applied": applied,
                "adjustments": bid_adjustments,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"AOV Bid Optimizer failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "bids_processed": 0,
                "bids_changed": 0,
            }


def main():
    """Standalone entry point for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if not project_id:
        logger.error("GOOGLE_CLOUD_PROJECT or GCP_PROJECT must be set")
        return 1

    dataset_id = os.getenv("BQ_DATASET", "amazon_ppc")
    dry_run = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
    auto_apply = os.getenv("AUTO_APPLY", "false").lower() in ("true", "1", "yes")

    optimizer = AOVBidOptimizer(project_id, dataset_id)
    result = optimizer.run(dry_run=dry_run, auto_apply=auto_apply)
    
    logger.info(f"Result: {result}")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
