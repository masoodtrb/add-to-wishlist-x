import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import redis

from celery_app import celery_app
from config import settings
from x_api_client import x_api_client

logger = logging.getLogger(__name__)

# Create synchronous Redis client for Celery tasks
sync_redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
    decode_responses=True,
)


@celery_app.task(bind=True, name="tasks.add_user_to_queue")
def add_user_to_queue(self, username: str, list_id: str = None) -> dict[str, Any]:
    """
    Add a user to the processing queue
    """
    try:
        task_list_id = list_id or settings.X_LIST_ID
        task_username = username.strip().lower()

        logger.info(
            f"Celery task: Adding user '{task_username}' to queue for list {task_list_id}",  # noqa: E501
        )

        # Check if user is already in queue
        queue_key = f"user_queue:{task_list_id}"

        # Use synchronous Redis operations
        existing_users = sync_redis_client.lrange(queue_key, 0, -1)

        if any(
            json.loads(user)["username"] == task_username for user in existing_users
        ):
            logger.info(f"User '{task_username}' is already in the queue")
            return {
                "success": False,
                "message": f"User '{task_username}' is already in the queue",
                "task_id": self.request.id,
            }

        # Add user to queue
        user_data = {
            "username": task_username,
            "list_id": task_list_id,
            "added_at": datetime.utcnow().isoformat(),
            "task_id": self.request.id,
            "status": "queued",
        }

        sync_redis_client.lpush(queue_key, json.dumps(user_data))

        # Set expiration for queue items (24 hours)
        sync_redis_client.expire(queue_key, 86400)

        logger.info(
            f"Successfully added user '{task_username}' to queue for list {task_list_id}"
        )

        return {
            "success": True,
            "message": f"User '{task_username}' added to queue",
            "task_id": self.request.id,
            "queue_position": sync_redis_client.llen(queue_key),
        }

    except Exception as e:
        logger.error(f"Error adding user to queue: {str(e)}")
        return {
            "success": False,
            "message": f"Error adding user to queue: {str(e)}",
            "task_id": self.request.id,
        }


@celery_app.task(bind=True, name="tasks.process_user_queue")
def process_user_queue(self, list_id: str = None) -> dict[str, Any]:
    """
    Process the user queue every 15 minutes
    """
    try:
        task_list_id = list_id or settings.X_LIST_ID
        queue_key = f"user_queue:{task_list_id}"

        logger.info(f"Celery task: Processing user queue for list {task_list_id}")

        # Get the next user from queue (FIFO)
        user_data_json = sync_redis_client.rpop(queue_key)

        if not user_data_json:
            logger.info("No users in queue to process")
            return {
                "success": True,
                "message": "No users in queue",
                "processed_count": 0,
            }

        user_data = json.loads(user_data_json)
        username = user_data["username"]

        logger.info(f"Processing user '{username}' from queue")

        # Get user ID from X API
        user_info = asyncio.run(x_api_client.get_user_by_username(username))

        if not user_info:
            logger.error(f"Could not find user '{username}' on X")
            user_data["status"] = "failed"
            user_data["error"] = "User not found on X"
            user_data["completed_at"] = datetime.utcnow().isoformat()
        else:
            user_id = user_info["id"]
            logger.info(f"Found user ID {user_id} for username '{username}'")

            # Add user to X list
            result = x_api_client.add_user_to_list(task_list_id, user_id)

            if result is True:
                logger.info(
                    f"Successfully added user '{username}' to X list {task_list_id}",
                )
                user_data["status"] = "completed"
                user_data["user_id"] = user_id
                user_data["completed_at"] = datetime.utcnow().isoformat()
            elif result == "RATE_LIMIT":
                # Rate limit hit - retry later
                if self.request.retries < 3:  # Max 3 retries
                    logger.warning(
                        f"Rate limit hit for user '{username}', retrying in 15 minutes"
                    )
                    user_data["status"] = "retry"
                    user_data["retry_count"] = self.request.retries + 1
                    user_data["retry_at"] = (
                        datetime.utcnow() + timedelta(minutes=15)
                    ).isoformat()

                    # Put user back in queue for retry
                    sync_redis_client.lpush(queue_key, json.dumps(user_data))

                    return {
                        "success": False,
                        "message": f"Rate limit hit for '{username}', retrying in 15 minutes",
                        "processed_count": 0,
                        "retry_count": self.request.retries + 1,
                    }
                else:
                    logger.error(
                        f"Failed to add user '{username}' to X list after 3 retries"
                    )
                    user_data["status"] = "failed"
                    user_data["error"] = "Failed to add to X list after 3 retries"
                    user_data["user_id"] = user_id
                    user_data["completed_at"] = datetime.utcnow().isoformat()
            else:
                # Other error
                logger.error(f"Failed to add user '{username}' to X list")
                user_data["status"] = "failed"
                user_data["error"] = "Failed to add to X list"
                user_data["user_id"] = user_id
                user_data["completed_at"] = datetime.utcnow().isoformat()

        # Store completed job
        completed_key = f"completed_jobs:{task_list_id}"
        sync_redis_client.lpush(completed_key, json.dumps(user_data))
        sync_redis_client.expire(completed_key, 86400)  # 24 hours

        logger.info(f"Successfully processed user '{username}' from queue")

        return {
            "success": True,
            "message": f"Successfully processed '{username}' from queue",
            "processed_count": 1,
            "username": username,
        }

    except Exception as e:
        logger.error(f"Error processing user queue: {str(e)}")
        return {
            "success": False,
            "message": f"Error processing queue: {str(e)}",
            "processed_count": 0,
        }


@celery_app.task(bind=True, name="tasks.cleanup_expired_jobs")
def cleanup_expired_jobs(self) -> dict[str, Any]:
    """
    Clean up expired jobs and old data
    """
    try:
        cleaned_count = 0

        # Clean up old completed jobs (older than 7 days)
        for list_id in [settings.X_LIST_ID]:
            completed_key = f"completed_jobs:{list_id}"
            jobs = sync_redis_client.lrange(completed_key, 0, -1)

            cutoff_date = datetime.utcnow() - timedelta(days=7)

            for job_json in jobs:
                job_data = json.loads(job_json)
                completed_at = datetime.fromisoformat(
                    job_data.get("completed_at", "1970-01-01"),
                )

                if completed_at < cutoff_date:
                    sync_redis_client.lrem(completed_key, 1, job_json)
                    cleaned_count += 1

        logger.info(f"Cleaned up {cleaned_count} expired jobs")

        return {
            "success": True,
            "message": f"Cleaned up {cleaned_count} expired jobs",
            "cleaned_count": cleaned_count,
        }

    except Exception as e:
        logger.error(f"Error cleaning up expired jobs: {str(e)}")

        return {
            "success": False,
            "message": f"Error cleaning up jobs: {str(e)}",
            "cleaned_count": 0,
        }


@celery_app.task(bind=True, name="tasks.get_queue_status")
def get_queue_status(self, list_id: str = None) -> dict[str, Any]:
    """
    Get current queue status
    """
    try:
        task_list_id = list_id or settings.X_LIST_ID
        queue_key = f"user_queue:{task_list_id}"
        completed_key = f"completed_jobs:{task_list_id}"

        # Get queue length
        queue_length = sync_redis_client.llen(queue_key)

        # Get recent completed jobs
        completed_jobs = sync_redis_client.lrange(
            completed_key,
            0,
            9,
        )  # Last 10

        return {
            "success": True,
            "queue_length": queue_length,
            "completed_jobs": [json.loads(job) for job in completed_jobs],
            "list_id": task_list_id,
        }

    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        return {"success": False, "message": f"Error getting queue status: {str(e)}"}


async def get_celery_task_status(task_id: str) -> dict[str, Any]:
    """
    Get the status of a Celery task and return data compatible with QueueStatusResponse
    """
    try:
        # Get the AsyncResult
        result = celery_app.AsyncResult(task_id)

        # Get queue status for the list
        list_id = settings.X_LIST_ID
        queue_key = f"user_queue:{list_id}"
        completed_key = f"completed_jobs:{list_id}"

        # Get queue length
        queue_length = sync_redis_client.llen(queue_key)

        # Get recent completed jobs
        completed_jobs = sync_redis_client.lrange(
            completed_key,
            0,
            9,
        )  # Last 10

        # Parse completed jobs
        parsed_completed_jobs = []
        for job in completed_jobs:
            try:
                parsed_completed_jobs.append(json.loads(job))
            except json.JSONDecodeError:
                continue

        # Determine task status
        if result.state == "PENDING":
            status_message = "Task is waiting to be processed"
        elif result.state == "PROGRESS":
            status_message = "Task is currently being processed"
        elif result.state == "SUCCESS":
            status_message = "Task completed successfully"
        elif result.state == "FAILURE":
            status_message = f"Task failed: {result.info}"
        else:
            status_message = f"Task status: {result.state}"

        return {
            "success": True,
            "queue_length": queue_length,
            "completed_jobs": parsed_completed_jobs,
            "list_id": list_id,
            "message": status_message,
            "task_state": result.state,
            "task_result": result.result if result.ready() else None,
        }
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        return {
            "success": False,
            "queue_length": 0,
            "completed_jobs": [],
            "list_id": settings.X_LIST_ID,
            "message": f"Error retrieving task status: {str(e)}",
        }


async def get_all_tasks_status(list_id: str = None) -> dict[str, Any]:
    """
    Get the status of all active Celery tasks and system status
    """
    try:
        # Get queue status for the list
        list_id = list_id or settings.X_LIST_ID
        queue_key = f"user_queue:{list_id}"
        completed_key = f"completed_jobs:{list_id}"

        # Get queue length
        queue_length = sync_redis_client.llen(queue_key)

        # Get all users in queue
        queue_users = sync_redis_client.lrange(queue_key, 0, -1)
        parsed_queue_users = []
        for user in queue_users:
            try:
                parsed_queue_users.append(json.loads(user))
            except json.JSONDecodeError:
                continue

        # Get recent completed jobs
        completed_jobs = sync_redis_client.lrange(
            completed_key,
            0,
            19,
        )  # Last 20

        # Parse completed jobs
        parsed_completed_jobs = []
        for job in completed_jobs:
            try:
                parsed_completed_jobs.append(json.loads(job))
            except json.JSONDecodeError:
                continue

        # Get system status
        try:
            sync_redis_client.ping()
            redis_connected = True
        except Exception:
            redis_connected = False
        x_api_configured = bool(settings.X_BEARER_TOKEN)

        return {
            "success": True,
            "system_status": {
                "redis_connected": redis_connected,
                "x_api_configured": x_api_configured,
                "list_id": list_id,
            },
            "queue_status": {
                "queue_length": queue_length,
                "queue_users": parsed_queue_users,
            },
            "completed_jobs": parsed_completed_jobs,
            "message": "All tasks status retrieved successfully",
        }
    except Exception as e:
        logger.error(f"Error getting all tasks status: {str(e)}")
        return {
            "success": False,
            "system_status": {
                "redis_connected": False,
                "x_api_configured": False,
                "list_id": settings.X_LIST_ID,
            },
            "queue_status": {
                "queue_length": 0,
                "queue_users": [],
            },
            "completed_jobs": [],
            "message": f"Error retrieving all tasks status: {str(e)}",
        }
