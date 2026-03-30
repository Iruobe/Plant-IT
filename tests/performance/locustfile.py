"""
Load and stress testing with Locust.

This file defines user behavior for load testing the API.
Tests can simulate 50+ concurrent users hitting the API.

Run with: locust -f tests/performance/locustfile.py --host=https://your-api-url

Test scenarios:
1. Normal load (10-50 users)
2. Stress test (100+ users)
3. Spike test (sudden traffic burst)
"""

from locust import HttpUser, task, between, tag
import json
import random


class PlantITUser(HttpUser):
    """
    Simulates a Plant IT user's behavior.
    
    Each user:
    - Has their own auth token (mocked)
    - Creates plants, views them, manages tasks
    - Occasionally uses AI features
    """
    
    # Wait 1-3 seconds between tasks (realistic user behavior)
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        Called when a user starts.
        Sets up authentication and creates initial data.
        """
        # In real tests, you'd get a real Firebase token
        # For load testing, use a test token or mock auth
        self.headers = {
            "Authorization": "Bearer test_load_test_token",
            "Content-Type": "application/json"
        }
        self.plant_ids = []
        self.task_ids = []
    
    # ============================================================
    # HIGH FREQUENCY TASKS (60% of traffic)
    # ============================================================
    
    @task(10)
    @tag("read", "plants")
    def list_plants(self):
        """
        List all plants.
        Most common operation - users check their plants frequently.
        """
        with self.client.get(
            "/api/v1/plants/",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                plants = response.json()
                # Store plant IDs for other operations
                self.plant_ids = [p["plant_id"] for p in plants]
                response.success()
            elif response.status_code == 401:
                response.failure("Auth failed")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(8)
    @tag("read", "care-plans")
    def get_today_tasks(self):
        """
        Get today's care tasks.
        Second most common - users check tasks daily.
        """
        with self.client.get(
            "/api/v1/care-plans/today",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                tasks = response.json()
                self.task_ids = [t["task_id"] for t in tasks]
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
    
    @task(5)
    @tag("read", "plants")
    def get_single_plant(self):
        """
        View a specific plant's details.
        """
        if not self.plant_ids:
            return
        
        plant_id = random.choice(self.plant_ids)
        with self.client.get(
            f"/api/v1/plants/{plant_id}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Plant may have been deleted
                self.plant_ids.remove(plant_id)
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
    
    # ============================================================
    # MEDIUM FREQUENCY TASKS (30% of traffic)
    # ============================================================
    
    @task(3)
    @tag("write", "care-plans")
    def complete_task(self):
        """
        Mark a task as complete.
        Users do this several times per day.
        """
        if not self.task_ids:
            return
        
        task_id = random.choice(self.task_ids)
        with self.client.post(
            f"/api/v1/care-plans/complete/{task_id}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
    
    @task(2)
    @tag("write", "plants")
    def create_plant(self):
        """
        Create a new plant.
        Less frequent - users add plants occasionally.
        """
        plant_data = {
            "name": f"Load Test Plant {random.randint(1, 10000)}",
            "species": "Test Species",
            "goal": random.choice(["decorative", "food", "medicinal"]),
            "location": "Test Location"
        }
        
        with self.client.post(
            "/api/v1/plants/",
            headers=self.headers,
            json=plant_data,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                plant = response.json()
                self.plant_ids.append(plant["plant_id"])
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
    
    @task(1)
    @tag("read", "usage")
    def check_usage(self):
        """
        Check API usage limits.
        Occasional check by users.
        """
        with self.client.get(
            "/api/v1/usage/",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
    
    # ============================================================
    # LOW FREQUENCY TASKS (10% of traffic - AI operations)
    # ============================================================
    
    @task(1)
    @tag("ai", "expensive")
    def chat_with_assistant(self):
        """
        Send a chat message to AI.
        Lower frequency due to rate limits and cost.
        """
        messages = [
            "How do I care for my monstera?",
            "Why are my plant's leaves yellow?",
            "When should I repot my plant?",
            "How often should I water succulents?",
        ]
        
        with self.client.post(
            "/api/v1/ai/chat",
            headers=self.headers,
            json={
                "message": random.choice(messages),
                "session_id": f"load_test_{self.environment.runner.user_count}"
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # Rate limited - expected behavior
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
    
    # ============================================================
    # CLEANUP
    # ============================================================
    
    @task(1)
    @tag("write", "plants", "cleanup")
    def delete_plant(self):
        """
        Delete a plant.
        Keeps test data from accumulating.
        """
        if len(self.plant_ids) > 5:  # Keep some plants
            plant_id = self.plant_ids.pop()
            with self.client.delete(
                f"/api/v1/plants/{plant_id}",
                headers=self.headers,
                catch_response=True
            ) as response:
                if response.status_code in [200, 404]:
                    response.success()
                else:
                    response.failure(f"Status: {response.status_code}")


class HealthCheckUser(HttpUser):
    """
    Simple user that only checks health endpoint.
    Used to establish baseline performance.
    """
    
    wait_time = between(0.5, 1)
    weight = 1  # Lower weight = fewer of these users
    
    @task
    def health_check(self):
        """Check API health endpoint."""
        self.client.get("/health")