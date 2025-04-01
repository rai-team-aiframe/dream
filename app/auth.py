from datetime import datetime, timedelta
from typing import Optional
import logging
import traceback
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import aiosqlite

from . import database
from . import email_sender

# Configure logging
logger = logging.getLogger("dreammaker.auth")

# Security constants
SECRET_KEY = "59d3ca27e31db200421cc6bed0c91cf88d86fe3f32db39c2fdb575f1009a5052"  # In production, use a secure secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    id: int
    username: str
    email: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class EmailVerification(BaseModel):
    email: str
    code: str

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password functions
def verify_password(plain_password, hashed_password):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False

def get_password_hash(password):
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Error hashing password: {str(e)}")
        raise

# Token functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {str(e)}")
        logger.error(traceback.format_exc())
        raise

async def authenticate_user(db, username: str, password: str):
    try:
        logger.info(f"Authenticating user: {username}")
        user = await database.get_user_by_username(db, username)
        if not user:
            logger.warning(f"Authentication failed: User not found: {username}")
            return False
            
        logger.debug(f"Verifying password for user: {username}")
        if not verify_password(password, user["hashed_password"]):
            logger.warning(f"Authentication failed: Invalid password for user: {username}")
            return False
        
        # Check if user is verified
        if not user["is_verified"]:
            logger.warning(f"Authentication failed: User not verified: {username}")
            return "not_verified"
        
        logger.info(f"Authentication successful for user: {username}")
        return user
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# Email verification functions
async def send_verification_email(db, email: str, username: str):
    """Send a verification email to the user."""
    try:
        logger.info(f"Sending verification email to: {email}")
        
        # Generate verification code
        verification_code = email_sender.generate_verification_code()
        logger.info(f"Generated verification code: {verification_code} for user: {username}")
        
        # Update verification code in database
        result = await database.update_verification_code(db, email, verification_code)
        if not result:
            logger.error(f"Failed to update verification code in database for: {email}")
            return False
        
        # Send verification email
        success = await email_sender.send_verification_email(email, username, verification_code)
        if success:
            logger.info(f"Verification email sent successfully to: {email}")
        else:
            logger.error(f"Failed to send verification email to: {email}")
        return success
    except Exception as e:
        logger.error(f"Error sending verification email: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def verify_email(db, email: str, code: str):
    """Verify a user's email."""
    try:
        logger.info(f"Verifying email: {email} with code: {code}")
        success, message = await database.verify_user_email(db, email, code)
        
        if success:
            logger.info(f"Email verified successfully: {email}")
        else:
            logger.warning(f"Email verification failed: {email} - {message}")
            
        return success, message
    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        logger.error(traceback.format_exc())
        return False, f"Verification error: {str(e)}"

# User dependency for protected routes
async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    try:
        logger.debug("Getting current user from token")
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                logger.warning("Token missing username")
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError as e:
            logger.warning(f"JWT error: {str(e)}")
            raise credentials_exception
        
        async for db in database.get_db():
            user = await database.get_user_by_username(db, token_data.username)
            if user is None:
                logger.warning(f"User not found: {token_data.username}")
                raise credentials_exception
                
            # Check if user is verified
            if not user["is_verified"]:
                logger.warning(f"User not verified: {token_data.username}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email not verified",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            logger.debug(f"Current user retrieved: {token_data.username}")
            return user
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        logger.error(traceback.format_exc())
        raise credentials_exception

# Cookie-based auth for templates
async def get_current_user_from_cookie(request: Request):
    try:
        logger.debug("Getting user from cookie")
        token = request.cookies.get("access_token")
        if not token:
            logger.debug("No access token in cookies")
            return None
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                logger.warning("Token missing username")
                return None
        except JWTError as e:
            logger.warning(f"JWT error in cookie: {str(e)}")
            return None
        
        async for db in database.get_db():
            user = await database.get_user_by_username(db, username)
            
            # If user found but not verified, return special status
            if user and not user["is_verified"]:
                logger.info(f"User found but not verified: {username}")
                user = dict(user)
                user["needs_verification"] = True
            
            if user:
                logger.debug(f"User found from cookie: {username}")
            else:
                logger.warning(f"User not found from cookie: {username}")
                
            return user
    except Exception as e:
        logger.error(f"Error getting user from cookie: {str(e)}")
        logger.error(traceback.format_exc())
        return None