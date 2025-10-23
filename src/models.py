from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserRequest(BaseModel):
    username: str = Field(
        ...,
        description="X username to add to list",
        min_length=1,
        max_length=50,
    )


class UserResponse(BaseModel):
    success: bool
    message: str
    user_id: str | None = None
    username: str | None = None
    rate_limited: bool = False
    next_available: datetime | None = None


class UserData(BaseModel):
    id: str
    username: str
    name: str
    public_metrics: dict[str, Any] | None = None


class ListMemberRequest(BaseModel):
    username: str = Field(
        ...,
        description="X username to add to list",
        min_length=1,
        max_length=50,
    )
    list_id: str | None = Field(
        None,
        description="List ID (uses default if not provided)",
    )


class HealthResponse(BaseModel):
    status: str
    redis_connected: bool
    x_api_configured: bool


class QueueStatusResponse(BaseModel):
    success: bool
    queue_length: int
    completed_jobs: list[dict[str, Any]]
    list_id: str
    message: str | None = None
    task_state: str | None = None
    task_result: Any | None = None


class QueueUserRequest(BaseModel):
    username: str = Field(
        ...,
        description="X username to add to queue",
        min_length=1,
        max_length=50,
    )
    list_id: str | None = Field(
        None,
        description="List ID (uses default if not provided)",
    )


class QueueUserResponse(BaseModel):
    success: bool
    message: str
    task_id: str | None = None
    queue_position: int | None = None


# Audit Log Models
class AuditLogEntry(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    level: str
    message: str
    user_id: str | None = None
    username: str | None = None
    list_id: str | None = None
    task_id: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool
    error_message: str | None = None
    additional_data: dict[str, Any] | None = None


class AuditLogQuery(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    event_type: str | None = None
    username: str | None = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class AuditLogResponse(BaseModel):
    success: bool
    logs: list[AuditLogEntry]
    total_count: int
    has_more: bool


class AuditStatsResponse(BaseModel):
    success: bool
    stats: dict[str, Any]


class AllTasksStatusResponse(BaseModel):
    success: bool
    system_status: dict[str, Any]
    queue_status: dict[str, Any]
    completed_jobs: list[dict[str, Any]]
    message: str


class AddUserRequest(BaseModel):
    username: str = Field(
        ...,
        description="X username to store in Redis",
        min_length=1,
        max_length=50,
    )


class AddUserResponse(BaseModel):
    success: bool
    message: str
    username: str | None = None


class GetUsersResponse(BaseModel):
    success: bool
    message: str
    users: list[dict[str, Any]]
    total_count: int
