from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin.auth import (
    ExpiredIdTokenError,
    RevokedIdTokenError,
    InvalidIdTokenError,
    CertificateFetchError,
)
from pathlib import Path
import json
import os

# Initialize Firebase Admin
def init_firebase():
    # Skip initialization in test environment
    # This allows tests to mock get_current_user without needing Firebase credentials. 
    # Had issues testing the firbase sdk
    if os.environ.get("ENVIRONMENT") == "test":
        return
        
    if firebase_admin._apps:
        return
    
    # Try environment variable first (for Lambda)
    firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_creds:
        cred_dict = json.loads(firebase_creds)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fall back to file (for local dev)
        cred_path = Path(__file__).parent.parent.parent / "firebase-service-account.json"
        cred = credentials.Certificate(str(cred_path))
    
    firebase_admin.initialize_app(cred)

init_firebase()

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Verify Firebase token and return user info."""
    
    # No credentials provided
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "missing_token",
                "message": "Authentication required. Please sign in."
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Empty token
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "empty_token",
                "message": "Authentication token is empty. Please sign in again."
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
        }
    
    except ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_expired",
                "message": "Your session has expired. Please sign in again."
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_revoked",
                "message": "Your session has been revoked. Please sign in again."
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Invalid authentication token. Please sign in again."
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except CertificateFetchError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "auth_service_unavailable",
                "message": "Authentication service temporarily unavailable. Please try again."
            },
        )
    
    except Exception as e:
        # Log unexpected errors for debugging
        print(f"Unexpected auth error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "auth_failed",
                "message": "Authentication failed. Please sign in again."
            },
            headers={"WWW-Authenticate": "Bearer"},
        )