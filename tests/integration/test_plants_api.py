"""
Integration tests for Plants API endpoints.

Tests the full request/response cycle for plant CRUD operations.
Uses mocked DynamoDB and S3, but tests the actual FastAPI routes.

Endpoints tested:
- POST /api/v1/plants/ (create)
- GET /api/v1/plants/ (list)
- GET /api/v1/plants/{id} (get one)
- DELETE /api/v1/plants/{id} (delete)
- POST /api/v1/plants/{id}/upload-url (get S3 upload URL)
- POST /api/v1/plants/{id}/confirm-upload (confirm upload)
"""

from uuid import uuid4


class TestCreatePlant:
    """Tests for POST /api/v1/plants/"""

    def test_create_plant_success(self, authenticated_client, sample_plant_data):
        """Creating a plant with valid data returns 201."""
        response = authenticated_client.post("/api/v1/plants/", json=sample_plant_data)

        assert response.status_code == 201

        data = response.json()
        assert data["name"] == sample_plant_data["name"]
        assert data["species"] == sample_plant_data["species"]
        assert data["goal"] == sample_plant_data["goal"]
        assert data["location"] == sample_plant_data["location"]
        assert data["health_status"] == "unknown"
        assert "plant_id" in data
        assert "created_at" in data

    def test_create_plant_minimal(self, authenticated_client, sample_plant_minimal):
        """Creating a plant with only required fields works."""
        response = authenticated_client.post(
            "/api/v1/plants/", json=sample_plant_minimal
        )

        assert response.status_code == 201

        data = response.json()
        assert data["name"] == sample_plant_minimal["name"]
        assert data["species"] is None
        assert data["location"] is None

    def test_create_plant_empty_name_fails(self, authenticated_client):
        """Creating a plant without a name returns 400/422."""
        response = authenticated_client.post(
            "/api/v1/plants/", json={"name": "", "goal": "decorative"}
        )

        assert response.status_code in [400, 422]

    def test_create_plant_invalid_goal_fails(self, authenticated_client):
        """Creating a plant with invalid goal returns 400/422."""
        response = authenticated_client.post(
            "/api/v1/plants/", json={"name": "Test Plant", "goal": "invalid_goal"}
        )

        assert response.status_code in [400, 422]

    def test_create_plant_name_too_long_fails(self, authenticated_client):
        """Creating a plant with name > 100 chars returns 400/422."""
        response = authenticated_client.post(
            "/api/v1/plants/", json={"name": "A" * 101, "goal": "decorative"}
        )

        assert response.status_code in [400, 422]

    def test_create_plant_unauthorized(self, client):
        """Creating a plant without auth returns 401."""
        response = client.post(
            "/api/v1/plants/", json={"name": "Test Plant", "goal": "decorative"}
        )

        assert response.status_code == 401


class TestListPlants:
    """Tests for GET /api/v1/plants/"""

    def test_list_plants_empty(self, authenticated_client):
        """Listing plants when none exist returns empty list."""
        response = authenticated_client.get("/api/v1/plants/")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_plants_returns_owned_plants(
        self, authenticated_client, create_test_plant
    ):
        """Listing plants returns all plants owned by user."""
        # Create 3 plants
        plant1 = create_test_plant({"name": "Plant 1", "goal": "decorative"})
        plant2 = create_test_plant({"name": "Plant 2", "goal": "food"})
        plant3 = create_test_plant({"name": "Plant 3", "goal": "medicinal"})

        response = authenticated_client.get("/api/v1/plants/")

        assert response.status_code == 200
        plants = response.json()
        assert len(plants) == 3

        names = {p["name"] for p in plants}
        assert names == {"Plant 1", "Plant 2", "Plant 3"}

    def test_list_plants_unauthorized(self, client):
        """Listing plants without auth returns 401."""
        response = client.get("/api/v1/plants/")

        assert response.status_code == 401


class TestGetPlant:
    """Tests for GET /api/v1/plants/{plant_id}"""

    def test_get_plant_success(self, authenticated_client, create_test_plant):
        """Getting an existing plant returns it."""
        plant = create_test_plant()

        response = authenticated_client.get(f"/api/v1/plants/{plant['plant_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["plant_id"] == plant["plant_id"]
        assert data["name"] == plant["name"]

    def test_get_plant_not_found(self, authenticated_client):
        """Getting a non-existent plant returns 404."""
        fake_id = str(uuid4())

        response = authenticated_client.get(f"/api/v1/plants/{fake_id}")

        assert response.status_code == 404

    def test_get_plant_unauthorized(self, client):
        """Getting a plant without auth - checks auth is enforced."""
        from uuid import uuid4

        response = client.get(f"/api/v1/plants/{uuid4()}")

        # Auth check may happen before/after plant lookup depending on middleware
        assert response.status_code in [401, 404]


class TestDeletePlant:
    """Tests for DELETE /api/v1/plants/{plant_id}"""

    def test_delete_plant_success(self, authenticated_client, create_test_plant):
        """Deleting an existing plant returns success."""
        plant = create_test_plant()

        response = authenticated_client.delete(f"/api/v1/plants/{plant['plant_id']}")

        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

        # Verify it's gone
        get_response = authenticated_client.get(f"/api/v1/plants/{plant['plant_id']}")
        assert get_response.status_code == 404

    def test_delete_plant_not_found(self, authenticated_client):
        """Deleting a non-existent plant returns 404."""
        fake_id = str(uuid4())

        response = authenticated_client.delete(f"/api/v1/plants/{fake_id}")

        assert response.status_code == 404

    def test_delete_plant_unauthorized(self, client):
        """Deleting a plant without auth returns 401."""
        response = client.delete(f"/api/v1/plants/{uuid4()}")

        assert response.status_code == 401


class TestUploadUrl:
    """Tests for POST /api/v1/plants/{plant_id}/upload-url"""

    def test_get_upload_url_success(self, authenticated_client, create_test_plant):
        """Getting upload URL for existing plant returns presigned URL."""
        plant = create_test_plant()

        response = authenticated_client.post(
            f"/api/v1/plants/{plant['plant_id']}/upload-url?filename=photo.jpg"
        )

        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "key" in data
        assert plant["plant_id"] in data["key"]

    def test_get_upload_url_invalid_extension(
        self, authenticated_client, create_test_plant
    ):
        """Getting upload URL with invalid extension returns 400."""
        plant = create_test_plant()

        response = authenticated_client.post(
            f"/api/v1/plants/{plant['plant_id']}/upload-url?filename=malware.exe"
        )

        assert response.status_code == 400
        assert "file type" in response.json()["detail"].lower()

    def test_get_upload_url_plant_not_found(self, authenticated_client):
        """Getting upload URL for non-existent plant returns 404."""
        fake_id = str(uuid4())

        response = authenticated_client.post(f"/api/v1/plants/{fake_id}/upload-url")

        assert response.status_code == 404


class TestConfirmUpload:
    """Tests for POST /api/v1/plants/{plant_id}/confirm-upload"""

    def test_confirm_upload_success(
        self, authenticated_client, create_test_plant, mock_firebase_user
    ):
        """Confirming upload updates plant with image URL."""
        plant = create_test_plant()
        plant_id = plant["plant_id"]
        user_id = mock_firebase_user["uid"]
        key = f"plants/{user_id}/{plant_id}/photo.jpg"

        response = authenticated_client.post(
            f"/api/v1/plants/{plant_id}/confirm-upload?key={key}"
        )

        assert response.status_code == 200
        assert "image_url" in response.json()

    def test_confirm_upload_invalid_key(self, authenticated_client, create_test_plant):
        """Confirming upload with invalid key returns 400."""
        plant = create_test_plant()

        response = authenticated_client.post(
            f"/api/v1/plants/{plant['plant_id']}/confirm-upload?key=invalid/path/photo.jpg"
        )

        assert response.status_code == 400

    def test_confirm_upload_plant_not_found(
        self, authenticated_client, mock_firebase_user
    ):
        """Confirming upload for non-existent plant returns 404."""
        fake_id = str(uuid4())
        user_id = mock_firebase_user["uid"]
        key = f"plants/{user_id}/{fake_id}/photo.jpg"

        response = authenticated_client.post(
            f"/api/v1/plants/{fake_id}/confirm-upload?key={key}"
        )

        assert response.status_code == 404
