import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings

security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    # Phones capitalize the first letter of the user ("Nico"); the user name
    # isn't secret, so it's compared ignoring case and surrounding spaces.
    correct_user = secrets.compare_digest(
        credentials.username.strip().lower().encode(), settings.basic_auth_user.strip().lower().encode()
    )
    correct_password = secrets.compare_digest(credentials.password, settings.basic_auth_password)
    if not (correct_user and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
