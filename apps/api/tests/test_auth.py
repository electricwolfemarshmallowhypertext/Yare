import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from firebase_admin import auth
from src.middleware.auth import AuthMiddleware

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:15:12",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "auth_middleware"
}

@pytest.fixture
def test_app():
    """Create test FastAPI app with auth middleware"""
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        exclude_paths={"/health"},
        created_at=TEST_METADATA["created_at"],
        created_by=TEST_METADATA["created_by"]
    )
    
    @app.get("/protected")
    async def protected_route():
        return {"status": "success"}
        
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    return app

@pytest.fixture
def test_client(test_app):
    """Create test client with auth middleware"""
    return TestClient(test_app)

def test_missing_auth_header(test_client):
    """Test request without auth header"""
    response = test_client.get("/protected")
    assert response.status_code == 401
    assert "Missing or invalid authorization header" in response.json()["detail"]

def test_invalid_auth_format(test_client):
    """Test invalid auth header format"""
    response = test_client.get(
        "/protected",
        headers={"Authorization": "InvalidFormat token123"}
    )
    assert response.status_code == 401
    assert "Missing or invalid authorization header" in response.json()["detail"]

def test_invalid_token(test_client):
    """Test invalid token"""
    response = test_client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert "Invalid or expired token" in response.json()["detail"]

def test_excluded_path(test_client):
    """Test excluded path bypasses auth"""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

async def test_valid_token(test_client, mock_firebase):
    """Test valid token processing"""
    # Create test user and custom token
    user = await auth.create_user(
        uid="test_user",
        email="test@example.com"
    )
    custom_token = auth.create_custom_token(user.uid)
    
    # Exchange custom token for ID token
    id_token = auth.verify_id_token(custom_token)
    
    response = test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {id_token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Cleanup
    await auth.delete_user(user.uid)

async def test_user_tier_assignment(test_client, mock_firebase):
    """Test user tier assignment"""
    # Create users with different tiers
    free_user = await auth.create_user(uid="free_user")
    pro_user = await auth.create_user(
        uid="pro_user",
        custom_claims={"pro": True}
    )
    premium_user = await auth.create_user(
        uid="premium_user",
        custom_claims={"premium": True}
    )
    
    # Test free tier
    free_token = auth.create_custom_token(free_user.uid)
    response = test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {free_token}"}
    )
    assert response.status_code == 200
    assert "user_tier" in response.headers
    assert response.headers["user_tier"] == "free"
    
    # Test pro tier
    pro_token = auth.create_custom_token(pro_user.uid)
    response = test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {pro_token}"}
    )
    assert response.status_code == 200
    assert response.headers["user_tier"] == "pro"
    
    # Test premium tier
    premium_token = auth.create_custom_token(premium_user.uid)
    response = test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {premium_token}"}
    )
    assert response.status_code == 200
    assert response.headers["user_tier"] == "premium"
    
    # Cleanup
    await auth.delete_user(free_user.uid)
    await auth.delete_user(pro_user.uid)
    await auth.delete_user(premium_user.uid)

def test_revoked_token(test_client, mock_firebase):
    """Test revoked token handling"""
    # Create user and token
    user = auth.create_user(uid="revoked_test")
    token = auth.create_custom_token(user.uid)
    
    # Revoke all tokens
    auth.revoke_refresh_tokens(user.uid)
    
    response = test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 401
    assert "Token has been revoked" in response.json()["detail"]
    
    # Cleanup
    auth.delete_user(user.uid)