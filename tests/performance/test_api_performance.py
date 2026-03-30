"""
API performance tests with response time assertions.

These tests verify that endpoints respond within acceptable time limits.
Run with: pytest tests/performance/ -v

Thresholds based on:
- 50 concurrent users target
- P95 response times
"""

import pytest
import time
from statistics import mean, stdev


class TestResponseTimes:
    """Tests that verify API response times meet requirements."""
    
    @pytest.fixture
    def time_request(self, authenticated_client):
        """
        Factory that times requests and returns response + duration.
        
        Usage:
            response, duration_ms = time_request("GET", "/api/v1/plants/")
        """
        def _time_request(method, url, **kwargs):
            start = time.perf_counter()
            
            if method == "GET":
                response = authenticated_client.get(url, **kwargs)
            elif method == "POST":
                response = authenticated_client.post(url, **kwargs)
            elif method == "DELETE":
                response = authenticated_client.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            duration_ms = (time.perf_counter() - start) * 1000
            return response, duration_ms
        
        return _time_request
    
    def test_list_plants_response_time(self, time_request, response_time_threshold, create_test_plant):
        """
        List plants should respond within 300ms.
        
        This is a frequently called endpoint that should be fast.
        """
        # Create some plants
        for i in range(5):
            create_test_plant({"name": f"Plant {i}", "goal": "decorative"})
        
        # Time multiple requests
        durations = []
        for _ in range(10):
            response, duration = time_request("GET", "/api/v1/plants/")
            assert response.status_code == 200
            durations.append(duration)
        
        avg_duration = mean(durations)
        max_duration = max(durations)
        
        print(f"\nList plants: avg={avg_duration:.1f}ms, max={max_duration:.1f}ms")
        
        assert avg_duration < response_time_threshold["list_plants"], \
            f"Average response time {avg_duration:.1f}ms exceeds threshold"
    
    def test_get_plant_response_time(self, time_request, response_time_threshold, create_test_plant):
        """
        Get single plant should respond within 200ms.
        
        Single item lookup should be very fast.
        """
        plant = create_test_plant()
        
        durations = []
        for _ in range(10):
            response, duration = time_request("GET", f"/api/v1/plants/{plant['plant_id']}")
            assert response.status_code == 200
            durations.append(duration)
        
        avg_duration = mean(durations)
        
        print(f"\nGet plant: avg={avg_duration:.1f}ms")
        
        assert avg_duration < response_time_threshold["get_plant"]
    
    def test_today_tasks_response_time(self, time_request, response_time_threshold, create_test_care_task):
        """
        Today's tasks should respond within 400ms.
        
        Critical endpoint - users check this frequently.
        """
        # Create some tasks
        for i in range(10):
            create_test_care_task(plant_name=f"Plant {i}")
        
        durations = []
        for _ in range(10):
            response, duration = time_request("GET", "/api/v1/care-plans/today")
            assert response.status_code == 200
            durations.append(duration)
        
        avg_duration = mean(durations)
        
        print(f"\nToday tasks: avg={avg_duration:.1f}ms")
        
        assert avg_duration < response_time_threshold["today_tasks"]
    
    def test_complete_task_response_time(self, time_request, response_time_threshold, create_test_care_task):
        """
        Completing a task should respond within 300ms.
        
        Write operation but should still be fast.
        """
        tasks = [create_test_care_task(plant_name=f"Plant {i}") for i in range(5)]
        
        durations = []
        for task in tasks:
            response, duration = time_request(
                "POST", 
                f"/api/v1/care-plans/complete/{task['task_id']}"
            )
            assert response.status_code == 200
            durations.append(duration)
        
        avg_duration = mean(durations)
        
        print(f"\nComplete task: avg={avg_duration:.1f}ms")
        
        assert avg_duration < response_time_threshold["complete_task"]
    
    def test_create_plant_response_time(self, time_request, response_time_threshold):
        """
        Creating a plant should respond within 500ms.
        
        Write operations are slower but should still be reasonable.
        """
        durations = []
        for i in range(5):
            response, duration = time_request(
                "POST",
                "/api/v1/plants/",
                json={"name": f"Perf Test Plant {i}", "goal": "decorative"}
            )
            assert response.status_code == 201
            durations.append(duration)
        
        avg_duration = mean(durations)
        
        print(f"\nCreate plant: avg={avg_duration:.1f}ms")
        
        assert avg_duration < response_time_threshold["create_plant"]


class TestConcurrentRequests:
    """Tests that verify API handles concurrent requests correctly."""
    
    def test_concurrent_list_plants(self, authenticated_client, create_test_plant):
        """
        Multiple concurrent list requests should all succeed.
        
        Simulates multiple users viewing their plants simultaneously.
        """
        import concurrent.futures
        
        # Create test data
        for i in range(3):
            create_test_plant({"name": f"Plant {i}", "goal": "decorative"})
        
        def make_request():
            response = authenticated_client.get("/api/v1/plants/")
            return response.status_code
        
        # Run 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(status == 200 for status in results), \
            f"Some requests failed: {results}"
    
    def test_concurrent_task_completions(self, authenticated_client, create_test_care_task):
        """
        Multiple concurrent task completions should all succeed.
        
        Simulates multiple users completing tasks at the same time.
        """
        import concurrent.futures
        
        # Create tasks
        tasks = [create_test_care_task(plant_name=f"Plant {i}") for i in range(10)]
        
        def complete_task(task):
            response = authenticated_client.post(
                f"/api/v1/care-plans/complete/{task['task_id']}"
            )
            return response.status_code
        
        # Complete all tasks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(complete_task, task) for task in tasks]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(status == 200 for status in results)
        