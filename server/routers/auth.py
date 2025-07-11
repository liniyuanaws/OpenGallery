"""
Traditional username/password authentication router
"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
import secrets
import hashlib
import jwt
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT settings
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# In-memory user storage (in production, use a proper database)
users_db: Dict[str, Dict[str, Any]] = {
    # Default demo users
    "admin": {
        "id": "user_admin",
        "username": "admin",
        "email": "admin@jaaz.com",
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    },
    "demo": {
        "id": "user_demo",
        "username": "demo",
        "email": "demo@jaaz.com", 
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    }
}

# Security
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginResponse(BaseModel):
    status: str
    token: str
    user_info: Dict[str, Any]
    message: str

class RegisterResponse(BaseModel):
    status: str
    message: str
    user_info: Dict[str, Any]

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == password_hash

def create_access_token(user_data: Dict[str, Any]) -> str:
    """Create JWT access token"""
    payload = {
        "sub": user_data["id"],
        "username": user_data["username"],
        "email": user_data["email"],
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return user data"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """User login with username and password"""
    try:
        username = request.username.lower().strip()
        password = request.password
        
        # Check if user exists
        if username not in users_db:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        user = users_db[username]
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled"
            )
        
        # Verify password
        if not verify_password(password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create access token
        token = create_access_token(user)
        
        # Prepare user info (exclude password hash)
        user_info = {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"],
            "provider": "jaaz"
        }
        
        return LoginResponse(
            status="success",
            token=token,
            user_info=user_info,
            message="Login successful"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    """User registration"""
    try:
        username = request.username.lower().strip()
        email = request.email.lower().strip()
        password = request.password
        
        # Validate input
        if len(username) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username must be at least 3 characters long"
            )
        
        if len(password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )
        
        # Check if username already exists
        if username in users_db:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Check if email already exists
        for user in users_db.values():
            if user["email"] == email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Create new user
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        new_user = {
            "id": user_id,
            "username": username,
            "email": email,
            "password_hash": hash_password(password),
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        }
        
        # Save user
        users_db[username] = new_user
        
        # Prepare user info (exclude password hash)
        user_info = {
            "id": new_user["id"],
            "username": new_user["username"],
            "email": new_user["email"],
            "created_at": new_user["created_at"],
            "provider": "jaaz"
        }
        
        return RegisterResponse(
            status="success",
            message="Registration successful",
            user_info=user_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user info from token"""
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Find user in database
        username = payload.get("username")
        if username and username in users_db:
            user = users_db[username]
            return {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "created_at": user["created_at"],
                "provider": "jaaz"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )

@router.post("/logout")
async def logout():
    """User logout (client should remove token)"""
    return {
        "status": "success",
        "message": "Logout successful"
    }

@router.get("/users")
async def list_users():
    """List all users (for development/admin purposes)"""
    users = []
    for user in users_db.values():
        users.append({
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"],
            "is_active": user.get("is_active", True)
        })
    return {"users": users}
