from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.users import create_user, email_exists, get_user_by_email
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterRequest):
    """Register a new user. Password is bcrypt-hashed before storage."""
    if await email_exists(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    password_hash = hash_password(body.password)
    user = await create_user(body.email, body.username, password_hash)
    return UserOut(**user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate and return a JWT access token."""
    user = await get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token(user["user_id"], user["email"], user["username"])
    return TokenResponse(
        access_token=token,
        user=UserOut(
            user_id=user["user_id"],
            email=user["email"],
            username=user["username"],
            created_at=user["created_at"],
        ),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserOut(**current_user)


@router.post("/logout", status_code=200)
async def logout():
    """
    Logout is handled client-side (token removal from storage).
    This endpoint exists for completeness and future token blacklisting.
    """
    return {"message": "Logged out successfully"}
