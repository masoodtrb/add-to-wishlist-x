import datetime
import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from audit_logger import AuditEventType, AuditLogLevel, audit_logger
from config import settings
from file_storage import file_storage
from models import (
    AddUserRequest,
    AddUserResponse,
    AllTasksStatusResponse,
    GetUsersResponse,
    HealthResponse,
    QueueStatusResponse,
    QueueUserRequest,
    QueueUserResponse,
)
from redis_client import redis_client
from tasks import add_user_to_queue, get_all_tasks_status, get_celery_task_status

app = FastAPI()  # <- the ASGI entrypoint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="X List Management API - Queue Only",
    description=(
        "API for managing X (Twitter) lists with queue-based processing to comply "
        "with free plan rate limits (15 minutes per username)"
    ),
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint"""
    request_id = str(uuid.uuid4())

    try:
        redis_connected = await redis_client.health_check()
        x_api_configured = bool(settings.X_BEARER_TOKEN)

        # Log health check
        await audit_logger.log_event(
            event_type=AuditEventType.HEALTH_CHECK,
            level=AuditLogLevel.INFO,
            message="Health check performed",
            request_id=request_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=redis_connected and x_api_configured,
        )

        return HealthResponse(
            status="healthy" if redis_connected and x_api_configured else "unhealthy",
            redis_connected=redis_connected,
            x_api_configured=x_api_configured,
        )
    except Exception as e:
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=AuditLogLevel.ERROR,
            message=f"Health check failed: {str(e)}",
            request_id=request_id,
            ip_address=request.client.host if request.client else None,
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail="Health check failed")


@app.post("/queue-user", response_model=QueueUserResponse)
async def queue_user_for_addition(request: QueueUserRequest, http_request: Request):
    """
    Add a user to the processing queue (PRIMARY METHOD)

    Due to X free plan limitations (15-minute rate limit per username),
    all user additions must go through this queue system.

    Users will be processed every 15 minutes by the Celery worker.
    This is the ONLY way to add users to X lists with the free plan.
    """
    request_id = str(uuid.uuid4())
    username = request.username.strip().lower()
    list_id = request.list_id or settings.X_LIST_ID

    # Log queue attempt
    await audit_logger.log_event(
        event_type=AuditEventType.USER_ADDED_TO_QUEUE,
        level=AuditLogLevel.INFO,
        message=f"Attempting to queue user '{username}' for processing",
        username=username,
        list_id=list_id,
        request_id=request_id,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent"),
    )

    try:
        # Check if user is already rate limited
        if await redis_client.is_rate_limited(username):
            next_available = datetime.datetime.now() + datetime.timedelta(
                seconds=settings.RATE_LIMIT_SECONDS,
            )

            # Log rate limit hit
            await audit_logger.log_event(
                event_type=AuditEventType.RATE_LIMIT_CHECK,
                level=AuditLogLevel.WARNING,
                message=f"Rate limit hit for user '{username}' during queue",
                username=username,
                request_id=request_id,
                success=False,
                error_message="User is rate limited",
            )

            return QueueUserResponse(
                success=False,
                message=(
                    f"User '{username}' is currently rate limited. "
                    f"Next available: {next_available}"
                ),
                task_id=None,
                queue_position=None,
            )

        # Add user to queue
        task = add_user_to_queue.delay(username, list_id)

        # Log successful queue
        await audit_logger.log_event(
            event_type=AuditEventType.USER_ADDED_TO_QUEUE,
            level=AuditLogLevel.INFO,
            message=f"Successfully queued user '{username}' for processing",
            username=username,
            list_id=list_id,
            task_id=task.id,
            request_id=request_id,
            success=True,
        )

        return QueueUserResponse(
            success=True,
            message=f"User '{username}' added to processing queue",
            task_id=task.id,
            queue_position=None,  # Will be updated by the task
        )

    except Exception as e:
        logger.error(f"Error queuing user {request.username}: {str(e)}")

        # Log system error
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=AuditLogLevel.ERROR,
            message=f"System error while queuing user '{username}'",
            username=username,
            request_id=request_id,
            success=False,
            error_message=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error. Please try again later.",
        )


@app.get("/queue-status", response_model=QueueStatusResponse)
async def get_queue_status_endpoint(task_id: str):
    """
    Get current queue status and recent completed jobs
    """
    try:
        task = await get_celery_task_status(task_id)

        return QueueStatusResponse(**task)
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving queue status",
        )


@app.get("/all-tasks-status", response_model=AllTasksStatusResponse)
async def get_all_tasks_status_endpoint(request: Request, list_id: str = None):
    """
    Get comprehensive status of all tasks, system health, and queue information
    """
    request_id = str(uuid.uuid4())

    try:
        # Log the request
        await audit_logger.log_event(
            event_type=AuditEventType.HEALTH_CHECK,
            level=AuditLogLevel.INFO,
            message="All tasks status requested",
            request_id=request_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Get all tasks status
        status_data = await get_all_tasks_status(list_id)

        return AllTasksStatusResponse(**status_data)
    except Exception as e:
        logger.error(f"Error getting all tasks status: {str(e)}")

        # Log error
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=AuditLogLevel.ERROR,
            message=f"Error getting all tasks status: {str(e)}",
            request_id=request_id,
            ip_address=request.client.host if request.client else None,
            success=False,
            error_message=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Error retrieving all tasks status",
        )


@app.post("/add-user", response_model=AddUserResponse)
async def add_user(request: AddUserRequest, http_request: Request):
    """
    Store a username in Redis

    This endpoint simply stores the provided username in Redis with a timestamp.
    No processing or API calls are made - just storage.
    """
    request_id = str(uuid.uuid4())
    username = request.username.strip().lower()

    # Log the request
    await audit_logger.log_event(
        event_type=AuditEventType.USER_ADDED_TO_QUEUE,  # Reusing existing event type
        level=AuditLogLevel.INFO,
        message=f"Attempting to store username '{username}' in Redis",
        username=username,
        request_id=request_id,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent"),
    )

    try:
        # Store username in file storage
        file_storage.store_username(username)

        # Log successful storage
        await audit_logger.log_event(
            event_type=AuditEventType.USER_ADDED_TO_QUEUE,
            level=AuditLogLevel.INFO,
            message=f"Successfully stored username '{username}' in file storage",
            username=username,
            request_id=request_id,
            success=True,
        )

        return AddUserResponse(
            success=True,
            message=f"Username '{username}' stored successfully in file storage",
            username=username,
        )

    except Exception as e:
        logger.error(f"Error storing username {username}: {str(e)}")

        # Log system error
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=AuditLogLevel.ERROR,
            message=f"System error while storing username '{username}'",
            username=username,
            request_id=request_id,
            success=False,
            error_message=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error. Please try again later.",
        )


@app.get("/get-users", response_model=GetUsersResponse)
async def get_users(http_request: Request):
    """
    Get all usernames stored in Redis

    This endpoint retrieves all usernames that have been stored in Redis
    with their timestamps.
    """
    request_id = str(uuid.uuid4())

    # Log the request
    await audit_logger.log_event(
        event_type=AuditEventType.HEALTH_CHECK,  # Reusing existing event type
        level=AuditLogLevel.INFO,
        message="Request to get all stored usernames",
        request_id=request_id,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent"),
    )

    try:
        # Get all stored usernames from file storage
        users = file_storage.get_all_stored_usernames()

        # Log successful retrieval
        await audit_logger.log_event(
            event_type=AuditEventType.HEALTH_CHECK,
            level=AuditLogLevel.INFO,
            message=f"Successfully retrieved {len(users)} stored usernames",
            request_id=request_id,
            success=True,
        )

        return GetUsersResponse(
            success=True,
            message=f"Retrieved {len(users)} stored usernames",
            users=users,
            total_count=len(users),
        )

    except Exception as e:
        logger.error(f"Error retrieving stored usernames: {str(e)}")

        # Log system error
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=AuditLogLevel.ERROR,
            message=f"System error while retrieving stored usernames: {str(e)}",
            request_id=request_id,
            success=False,
            error_message=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error. Please try again later.",
        )


@app.get("/file-storage-stats", response_model=dict)
async def get_file_storage_stats(http_request: Request):
    """
    Get statistics about file storage
    """
    try:
        # Get count of stored usernames
        count = file_storage.get_stored_usernames_count()

        # Get backup data
        backup_data = file_storage.backup_stored_usernames()

        # Check file storage health
        file_healthy = file_storage.health_check()

        return {
            "success": True,
            "stored_usernames_count": count,
            "file_storage_healthy": file_healthy,
            "backup_data": backup_data,
            "message": f"Found {count} stored usernames",
        }

    except Exception as e:
        logger.error(f"Error getting file storage stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error. Please try again later.",
        )


# 13d05d17-4aad-4520-b459-3d7dc9a1a648
