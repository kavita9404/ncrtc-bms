"""Password hashing (bcrypt), JWT sessions, and role / depot-scope checks."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import ACCESS_TOKEN_MINUTES, ALGORITHM, SECRET_KEY
from .database import get_db
from .models import User

ROLES = ("driver", "conductor", "depot_manager", "control_operator", "admin", "executive")
GLOBAL_ROLES = {"admin", "control_operator", "executive"}  # see every depot
CREW_ROLES = {"driver", "conductor"}
OPS_ROLES = ("admin", "control_operator", "depot_manager")  # may change data
VIEW_ROLES = ("admin", "control_operator", "depot_manager", "executive")  # may see ops dashboards

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", {"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise err
    if not user:
        raise err
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role is not allowed to do this")
        return user
    return checker


def can_access_depot(user: User, depot_id: int | None) -> bool:
    return user.role in GLOBAL_ROLES or (depot_id is not None and user.depot_id == depot_id)


def resolve_depot(user: User, requested: int | None) -> int | None:
    """Depot filter to apply for this user. Global roles may pick any; others are pinned to their own."""
    if user.role in GLOBAL_ROLES:
        return requested
    if requested is not None and requested != user.depot_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only access your own depot")
    return user.depot_id
