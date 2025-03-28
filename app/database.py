import aiosqlite
import os
from datetime import datetime
from typing import List, Optional

DATABASE_PATH = "dreammaker.db"

async def get_db():
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

async def init_db():
    """Initialize the database with required tables."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Create users table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_reset_date TEXT DEFAULT (strftime('%Y-%m-%d', 'now')),
            remaining_images INTEGER DEFAULT 50
        )
        """)
        
        # Create images table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            translated_prompt TEXT NOT NULL,
            file_path TEXT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        
        # Create rate limiting table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            last_generation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        
        await db.commit()

# User model operations
async def create_user(db, username: str, email: str, hashed_password: str):
    """Create a new user in the database."""
    try:
        cursor = await db.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            (username, email, hashed_password)
        )
        await db.commit()
        return cursor.lastrowid
    except aiosqlite.IntegrityError:
        return None

async def get_user_by_username(db, username: str):
    """Get a user by username."""
    async with db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ) as cursor:
        return await cursor.fetchone()

async def get_user_by_email(db, email: str):
    """Get a user by email."""
    async with db.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ) as cursor:
        return await cursor.fetchone()

async def get_user_by_id(db, user_id: int):
    """Get a user by ID."""
    async with db.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ) as cursor:
        return await cursor.fetchone()

# User image limits and rate limiting
async def check_and_update_daily_limit(db, user_id):
    """Check if user has images remaining for the day and reset if needed."""
    # Check current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Get user's last reset date and remaining images
    async with db.execute(
        "SELECT last_reset_date, remaining_images FROM users WHERE id = ?", (user_id,)
    ) as cursor:
        user_data = await cursor.fetchone()
        
    if not user_data:
        return False, "User not found"
    
    last_reset_date = user_data['last_reset_date']
    remaining_images = user_data['remaining_images']
    
    # Reset counter if it's a new day
    if last_reset_date != current_date:
        await db.execute(
            "UPDATE users SET last_reset_date = ?, remaining_images = 50 WHERE id = ?",
            (current_date, user_id)
        )
        await db.commit()
        remaining_images = 50
    
    # Check if user has images remaining
    if remaining_images <= 0:
        return False, f"Daily limit reached. Try again tomorrow."
    
    return True, remaining_images

async def decrement_image_count(db, user_id):
    """Decrement the user's remaining image count for the day."""
    await db.execute(
        "UPDATE users SET remaining_images = remaining_images - 1 WHERE id = ?",
        (user_id,)
    )
    await db.commit()

async def get_remaining_images(db, user_id):
    """Get the number of remaining images for a user."""
    # Check current date first to reset if needed
    await check_and_update_daily_limit(db, user_id)
    
    # Get remaining images
    async with db.execute(
        "SELECT remaining_images FROM users WHERE id = ?", (user_id,)
    ) as cursor:
        user_data = await cursor.fetchone()
        
    if not user_data:
        return 0
        
    return user_data['remaining_images']

async def check_rate_limit(db, user_id):
    """Check if user is within rate limit (10 seconds between generations)."""
    # Check if user has a rate limit entry
    async with db.execute(
        "SELECT last_generation_time FROM rate_limits WHERE user_id = ?", (user_id,)
    ) as cursor:
        rate_data = await cursor.fetchone()
    
    current_time = datetime.now()
    
    if not rate_data:
        # First generation, create entry
        await db.execute(
            "INSERT INTO rate_limits (user_id, last_generation_time) VALUES (?, ?)",
            (user_id, current_time)
        )
        await db.commit()
        return True, 0
    
    # Calculate time difference
    last_time = datetime.fromisoformat(rate_data['last_generation_time'].replace('Z', '+00:00'))
    time_diff = (current_time - last_time).total_seconds()
    
    # Check if enough time has passed
    if time_diff < 10:
        return False, 10 - int(time_diff)
    
    # Update the last generation time
    await db.execute(
        "UPDATE rate_limits SET last_generation_time = ? WHERE user_id = ?",
        (current_time, user_id)
    )
    await db.commit()
    
    return True, 0

# Image model operations
async def save_image(db, user_id: int, prompt: str, translated_prompt: str, 
                    file_path: str, width: int, height: int):
    """Save a generated image to the database."""
    cursor = await db.execute(
        """
        INSERT INTO images (user_id, prompt, translated_prompt, file_path, width, height)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, prompt, translated_prompt, file_path, width, height)
    )
    await db.commit()
    return cursor.lastrowid

async def get_user_images(db, user_id: int):
    """Get all images for a specific user."""
    async with db.execute(
        "SELECT * FROM images WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ) as cursor:
        return await cursor.fetchall()

async def get_image(db, image_id: int):
    """Get an image by ID."""
    async with db.execute(
        "SELECT * FROM images WHERE id = ?", (image_id,)
    ) as cursor:
        return await cursor.fetchone()