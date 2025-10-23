import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from redis_client import redis_client

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Audit event types"""

    USER_ADDED_TO_QUEUE = "user_added_to_queue"
    USER_PROCESSED_FROM_QUEUE = "user_processed_from_queue"
    USER_ADDED_TO_LIST = "user_added_to_list"
    USER_ADD_FAILED = "user_add_failed"
    USER_LOOKUP = "user_lookup"
    RATE_LIMIT_CHECK = "rate_limit_check"
    QUEUE_STATUS_CHECK = "queue_status_check"
    API_CALL = "api_call"
    SYSTEM_ERROR = "system_error"
    HEALTH_CHECK = "health_check"
    CLEANUP_JOBS = "cleanup_jobs"


class AuditLogLevel(Enum):
    """Audit log levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLogger:
    """Audit logging service"""

    def __init__(self):
        self.redis_client = redis_client.redis_client

    async def log_event(
        self,
        event_type: AuditEventType,
        level: AuditLogLevel,
        message: str,
        user_id: str | None = None,
        username: str | None = None,
        list_id: str | None = None,
        task_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        additional_data: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> str:
        """
        Log an audit event
        Returns the audit log ID
        """
        try:
            audit_id = str(uuid.uuid4())
            timestamp = datetime.now(UTC)

            audit_entry = {
                "id": audit_id,
                "timestamp": timestamp.isoformat(),
                "event_type": event_type.value,
                "level": level.value,
                "message": message,
                "user_id": user_id,
                "username": username,
                "list_id": list_id,
                "task_id": task_id,
                "request_id": request_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "error_message": error_message,
                "additional_data": additional_data or {},
            }

            # Store in Redis with TTL (30 days)
            audit_key = f"audit_log:{audit_id}"
            await self.redis_client.setex(
                audit_key,
                30 * 24 * 3600,  # 30 days
                json.dumps(audit_entry, default=str),
            )

            # Add to time-series index
            time_index_key = f"audit_logs_by_time:{timestamp.strftime('%Y-%m-%d')}"
            await self.redis_client.zadd(
                time_index_key,
                {audit_id: timestamp.timestamp()},
            )
            await self.redis_client.expire(time_index_key, 30 * 24 * 3600)

            # Add to event type index
            event_index_key = f"audit_logs_by_event:{event_type.value}"
            await self.redis_client.zadd(
                event_index_key,
                {audit_id: timestamp.timestamp()},
            )
            await self.redis_client.expire(event_index_key, 30 * 24 * 3600)

            # Add to user index (if user info available)
            if username:
                user_index_key = f"audit_logs_by_user:{username}"
                await self.redis_client.zadd(
                    user_index_key,
                    {audit_id: timestamp.timestamp()},
                )
                await self.redis_client.expire(user_index_key, 30 * 24 * 3600)

            logger.info(f"Audit log created: {event_type.value} - {message}")
            return audit_id

        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            return None

    async def get_audit_logs(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_type: AuditEventType | None = None,
        username: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Retrieve audit logs with filtering
        """
        try:
            # Determine which index to use
            if event_type:
                index_key = f"audit_logs_by_event:{event_type.value}"
            elif username:
                index_key = f"audit_logs_by_user:{username}"
            elif start_date:
                date_str = start_date.strftime("%Y-%m-%d")
                index_key = f"audit_logs_by_time:{date_str}"
            else:
                # Get from today's index
                today = datetime.now(UTC).strftime("%Y-%m-%d")
                index_key = f"audit_logs_by_time:{today}"

            # Get audit log IDs from index
            if start_date and end_date:
                audit_ids = await self.redis_client.zrangebyscore(
                    index_key,
                    start_date.timestamp(),
                    end_date.timestamp(),
                    start=offset,
                    num=limit,
                )
            else:
                audit_ids = await self.redis_client.zrevrange(
                    index_key,
                    offset,
                    offset + limit - 1,
                )

            # Fetch audit log details
            audit_logs = []
            for audit_id in audit_ids:
                audit_key = f"audit_log:{audit_id}"
                audit_data = await self.redis_client.get(audit_key)
                if audit_data:
                    audit_logs.append(json.loads(audit_data))

            return audit_logs

        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {str(e)}")
            return []

    async def get_audit_stats(self, days: int = 7) -> dict[str, Any]:
        """
        Get audit statistics for the last N days
        """
        try:
            stats = {
                "total_events": 0,
                "events_by_type": {},
                "events_by_level": {},
                "success_rate": 0,
                "error_count": 0,
                "date_range": {},
            }

            # Get events from the last N days
            for i in range(days):
                date = datetime.now(UTC) - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                time_index_key = f"audit_logs_by_time:{date_str}"

                audit_ids = await self.redis_client.zrange(time_index_key, 0, -1)

                for audit_id in audit_ids:
                    audit_key = f"audit_log:{audit_id}"
                    audit_data = await self.redis_client.get(audit_key)

                    if audit_data:
                        audit_entry = json.loads(audit_data)
                        stats["total_events"] += 1

                        # Count by event type
                        event_type = audit_entry.get("event_type", "unknown")
                        stats["events_by_type"][event_type] = (
                            stats["events_by_type"].get(event_type, 0) + 1
                        )

                        # Count by level
                        level = audit_entry.get("level", "info")
                        stats["events_by_level"][level] = (
                            stats["events_by_level"].get(level, 0) + 1
                        )

                        # Count success/failure
                        if not audit_entry.get("success", True):
                            stats["error_count"] += 1

            # Calculate success rate
            if stats["total_events"] > 0:
                stats["success_rate"] = (
                    (stats["total_events"] - stats["error_count"])
                    / stats["total_events"]
                ) * 100

            return stats

        except Exception as e:
            logger.error(f"Failed to get audit stats: {str(e)}")
            return {}

    async def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """
        Clean up audit logs older than specified days
        Returns number of logs cleaned up
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)
            cleaned_count = 0

            # Get all date indexes
            pattern = "audit_logs_by_time:*"
            date_keys = await self.redis_client.keys(pattern)

            for date_key in date_keys:
                # Get audit IDs older than cutoff
                old_audit_ids = await self.redis_client.zrangebyscore(
                    date_key,
                    0,
                    cutoff_date.timestamp(),
                )

                for audit_id in old_audit_ids:
                    # Delete the audit log
                    audit_key = f"audit_log:{audit_id}"
                    await self.redis_client.delete(audit_key)

                    # Remove from indexes
                    await self.redis_client.zrem(date_key, audit_id)
                    cleaned_count += 1

            logger.info(f"Cleaned up {cleaned_count} old audit logs")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {str(e)}")
            return 0


# Global audit logger instance
audit_logger = AuditLogger()
