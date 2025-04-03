import os
import json
from datetime import timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Request, Form, Response, status, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
import aiosqlite

from . import database
from . import auth
from . import image_generator
from . import translator
from . import email_service
from . import queue_manager
from . import profile_manager
from . import payment_manager

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

class TaskStatusResponse(BaseModel):
    task_id: int
    status: str
    position: int
    estimated_time: int
    result_path: Optional[str] = None
    error_message: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class UsernameChangeRequest(BaseModel):
    new_username: str

class EmailChangeRequest(BaseModel):
    new_email: EmailStr

class VerificationRequest(BaseModel):
    code: str

class TokenPackagePurchaseRequest(BaseModel):
    package_id: str

class PlanUpgradeRequest(BaseModel):
    plan_id: str

# Database initialization on startup
@app.on_event("startup")
async def startup_event():
    await database.init_db()
    # Start the queue manager
    await queue_manager.queue_manager.start()

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    # Stop the queue manager
    await queue_manager.queue_manager.stop()

# Helper function to check if user has selected a plan
async def check_user_has_plan(user):
    """Check if user has selected a plan"""
    try:
        # Try to access the has_selected_plan attribute directly
        # If it exists, return its value, otherwise return False
        return bool(user["has_selected_plan"])
    except (KeyError, IndexError, TypeError):
        # If the field doesn't exist or there's any other error, assume they haven't selected a plan
        return False

# Routes for web pages
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        # Check if user has selected a plan
        has_plan = await check_user_has_plan(user)
        if not has_plan:
            return RedirectResponse(url="/plans?new_user=true", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("welcome.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        # Check if user has selected a plan
        has_plan = await check_user_has_plan(user)
        if not has_plan:
            return RedirectResponse(url="/plans?new_user=true", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        # Check if user has selected a plan
        has_plan = await check_user_has_plan(user)
        if not has_plan:
            return RedirectResponse(url="/plans?new_user=true", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request):
    # Check if user is already authenticated
    user = await auth.get_current_user_from_cookie(request)
    if user:
        # Check if user has selected a plan
        has_plan = await check_user_has_plan(user)
        if not has_plan:
            return RedirectResponse(url="/plans?new_user=true", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    
    # Check for email in query params
    email = request.query_params.get("email", "")
    if not email:
        return RedirectResponse(url="/signup", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("verify.html", {"request": request, "email": email})

@app.get("/studio", response_class=HTMLResponse)
async def studio_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Check if user has selected a plan
    has_plan = await check_user_has_plan(user)
    if not has_plan:
        return RedirectResponse(url="/plans?new_user=true", status_code=status.HTTP_302_FOUND)
    
    # Get user's images and remaining count
    async for db in database.get_db():
        images = await database.get_user_images(db, user["id"])
        remaining_images = await database.get_remaining_images(db, user["id"])
        token_balance = await database.get_user_tokens(db, user_id=user["id"])
        plan_details = await database.get_user_plan_details(db, user_id=user["id"])
        
        # Get user's active tasks
        user_tasks = await database.get_user_queue_tasks(db, user["id"])
        active_tasks = [t for t in user_tasks if t['status'] in ('pending', 'processing')]
        
        context = {
            "request": request, 
            "user": user, 
            "images": images,
            "remaining_images": remaining_images,
            "token_balance": token_balance,
            "token_cost": database.IMAGE_TOKEN_COST,
            "plan": plan_details,
            "has_active_task": len(active_tasks) > 0,
            "active_task_id": active_tasks[0]['id'] if active_tasks else None
        }
        
        return templates.TemplateResponse("studio.html", context)

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Check if user has selected a plan
    has_plan = await check_user_has_plan(user)
    if not has_plan:
        return RedirectResponse(url="/plans?new_user=true", status_code=status.HTTP_302_FOUND)
    
    async for db in database.get_db():
        profile_data = await profile_manager.get_user_profile_data(db, user["id"])
        
        context = {
            "request": request,
            "user": user,
            "profile": profile_data
        }
        
        return templates.TemplateResponse("profile.html", context)

@app.get("/plans", response_class=HTMLResponse)
async def plans_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Check if this is a new user
    is_new_user = request.query_params.get("new_user", "false") == "true"
    
    async for db in database.get_db():
        plans_data = await payment_manager.get_available_plans(db, user["id"])
        token_packages = await payment_manager.get_token_packages()
        token_balance = await database.get_user_tokens(db, user["id"])
        payment_history = await payment_manager.get_payment_history(db, user["id"])
        
        context = {
            "request": request,
            "user": user,
            "plans": plans_data["plans"],
            "current_plan": plans_data["current_plan"],
            "token_packages": token_packages,
            "token_balance": token_balance,
            "payment_history": payment_history,
            "is_new_user": is_new_user
        }
        
        return templates.TemplateResponse("plans.html", context)

# Authentication API routes
@app.post("/api/token")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    async for db in database.get_db():
        user = await auth.authenticate_user(db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
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

@app.post("/api/send-verification")
async def send_verification_code(user_create: auth.UserCreate):
    # Check if email domain is valid
    if not email_service.is_valid_email_domain(user_create.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Gmail and Outlook email accounts are accepted"
        )
    
    async for db in database.get_db():
        # Check if username already exists
        existing_user = await database.get_user_by_username(db, user_create.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        existing_email = await database.get_user_by_email(db, user_create.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Generate verification code
        verification_code = email_service.generate_verification_code()
        
        # Hash password and store verification data
        hashed_password = auth.get_password_hash(user_create.password)
        await database.save_verification_code(
            db, user_create.username, user_create.email, hashed_password, verification_code
        )
        
        # Send verification email
        email_sent = email_service.send_verification_email(
            user_create.email, user_create.username, verification_code
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email"
            )
        
        return {"detail": "Verification email sent", "email": user_create.email}

@app.post("/api/verify-account")
async def verify_account(email: str = Form(...), code: str = Form(...)):
    async for db in database.get_db():
        success, result = await database.verify_and_create_user(db, email, code)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result
            )
        
        # Get the created user
        user = await database.get_user_by_id(db, result)
        
        # Set has_selected_plan to false for new users
        # This will force them to visit the plans page
        if user:
            await database.update_user_profile(db, user["id"], has_selected_plan=False)
        
        # Create access token
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": user["username"]}, expires_delta=access_token_expires
        )
        
        response = Response(
            content=json.dumps({"detail": "Account verified successfully", "redirect": "/plans?new_user=true"}),
            media_type="application/json"
        )
        
        # Set cookie for web pages
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        
        return response

@app.post("/api/signup")
async def signup(user_create: auth.UserCreate):
    async for db in database.get_db():
        # Check if username already exists
        existing_user = await database.get_user_by_username(db, user_create.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        existing_email = await database.get_user_by_email(db, user_create.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        hashed_password = auth.get_password_hash(user_create.password)
        user_id = await database.create_user(
            db, user_create.username, user_create.email, hashed_password
        )
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating user"
            )
        
        return {"detail": "User created successfully"}

@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"detail": "Logged out successfully"}

# Plan selection for new users
@app.post("/api/select-initial-plan")
async def select_initial_plan(request: Request, plan_data: PlanUpgradeRequest):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        # Set the plan
        if plan_data.plan_id not in database.PLANS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid plan"
            )
        
        # For free plan, just update the user profile
        if plan_data.plan_id == database.PLAN_FREE:
            # Mark that the user has selected a plan
            await database.update_user_profile(db, user["id"], 
                plan=database.PLAN_FREE, 
                has_selected_plan=True)
            return {"detail": "Free plan selected", "redirect": "/studio"}
        
        # For paid plans, process payment
        success, message, payment_id = await payment_manager.upgrade_user_plan(
            db, user["id"], plan_data.plan_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Mark that the user has selected a plan
        await database.update_user_profile(db, user["id"], has_selected_plan=True)
        
        return {"detail": message, "redirect": "/studio"}

# Profile management routes
@app.post("/api/profile/request-password-change")
async def request_password_change(request: Request, password_data: PasswordChangeRequest):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        # Verify current password
        auth_user = await auth.authenticate_user(db, user["username"], password_data.current_password)
        if not auth_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Request password change
        success, message = await profile_manager.request_password_change(
            db, user["id"], user["email"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"detail": message}

@app.post("/api/profile/verify-password-change")
async def verify_password_change(request: Request, verification: VerificationRequest, new_password: str = Form(...)):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        # Verify and change password
        success, message = await profile_manager.verify_and_change_password(
            db, user["id"], verification.code, new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"detail": message}

@app.post("/api/profile/request-username-change")
async def request_username_change(request: Request, username_data: UsernameChangeRequest):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        # Request username change
        success, message = await profile_manager.request_username_change(
            db, user["id"], user["email"], username_data.new_username
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"detail": message}

@app.post("/api/profile/verify-username-change")
async def verify_username_change(request: Request, verification: VerificationRequest):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        # Verify and change username
        success, message = await profile_manager.verify_and_change_username(
            db, user["id"], verification.code
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # If username was changed successfully, we need to update the token
        if success:
            # Get the updated user
            updated_user = await database.get_user_by_id(db, user["id"])
            
            # Create a new token with the updated username
            access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = auth.create_access_token(
                data={"sub": updated_user["username"]}, expires_delta=access_token_expires
            )
            
            response = JSONResponse(content={"detail": message})
            
            # Set the updated cookie
            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                samesite="lax"
            )
            
            return response
        
        return {"detail": message}

@app.post("/api/profile/request-email-change")
async def request_email_change(request: Request, email_data: EmailChangeRequest):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        # Request email change
        success, message = await profile_manager.request_email_change(
            db, user["id"], user["email"], email_data.new_email
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"detail": message}

@app.post("/api/profile/verify-email-change")
async def verify_email_change(request: Request, verification: VerificationRequest):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        # Verify and change email
        success, message = await profile_manager.verify_and_change_email(
            db, user["id"], verification.code
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"detail": message}

@app.get("/api/profile")
async def get_profile(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        profile_data = await profile_manager.get_user_profile_data(db, user["id"])
        return profile_data

# Payment and plans routes
@app.post("/api/payments/purchase-tokens")
async def purchase_tokens(
    request: Request,
    purchase_data: TokenPackagePurchaseRequest
):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        success, message, payment_id = await payment_manager.purchase_token_package(
            db, user["id"], purchase_data.package_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"detail": message, "payment_id": payment_id}

@app.post("/api/payments/upgrade-plan")
async def upgrade_plan(
    request: Request,
    upgrade_data: PlanUpgradeRequest
):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        success, message, payment_id = await payment_manager.upgrade_user_plan(
            db, user["id"], upgrade_data.plan_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"detail": message, "payment_id": payment_id}

@app.get("/api/payments/history")
async def get_payment_history(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        payments = await payment_manager.get_payment_history(db, user["id"])
        return payments

@app.get("/api/plans")
async def get_plans(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        plans = await payment_manager.get_available_plans(db, user["id"])
        return plans

@app.get("/api/token-packages")
async def get_token_packages():
    packages = await payment_manager.get_token_packages()
    return packages

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
    
    # Check if user has selected a plan
    has_plan = await check_user_has_plan(user)
    if not has_plan:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must select a plan first"
        )
    
    try:
        async for db in database.get_db():
            # Check if user can generate (has tokens, not rate limited)
            can_generate, message = await database.check_user_can_generate(db, user["id"])
            if not can_generate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
            
            # Add to queue instead of generating directly
            task_id = await queue_manager.queue_manager.add_task(
                user["id"],
                request.prompt,
                request.width,
                request.height,
                request.steps
            )
            
            # Return task ID for status polling
            return {"task_id": task_id, "status": "queued"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating image: {str(e)}"
        )

@app.get("/api/task-status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: int, request: Request):
    # Get user from cookie authentication
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    try:
        # Get task status from queue manager
        status = await queue_manager.queue_manager.get_task_status(task_id)
        
        # Check if task exists and belongs to user
        async for db in database.get_db():
            task = await database.get_task_by_id(db, task_id)
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            if task["user_id"] != user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this task"
                )
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting task status: {str(e)}"
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
                "created_at": img["created_at"],
                "tokens_used": img["tokens_used"]
            }
            for img in images
        ]

@app.get("/api/user-stats")
async def get_user_stats(request: Request):
    # Get user from cookie authentication
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    async for db in database.get_db():
        remaining_images = await database.get_remaining_images(db, user["id"])
        token_balance = await database.get_user_tokens(db, user["id"])
        plan_details = await database.get_user_plan_details(db, user["id"])
        rate_ok, wait_time = await database.check_rate_limit(db, user["id"])
        
        return {
            "remaining_images": remaining_images,
            "token_balance": token_balance,
            "token_cost_per_image": database.IMAGE_TOKEN_COST,
            "plan": {
                "name": plan_details["name"],
                "generation_wait": plan_details["generation_wait"],
                "queue_wait": plan_details["queue_wait"]
            },
            "rate_limited": not rate_ok,
            "wait_time": wait_time if not rate_ok else 0
        }

@app.get("/api/images/{image_id}")
async def get_image(image_id: int, request: Request):
    # Get user from cookie authentication
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
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
            "created_at": image["created_at"],
            "tokens_used": image["tokens_used"]
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