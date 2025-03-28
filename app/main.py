import os
from datetime import timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Form, Response, status, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
import aiosqlite

from . import database
from . import auth
from . import image_generator
from . import translator

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

# Database initialization on startup
@app.on_event("startup")
async def startup_event():
    await database.init_db()

# Routes for web pages
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("welcome.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/studio", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/studio", response_class=HTMLResponse)
async def studio_page(request: Request):
    user = await auth.get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Get user's images
    async for db in database.get_db():
        images = await database.get_user_images(db, user["id"])
        return templates.TemplateResponse(
            "studio.html", {"request": request, "user": user, "images": images}
        )

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