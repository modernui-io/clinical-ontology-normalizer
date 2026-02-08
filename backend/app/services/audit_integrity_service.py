"""Audit integrity verification service for tamper detection.

CISO-8: Comprehensive Audit Logging Hardening
CLO-2.5: 21 CFR Part 11 Audit Trail Compliance

Provides functions to verify the integrity of the audit log hash chain.
Each audit record contains a SHA-256 hash computed from:
    SHA-256(previous_hash | record_id | timestamp | user_id | action |
            resource_type | resource_id | patient_id)

If any record is modified, its hash will no longer match, and all
subsequent records in the chain will also fail verification.

Usage:
    from app.services.audit_integrity_service import verify_audit_chain

    result = await verify_audit_chain(db)
    if not result.is_valid:
        for error in result.errors:
            print(f"Tampering detected: {error}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


@dataclass
class ChainVerificationResult:
    """Result of an audit log hash chain verification.

    Attributes:
        is_valid: True if the entire chain is intact with no tampering detected.
        records_checked: Number of audit records examined.
        records_valid: Number of records whose hash matched the expected value.
        records_invalid: Number of records whose hash did NOT match.
        records_unchained: Number of records without hash chain data (pre-migration).
        first_invalid_id: ID of the first record that failed verification (if any).
        errors: List of human-readable error descriptions.
        verified_at: Timestamp when verification was performed.
    """

    is_valid: bool = True
    records_checked: int = 0
    records_valid: int = 0
    records_invalid: int = 0
    records_unchained: int = 0
    first_invalid_id: str | None = None
    errors: list[str] = field(default_factory=list)
    verified_at: datetime = field(default_factory=lambda: datetime.now())


async def verify_audit_chain(
    db: AsyncSession,
    start_id: str | None = None,
    end_id: str | None = None,
    batch_size: int = 1000,
) -> ChainVerificationResult:
    """Verify the integrity of the audit log hash chain.

    Walks the audit log in chronological order, recomputing each record's
    hash and comparing it to the stored hash. If any record has been
    modified, its recomputed hash will differ from the stored value.

    Args:
        db: Database session.
        start_id: If provided, start verification from this record ID.
        end_id: If provided, stop verification at this record ID.
        batch_size: Number of records to fetch per database query.

    Returns:
        ChainVerificationResult with details of the verification.
    """
    result = ChainVerificationResult()

    # Build the base query: order by timestamp ascending for chain traversal
    query = (
        select(AuditLog)
        .order_by(AuditLog.timestamp.asc())
    )

    # Apply optional range filters
    if start_id:
        # Find the timestamp of the start record to filter from there
        start_stmt = select(AuditLog.timestamp).where(AuditLog.id == start_id)
        start_result = await db.execute(start_stmt)
        start_ts = start_result.scalar_one_or_none()
        if start_ts:
            query = query.where(AuditLog.timestamp >= start_ts)

    if end_id:
        end_stmt = select(AuditLog.timestamp).where(AuditLog.id == end_id)
        end_result = await db.execute(end_stmt)
        end_ts = end_result.scalar_one_or_none()
        if end_ts:
            query = query.where(AuditLog.timestamp <= end_ts)

    # Process in batches to avoid loading the entire table into memory
    offset = 0
    expected_previous_hash: str | None = None

    while True:
        batch_query = query.limit(batch_size).offset(offset)
        batch_result = await db.execute(batch_query)
        records = list(batch_result.scalars().all())

        if not records:
            break

        for record in records:
            result.records_checked += 1

            # Skip records that predate the hash chain migration
            if record.record_hash is None:
                result.records_unchained += 1
                continue

            # Verify the previous_hash linkage
            if expected_previous_hash is not None:
                if record.previous_hash != expected_previous_hash:
                    result.is_valid = False
                    result.records_invalid += 1
                    error_msg = (
                        f"Chain break at record {record.id}: "
                        f"expected previous_hash={expected_previous_hash[:16]}..., "
                        f"got previous_hash={record.previous_hash[:16] if record.previous_hash else 'None'}..."
                    )
                    result.errors.append(error_msg)
                    if result.first_invalid_id is None:
                        result.first_invalid_id = record.id
                    logger.warning(f"AUDIT INTEGRITY: {error_msg}")

            # Recompute the hash from the record's fields
            timestamp_iso = record.timestamp.isoformat() if record.timestamp else ""
            recomputed_hash = AuditService._compute_record_hash(
                previous_hash=record.previous_hash or AuditService.GENESIS_HASH,
                record_id=record.id,
                timestamp_iso=timestamp_iso,
                user_id=record.user_id,
                action=record.action,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                patient_id=record.patient_id,
            )

            if recomputed_hash != record.record_hash:
                result.is_valid = False
                result.records_invalid += 1
                error_msg = (
                    f"Hash mismatch at record {record.id}: "
                    f"stored={record.record_hash[:16]}..., "
                    f"computed={recomputed_hash[:16]}..."
                )
                result.errors.append(error_msg)
                if result.first_invalid_id is None:
                    result.first_invalid_id = record.id
                logger.warning(f"AUDIT INTEGRITY: {error_msg}")
            else:
                result.records_valid += 1

            # Track the expected previous_hash for the next record
            expected_previous_hash = record.record_hash

        offset += batch_size

    # Log summary
    if result.is_valid:
        logger.info(
            f"AUDIT INTEGRITY: Chain verified OK. "
            f"{result.records_checked} records checked, "
            f"{result.records_valid} valid, "
            f"{result.records_unchained} pre-migration (unchained)."
        )
    else:
        logger.error(
            f"AUDIT INTEGRITY: TAMPERING DETECTED. "
            f"{result.records_invalid} invalid records out of "
            f"{result.records_checked} checked. "
            f"First invalid: {result.first_invalid_id}"
        )

    return result


async def get_chain_summary(db: AsyncSession) -> dict:
    """Get a summary of the audit chain state.

    Useful for dashboards and monitoring. Returns counts and the
    latest hash value without performing full verification.

    Args:
        db: Database session.

    Returns:
        Dictionary with chain summary statistics.
    """
    from sqlalchemy import func

    # Total records
    total_stmt = select(func.count(AuditLog.id))
    total_result = await db.execute(total_stmt)
    total_count = total_result.scalar() or 0

    # Records with hashes
    hashed_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.record_hash.isnot(None)
    )
    hashed_result = await db.execute(hashed_stmt)
    hashed_count = hashed_result.scalar() or 0

    # Latest hash
    latest_stmt = (
        select(AuditLog.record_hash, AuditLog.timestamp)
        .where(AuditLog.record_hash.isnot(None))
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    latest_result = await db.execute(latest_stmt)
    latest_row = latest_result.first()

    return {
        "total_records": total_count,
        "chained_records": hashed_count,
        "unchained_records": total_count - hashed_count,
        "latest_hash": latest_row[0] if latest_row else None,
        "latest_timestamp": (
            latest_row[1].isoformat() if latest_row and latest_row[1] else None
        ),
        "chain_coverage_pct": (
            round(hashed_count / total_count * 100, 1) if total_count > 0 else 0.0
        ),
    }
