"""Utility script to fix BigQuery Data Transfer configs.

This helper ensures that the `organization_id` parameter used by
BigQuery Data Transfer Service is a numeric string.  The Google Ads and
Campaign Manager data sources require numeric organization IDs.  The
transfer associated with this project has been failing because a text
value (e.g. a project ID) was supplied instead of the numeric
identifier.

Usage example::

    python fix_bigquery_transfer.py \
        --project-id amazon-ppc-474902 \
        --location us \
        --config-id 69588e94-0000-2970-aebe-582429ad18d4 \
        --organization-id 1234567890

The script validates the supplied organization ID and updates the
transfer configuration via the BigQuery Data Transfer API.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from google.api_core import exceptions
from google.cloud import bigquery_datatransfer
from google.protobuf import field_mask_pb2, struct_pb2


def _ensure_numeric(value: str, *, field_name: str) -> str:
    """Validate that ``value`` contains only decimal digits.

    Args:
        value: User-supplied value to validate.
        field_name: Human readable field name for error messaging.

    Returns:
        The original value when valid.

    Raises:
        ValueError: If ``value`` is empty or contains non-numeric
            characters.
    """

    if not value:
        raise ValueError(f"{field_name} is required and cannot be blank")

    normalized = value.strip()
    if not normalized.isdigit():
        raise ValueError(
            f"{field_name} must be a numeric string. Received: {value!r}"
        )

    return normalized


def update_transfer_organization_id(
    *,
    project_id: str,
    location: str,
    config_id: str,
    organization_id: str,
    dry_run: bool = False,
) -> Optional[str]:
    """Update the ``organization_id`` parameter on a transfer config.

    Args:
        project_id: Google Cloud project ID or numeric project number.
        location: BigQuery Data Transfer location (e.g. ``us``).
        config_id: Transfer configuration identifier.
        organization_id: Numeric organization ID to apply.
        dry_run: When ``True``, log the proposed change without
            performing the update.

    Returns:
        The previous organization ID if the configuration existed.

    Raises:
        google.api_core.exceptions.GoogleAPICallError: Propagates API
            errors for callers that want to handle them.
    """

    validated_org_id = _ensure_numeric(
        organization_id, field_name="organization_id"
    )

    client = bigquery_datatransfer.DataTransferServiceClient()
    transfer_name = client.transfer_config_path(
        project=project_id, location=location, transfer_config=config_id
    )

    logging.info("Fetching transfer configuration: %s", transfer_name)
    config = client.get_transfer_config(name=transfer_name)

    params_struct = struct_pb2.Struct()
    if config.params:
        params_struct.update(config.params)

    previous_org_id = params_struct.get("organization_id")
    if previous_org_id == validated_org_id:
        logging.info(
            "organization_id is already set to %s; no update required",
            validated_org_id,
        )
        return previous_org_id

    logging.info(
        "Updating organization_id from %r to %s", previous_org_id, validated_org_id
    )
    params_struct["organization_id"] = validated_org_id

    if dry_run:
        logging.info("Dry run enabled; skipping API update call")
        return previous_org_id

    config.params.CopyFrom(params_struct)
    update_mask = field_mask_pb2.FieldMask(paths=["params"])
    client.update_transfer_config(transfer_config=config, update_mask=update_mask)
    logging.info("Transfer configuration updated successfully")
    return previous_org_id


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure the BigQuery Data Transfer organization_id parameter is numeric"
        )
    )
    parser.add_argument("--project-id", required=True, help="GCP project ID or number")
    parser.add_argument("--location", required=True, help="Transfer location (e.g. us)")
    parser.add_argument(
        "--config-id",
        required=True,
        help="Transfer configuration ID (the last segment of the config name)",
    )
    parser.add_argument(
        "--organization-id",
        required=True,
        help="Numeric organization ID expected by the data source",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the proposed update without modifying the transfer",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))

    try:
        previous_value = update_transfer_organization_id(
            project_id=args.project_id,
            location=args.location,
            config_id=args.config_id,
            organization_id=args.organization_id,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        logging.error("Validation failed: %s", exc)
        return 2
    except exceptions.GoogleAPICallError as exc:
        logging.error("BigQuery Data Transfer API error: %s", exc)
        return 1

    if previous_value is None:
        logging.info("organization_id was not previously set")
    else:
        logging.info("Previous organization_id value was %s", previous_value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
