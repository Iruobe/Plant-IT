from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import date
from typing import Optional
import uuid
import json

from app.core.auth import get_current_user
from app.repositories import care_plans as care_plans_repo
from app.repositories.dynamodb import get_plants_table
from app.services.bedrock import get_bedrock_client

router = APIRouter()


class TaskCompletion(BaseModel):
    completed_date: Optional[str] = None


class CarePlanTask(BaseModel):
    task_id: str
    plant_id: str
    plant_name: str
    task_type: str
    title: str
    description: str
    frequency: str
    times_per_week: int
    priority: str
    completed: bool = False
    completions_this_week: int = 0
    remaining_this_week: Optional[int] = None


@router.post("/generate/{plant_id}")
async def generate_care_plan(
    plant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Generate AI care plan for a plant based on its health analysis."""
    user_id = current_user["uid"]
    
    # Get plant details
    table = get_plants_table()
    response = table.get_item(Key={'user_id': user_id, 'plant_id': plant_id})
    plant = response.get('Item')
    
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    # Delete existing care plans for this plant
    care_plans_repo.delete_care_plans_for_plant(user_id, plant_id)
    
    # Generate care plan using AI
    prompt = f"""Based on the following plant information, generate a specific care plan with actionable daily and weekly tasks.

Plant Details:
- Name: {plant.get('name', 'Unknown')}
- Species: {plant.get('species', 'Unknown')}
- Health Status: {plant.get('health_status', 'Unknown')}
- Health Score: {plant.get('health_score', 'Unknown')}%
- Location: {plant.get('location', 'Unknown')}
- Goal: {plant.get('goal', 'General care')}

Generate 3-5 specific care tasks. For each task, provide:
1. task_type: one of [water, fertilize, sunlight, rotate, prune, mist, inspect, repot]
2. title: short action title (e.g., "Water your plant")
3. description: specific instructions with quantities (e.g., "Apply 200ml of room temperature water at the base")
4. frequency: one of [daily, weekly, 2x_weekly, 3x_weekly]
5. times_per_week: number (7 for daily, 1 for weekly, 2 for 2x_weekly, 3 for 3x_weekly)
6. priority: one of [high, medium, low]

Consider the plant's current health score when recommending care intensity.

Respond ONLY with a JSON array of tasks, no other text:
[
  {{"task_type": "water", "title": "...", "description": "...", "frequency": "daily", "times_per_week": 7, "priority": "high"}},
  ...
]
"""

    try:
        bedrock = get_bedrock_client()
        response = bedrock.invoke_model(
            modelId="anthropic.claude-sonnet-4-20250514",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        ai_response = result['content'][0]['text']
        
        # Parse AI response
        # Clean up response if needed
        ai_response = ai_response.strip()
        if ai_response.startswith("```json"):
            ai_response = ai_response[7:]
        if ai_response.startswith("```"):
            ai_response = ai_response[3:]
        if ai_response.endswith("```"):
            ai_response = ai_response[:-3]
        
        tasks_data = json.loads(ai_response.strip())
        
        # Create care plan tasks
        created_tasks = []
        for task_data in tasks_data:
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            task = care_plans_repo.create_care_plan_task(
                user_id=user_id,
                task_id=task_id,
                plant_id=plant_id,
                plant_name=plant.get('name', 'Unknown'),
                task_type=task_data.get('task_type', 'other'),
                title=task_data.get('title', ''),
                description=task_data.get('description', ''),
                frequency=task_data.get('frequency', 'daily'),
                times_per_week=task_data.get('times_per_week', 7),
                priority=task_data.get('priority', 'medium')
            )
            created_tasks.append(task)
        
        return {
            "message": f"Generated {len(created_tasks)} care tasks",
            "tasks": created_tasks
        }
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate care plan: {str(e)}")


@router.get("/today", response_model=list[CarePlanTask])
async def get_today_tasks(
    current_user: dict = Depends(get_current_user)
):
    """Get all pending tasks for today."""
    user_id = current_user["uid"]
    tasks = care_plans_repo.get_pending_tasks_for_today(user_id)
    return tasks


@router.get("/plant/{plant_id}")
async def get_plant_care_plan(
    plant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get care plan for a specific plant."""
    user_id = current_user["uid"]
    tasks = care_plans_repo.get_care_plans_for_plant(user_id, plant_id)
    return tasks


@router.post("/complete/{task_id}")
async def complete_task(
    task_id: str,
    body: TaskCompletion = TaskCompletion(),
    current_user: dict = Depends(get_current_user)
):
    """Mark a task as completed."""
    user_id = current_user["uid"]
    
    completion = care_plans_repo.mark_task_complete(
        user_id=user_id,
        task_id=task_id,
        completed_date=body.completed_date
    )
    
    return {"message": "Task completed", "completion": completion}


@router.delete("/complete/{task_id}")
async def uncomplete_task(
    task_id: str,
    completed_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Unmark a task as completed."""
    user_id = current_user["uid"]
    
    care_plans_repo.unmark_task_complete(
        user_id=user_id,
        task_id=task_id,
        completed_date=completed_date
    )
    
    return {"message": "Task completion removed"}


@router.get("/history")
async def get_completion_history(
    week: Optional[int] = None,
    year: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get task completion history for a week."""
    user_id = current_user["uid"]
    
    completions = care_plans_repo.get_completions_for_week(user_id, week, year)
    return completions