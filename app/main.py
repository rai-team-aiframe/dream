import os
import sys
import traceback
import logging
from datetime import timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Form, Response, status, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
import aiosqlite

from . import database
from . import auth
from . import image_generator
from . import translator
from . import email_sender

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("dreammaker")

# Create directory structure if not exists
os.makedirs("static/images/generated", exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="DreamMaker")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Models for API requests
class ImageGenerationRequest(BaseModel):
    prompt: str
    width: Optional[int] = 1024
    height: Optional[int] = 1024
    steps: Optional[int] = 4

class ImageResponse(BaseModel):
    id: int
    prompt: str
    translated_prompt: str
    file_path: str
    width: int
    height: int
    created_at: str

class ResendVerificationRequest(BaseModel):
    email: str

# Database initialization on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    await database.init_db()
    logger.info("Database initialized successfully")

# Routes for web pages
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        if user.get("needs_verification"):
            logger.info(f"User {user['username']} needs verification, redirecting to verify-email")
            return RedirectResponse(url=f"/verify-email?email={user['email']}", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("welcome.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        if user.get("needs_verification"):
            logger.info(f"User {user['username']} needs verification, redirecting to verify-email")
            return RedirectResponse(url=f"/verify-email?email={user['email']}", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        if user.get("needs_verification"):
            logger.info(f"User {user['username']} needs verification, redirecting to verify-email")
            return RedirectResponse(url=f"/verify-email?email={user['email']}", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request, email: str = None):
    logger.info(f"Accessing verification page for email: {email}")
    
    if not email:
        logger.warning("No email provided for verification page, redirecting to signup")
        return RedirectResponse(url="/signup", status_code=status.HTTP_302_FOUND)
    
    # Check if the email exists in the database
    async for db in database.get_db():
        user = await database.get_user_by_email(db, email)
        if not user:
            logger.warning(f"Email not found in database: {email}")
            return RedirectResponse(url="/signup", status_code=status.HTTP_302_FOUND)
        
        # If already verified, redirect to login
        if user["is_verified"]:
            logger.info(f"User {user['username']} already verified, redirecting to login")
            return RedirectResponse(url="/login?verified=true", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("verify_email.html", {"request": request, "email": email})

@app.get("/studio", response_class=HTMLResponse)
async def studio_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Check if user is verified
    if user.get("needs_verification"):
        logger.info(f"User {user['username']} needs verification, redirecting to verify-email")
        return RedirectResponse(url=f"/verify-email?email={user['email']}", status_code=status.HTTP_302_FOUND)
    
    # Get user's images
    async for db in database.get_db():
        images = await database.get_user_images(db, user["id"])
        return templates.TemplateResponse(
            "studio.html", {"request": request, "user": user, "images": images}
        )

# Authentication API routes
@app.post("/api/token")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    logger.info(f"Login attempt for username: {form_data.username}")
    
    async for db in database.get_db():
        user = await auth.authenticate_user(db, form_data.username, form_data.password)
        
        if not user:
            logger.warning(f"Login failed for username: {form_data.username} - Invalid credentials")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user's email is verified
        if user == "not_verified":
            # Get user to retrieve email
            user_data = await database.get_user_by_username(db, form_data.username)
            logger.warning(f"Login attempt for unverified account: {form_data.username}, email: {user_data['email']}")
            
            # Set a custom header to pass the email to the frontend
            response.headers["X-Email-Verification"] = user_data["email"]
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Email not verified. Please verify your email first.",
                headers={"email": user_data["email"]}
            )
        
        logger.info(f"Login successful for username: {form_data.username}")
        
        # Create access token
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": user["username"]}, expires_delta=access_token_expires
        )
        
        # Set cookie for web pages
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        
        return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/signup")
async def signup(user_create: auth.UserCreate):
    logger.info(f"Signup attempt for username: {user_create.username}, email: {user_create.email}")
    
    # Validate email domain (only Gmail and Outlook allowed)
    if not email_sender.is_valid_email_domain(user_create.email):
        logger.warning(f"Invalid email domain: {user_create.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Gmail and Outlook email addresses are allowed"
        )
    
    async for db in database.get_db():
        # Check if username already exists
        existing_user = await database.get_user_by_username(db, user_create.username)
        if existing_user:
            logger.warning(f"Signup failed: Username already exists: {user_create.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        existing_email = await database.get_user_by_email(db, user_create.email)
        if existing_email:
            # If user exists but is not verified, allow them to try again
            if not existing_email["is_verified"]:
                logger.info(f"User exists but not verified, sending new code: {user_create.email}")
                
                # Generate new verification code
                verification_code = email_sender.generate_verification_code()
                logger.info(f"New verification code generated: {verification_code}")
                
                # Update the verification code
                await database.update_verification_code(db, user_create.email, verification_code)
                
                # Send new verification email
                success = await email_sender.send_verification_email(
                    user_create.email, existing_email["username"], verification_code
                )
                
                if not success:
                    logger.error(f"Failed to send verification email to: {user_create.email}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to send verification email. Please try again."
                    )
                
                return {"detail": "User already exists but not verified. New verification code sent."}
            else:
                logger.warning(f"Signup failed: Email already registered: {user_create.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Create user
        hashed_password = auth.get_password_hash(user_create.password)
        
        # Generate verification code
        verification_code = email_sender.generate_verification_code()
        logger.info(f"Verification code generated for {user_create.email}: {verification_code}")
        
        # Create user with verification code
        user_id = await database.create_user(
            db, user_create.username, user_create.email, hashed_password, verification_code
        )
        
        if user_id is None:
            logger.error(f"Failed to create user: {user_create.username}, {user_create.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating user"
            )
        
        logger.info(f"User created with ID: {user_id}")
        
        # Send verification email
        success = await email_sender.send_verification_email(
            user_create.email, user_create.username, verification_code
        )
        
        if not success:
            logger.error(f"Failed to send verification email to: {user_create.email}")
            # Delete the user if email fails to send
            await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            await db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email. Please try again."
            )
        
        logger.info(f"Verification email sent successfully to: {user_create.email}")
        return {"detail": "User created successfully. Please check your email for verification code."}

@app.post("/api/verify-email")
async def verify_email(verification: auth.EmailVerification):
    logger.info(f"Verifying email: {verification.email} with code: {verification.code}")
    
    try:
        async for db in database.get_db():
            # Check if user exists
            user = await database.get_user_by_email(db, verification.email)
            if not user:
                logger.warning(f"Verification failed: Email not found: {verification.email}")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Email not found"}
                )
            
            # Debug output
            logger.info(f"User found: {user['username']}")
            logger.info(f"DB code: {user['verification_code']} vs Submitted code: {verification.code}")
            logger.info(f"Verification expiry: {user['verification_expiry']}")
            
            # Verify the email
            success, message = await database.verify_user_email(db, verification.email, verification.code)
            
            if not success:
                logger.warning(f"Verification failed: {message} for email: {verification.email}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": message}
                )
            
            logger.info(f"Email verified successfully: {verification.email}")
            
            # Create token for automatic login (optional)
            access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = auth.create_access_token(
                data={"sub": user["username"]}, expires_delta=access_token_expires
            )
            
            # Return success response with token
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "detail": message, 
                    "verified": True,
                    "username": user["username"],
                    "access_token": access_token,
                    "token_type": "bearer"
                }
            )
    except Exception as e:
        logger.error(f"Exception during email verification: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Verification error: {str(e)}"}
        )

@app.post("/api/resend-verification")
async def resend_verification(request: ResendVerificationRequest):
    logger.info(f"Resending verification code for email: {request.email}")
    
    async for db in database.get_db():
        # Check if email exists
        user = await database.get_user_by_email(db, request.email)
        
        if not user:
            logger.warning(f"Resend verification failed: Email not found: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not found"
            )
        
        # Check if already verified
        if user["is_verified"]:
            logger.warning(f"Resend verification skipped: Email already verified: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )
        
        # Send new verification email
        success = await auth.send_verification_email(db, request.email, user["username"])
        
        if not success:
            logger.error(f"Failed to resend verification email to: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email. Please try again."
            )
        
        logger.info(f"Verification email resent successfully to: {request.email}")
        return {"detail": "Verification email sent successfully"}

@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"detail": "Logged out successfully"}

# Image generation API routes
@app.post("/api/generate-image")
async def generate_image(
    request: ImageGenerationRequest, 
    request_obj: Request
):
    # Get user from cookie authentication
    user = await auth.get_current_user_from_cookie(request_obj)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Check if user is verified
    if user.get("needs_verification"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to access this feature."
        )
        
    try:
        # Translate prompt if not in English
        translated_prompt = await translator.translate_to_english(request.prompt)
        
        # Generate the image
        file_path = await image_generator.generate_image(
            prompt=translated_prompt,
            width=request.width,
            height=request.height,
            steps=request.steps
        )
        
        # Save to database
        async for db in database.get_db():
            image_id = await database.save_image(
                db, 
                user["id"], 
                request.prompt, 
                translated_prompt, 
                file_path, 
                request.width, 
                request.height
            )
            
            # Get the saved image
            image = await database.get_image(db, image_id)
            
            return {
                "id": image["id"],
                "prompt": image["prompt"],
                "translated_prompt": image["translated_prompt"],
                "file_path": image["file_path"],
                "width": image["width"],
                "height": image["height"],
                "created_at": image["created_at"]
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating image: {str(e)}"
        )

@app.get("/api/images")
async def get_user_images(request: Request):
    # Get user from cookie authentication
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Check if user is verified
    if user.get("needs_verification"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to access this feature."
        )
        
    async for db in database.get_db():
        images = await database.get_user_images(db, user["id"])
        return [
            {
                "id": img["id"],
                "prompt": img["prompt"],
                "translated_prompt": img["translated_prompt"],
                "file_path": img["file_path"],
                "width": img["width"],
                "height": img["height"],
                "created_at": img["created_at"]
            }
            for img in images
        ]

@app.get("/api/images/{image_id}")
async def get_image(image_id: int, request: Request):
    # Get user from cookie authentication
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Check if user is verified
    if user.get("needs_verification"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to access this feature."
        )
        
    async for db in database.get_db():
        image = await database.get_image(db, image_id)
        
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        # Check if the image belongs to the user
        if image["user_id"] != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this image"
            )
        
        return {
            "id": image["id"],
            "prompt": image["prompt"],
            "translated_prompt": image["translated_prompt"],
            "file_path": image["file_path"],
            "width": image["width"],
            "height": image["height"],
            "created_at": image["created_at"]
        }

@app.get("/api/download/{image_id}")
async def download_image(image_id: int, request: Request):
    # Get user from cookie authentication
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Check if user is verified
    if user.get("needs_verification"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to access this feature."
        )
        
    async for db in database.get_db():
        image = await database.get_image(db, image_id)
        
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        # Check if the image belongs to the user
        if image["user_id"] != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this image"
            )
        
        # Return the file for download
        return FileResponse(
            path=image["file_path"],
            filename=os.path.basename(image["file_path"]),
            media_type="image/png"
        )

# Run with: uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)