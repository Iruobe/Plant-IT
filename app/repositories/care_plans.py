import boto3
from datetime import datetime, date
from typing import Optional
from app.core.config import settings

_dynamodb = None
_care_plans_table = None
_completions_table = None


def get_dynamodb():
    """Get cached DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        if settings.DYNAMODB_ENDPOINT_URL and settings.ENVIRONMENT == "development":
            _dynamodb = boto3.resource(
                "dynamodb",
                region_name=settings.AWS_REGION,
                endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
                aws_access_key_id="dummyAccount",
                aws_secret_access_key="dummyAccount",
            )
        else:
            _dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    return _dynamodb


def get_care_plans_table():
    """Get cached care plans table."""
    global _care_plans_table
    if _care_plans_table is None:
        db = get_dynamodb()
        _care_plans_table = db.Table(settings.CARE_PLANS_TABLE_NAME)
    return _care_plans_table


def get_completions_table():
    """Get cached task completions table."""
    global _completions_table
    if _completions_table is None:
        db = get_dynamodb()
        _completions_table = db.Table(settings.TASK_COMPLETIONS_TABLE_NAME)
    return _completions_table


def get_week_number(d: date = None) -> tuple[int, int]:
    """Get ISO week number and year."""
    if d is None:
        d = date.today()
    iso_cal = d.isocalendar()
    return iso_cal[1], iso_cal[0]  # week_number, year


# Care Plans CRUD
def create_care_plan_task(
    user_id: str,
    task_id: str,
    plant_id: str,
    plant_name: str,
    task_type: str,
    title: str,
    description: str,
    frequency: str,
    times_per_week: int,
    priority: str = "medium",
) -> dict:
    """Create a new care plan task."""
    table = get_care_plans_table()

    item = {
        "user_id": user_id,
        "task_id": task_id,
        "plant_id": plant_id,
        "plant_name": plant_name,
        "task_type": task_type,
        "title": title,
        "description": description,
        "frequency": frequency,
        "times_per_week": times_per_week,
        "priority": priority,
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
    }

    table.put_item(Item=item)
    return item


def get_care_plans_for_user(user_id: str) -> list[dict]:
    """Get all active care plan tasks for a user."""
    table = get_care_plans_table()

    response = table.query(
        KeyConditionExpression="user_id = :uid",
        FilterExpression="active = :active",
        ExpressionAttributeValues={":uid": user_id, ":active": True},
    )

    return response.get("Items", [])


def get_care_plans_for_plant(user_id: str, plant_id: str) -> list[dict]:
    """Get all care plan tasks for a specific plant."""
    table = get_care_plans_table()

    response = table.query(
        KeyConditionExpression="user_id = :uid",
        FilterExpression="plant_id = :pid AND active = :active",
        ExpressionAttributeValues={":uid": user_id, ":pid": plant_id, ":active": True},
    )

    return response.get("Items", [])


def delete_care_plans_for_plant(user_id: str, plant_id: str):
    """Deactivate all care plans for a plant."""
    tasks = get_care_plans_for_plant(user_id, plant_id)
    table = get_care_plans_table()

    for task in tasks:
        table.update_item(
            Key={"user_id": user_id, "task_id": task["task_id"]},
            UpdateExpression="SET active = :active",
            ExpressionAttributeValues={":active": False},
        )


# Task Completions
def mark_task_complete(user_id: str, task_id: str, completed_date: str = None) -> dict:
    """Mark a task as completed for a specific date."""
    table = get_completions_table()

    if completed_date is None:
        completed_date = date.today().isoformat()

    week_num, year = get_week_number(date.fromisoformat(completed_date))
    completion_id = f"{task_id}#{completed_date}"

    item = {
        "user_id": user_id,
        "completion_id": completion_id,
        "task_id": task_id,
        "completed_date": completed_date,
        "week_number": week_num,
        "year": year,
        "completed_at": datetime.utcnow().isoformat(),
    }

    table.put_item(Item=item)
    return item


def unmark_task_complete(user_id: str, task_id: str, completed_date: str = None):
    """Remove completion record for a task."""
    table = get_completions_table()

    if completed_date is None:
        completed_date = date.today().isoformat()

    completion_id = f"{task_id}#{completed_date}"

    table.delete_item(Key={"user_id": user_id, "completion_id": completion_id})


def get_completions_for_week(
    user_id: str, week_number: int = None, year: int = None
) -> list[dict]:
    """Get all task completions for a specific week."""
    table = get_completions_table()

    if week_number is None or year is None:
        week_number, year = get_week_number()

    response = table.query(
        KeyConditionExpression="user_id = :uid",
        FilterExpression="week_number = :week AND #yr = :year",
        ExpressionAttributeValues={
            ":uid": user_id,
            ":week": week_number,
            ":year": year,
        },
        ExpressionAttributeNames={"#yr": "year"},  # year is a reserved word
    )

    return response.get("Items", [])


def get_completions_for_today(user_id: str) -> list[dict]:
    """Get all task completions for today."""
    table = get_completions_table()
    today = date.today().isoformat()

    response = table.query(
        KeyConditionExpression="user_id = :uid",
        FilterExpression="completed_date = :today",
        ExpressionAttributeValues={":uid": user_id, ":today": today},
    )

    return response.get("Items", [])


def get_tasks_for_today(user_id: str) -> list[dict]:
    """Get all tasks for today, including completed ones."""
    # Get all care plans
    all_tasks = get_care_plans_for_user(user_id)

    # Get completions for today and this week
    today_completions = get_completions_for_today(user_id)
    week_completions = get_completions_for_week(user_id)

    today_completed_ids = {c["task_id"] for c in today_completions}

    # Count completions per task this week
    week_completion_counts = {}
    for c in week_completions:
        tid = c["task_id"]
        week_completion_counts[tid] = week_completion_counts.get(tid, 0) + 1

    today_tasks = []

    for task in all_tasks:
        task_id = task["task_id"]
        frequency = task.get("frequency", "daily")
        times_per_week = task.get("times_per_week", 7)

        # Check if task should show today
        if frequency == "daily":
            # Daily tasks: always show, mark as completed if done today
            task["completed"] = task_id in today_completed_ids
            task["completions_this_week"] = week_completion_counts.get(task_id, 0)
            today_tasks.append(task)
        else:
            # Weekly tasks: show if not hit target for the week OR completed today
            completions = week_completion_counts.get(task_id, 0)
            is_completed_today = task_id in today_completed_ids

            if completions < times_per_week or is_completed_today:
                task["completed"] = is_completed_today
                task["completions_this_week"] = completions
                task["remaining_this_week"] = max(0, times_per_week - completions)
                today_tasks.append(task)

    # Sort by plant_name, then by completed status (incomplete first)
    today_tasks.sort(key=lambda t: (t.get("plant_name", ""), t.get("completed", False)))

    return today_tasks
