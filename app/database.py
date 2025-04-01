import aiosqlite
import os
import logging
import traceback
from datetime import datetime
from typing import List, Optional

# Configure logging
logger = logging.getLogger("dreammaker.database")

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
    logger.info(f"Initializing database at {DATABASE_PATH}")
    try:
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
                remaining_images INTEGER DEFAULT 50,
                is_verified INTEGER DEFAULT 0,
                verification_code TEXT,
                verification_expiry REAL
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
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        logger.error(traceback.format_exc())
        raise

# User model operations
async def create_user(db, username: str, email: str, hashed_password: str, verification_code: str = None):
    """Create a new user in the database."""
    try:
        logger.info(f"Creating new user: {username}, {email}")
        # Set expiry time to 30 minutes from now
        expiry_time = datetime.now().timestamp() + 30 * 60 
        logger.info(f"Verification expiry set to: {expiry_time} (in epoch seconds)")
        
        cursor = await db.execute(
            """
            INSERT INTO users 
            (username, email, hashed_password, is_verified, verification_code, verification_expiry) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, email, hashed_password, 0, verification_code, expiry_time)
        )
        await db.commit()
        user_id = cursor.lastrowid
        logger.info(f"User created with ID: {user_id}")
        return user_id
    except aiosqlite.IntegrityError as e:
        logger.error(f"IntegrityError creating user: {str(e)}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        logger.error(traceback.format_exc())
        return None

async def get_user_by_username(db, username: str):
    """Get a user by username."""
    try:
        logger.debug(f"Getting user by username: {username}")
        async with db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ) as cursor:
            user = await cursor.fetchone()
            if user:
                logger.debug(f"User found: {username}")
            else:
                logger.debug(f"User not found: {username}")
            return user
    except Exception as e:
        logger.error(f"Error getting user by username: {str(e)}")
        logger.error(traceback.format_exc())
        return None

async def get_user_by_email(db, email: str):
    """Get a user by email."""
    try:
        logger.debug(f"Getting user by email: {email}")
        async with db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ) as cursor:
            user = await cursor.fetchone()
            if user:
                logger.debug(f"User found with email: {email}")
            else:
                logger.debug(f"No user found with email: {email}")
            return user
    except Exception as e:
        logger.error(f"Error getting user by email: {str(e)}")
        logger.error(traceback.format_exc())
        return None

async def get_user_by_id(db, user_id: int):
    """Get a user by ID."""
    try:
        logger.debug(f"Getting user by ID: {user_id}")
        async with db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting user by ID: {str(e)}")
        logger.error(traceback.format_exc())
        return None

async def verify_user_email(db, email: str, verification_code: str):
    """Verify a user's email."""
    try:
        logger.info(f"Verifying email for: {email} with code: {verification_code}")
        
        # Get user by email
        user = await get_user_by_email(db, email)
        
        if not user:
            logger.warning(f"Verification failed: User not found for email: {email}")
            return False, "User not found"
        
        # If already verified
        if user['is_verified']:
            logger.info(f"Email already verified: {email}")
            return True, "Email already verified"
        
        # Debug info
        logger.info(f"Verification attempt for user: {user['username']}")
        logger.info(f"Stored code: {user['verification_code']}")
        logger.info(f"Submitted code: {verification_code}")
        logger.info(f"Verification expiry: {user['verification_expiry']}")
        logger.info(f"Code types - DB: {type(user['verification_code'])}, Input: {type(verification_code)}")
        
        # Normalize codes for comparison - ensure they're both strings and trim whitespace
        db_code = str(user['verification_code']).strip() if user['verification_code'] is not None else ""
        input_code = str(verification_code).strip() if verification_code is not None else ""
        
        logger.info(f"Normalized codes - DB: '{db_code}', Input: '{input_code}'")
        
        # Get current time
        current_time = datetime.now().timestamp()
        logger.info(f"Current time: {current_time} (in epoch seconds)")
        
        # Check if verification code is expired
        if user['verification_expiry'] is None or user['verification_expiry'] < current_time:
            logger.warning(f"Verification code expired for email: {email}")
            return False, "Verification code has expired"
        
        # Check if verification code matches
        if db_code != input_code:
            logger.warning(f"Invalid verification code for email: {email}")
            logger.warning(f"Expected: '{db_code}', Got: '{input_code}'")
            return False, "Invalid verification code"
        
        # Update user as verified
        try:
            await db.execute(
                "UPDATE users SET is_verified = 1, verification_code = NULL WHERE id = ?",
                (user['id'],)
            )
            await db.commit()
            logger.info(f"Database updated for user {user['id']}: is_verified = 1")
        except Exception as update_error:
            logger.error(f"Database update error: {str(update_error)}")
            logger.error(traceback.format_exc())
            return False, f"Database error: {str(update_error)}"
        
        logger.info(f"Email successfully verified: {email}")
        return True, "Email verified successfully"
    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        logger.error(traceback.format_exc())
        return False, f"Verification error: {str(e)}"

async def is_user_verified(db, user_id: int):
    """Check if a user is verified."""
    try:
        logger.debug(f"Checking if user is verified: {user_id}")
        async with db.execute(
            "SELECT is_verified FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            user = await cursor.fetchone()
            
        if not user:
            logger.warning(f"User not found for verification check: {user_id}")
            return False
        
        is_verified = bool(user['is_verified'])
        logger.debug(f"User {user_id} verification status: {is_verified}")
        return is_verified
    except Exception as e:
        logger.error(f"Error checking user verification: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def update_verification_code(db, email: str, verification_code: str):
    """Update verification code for a user."""
    try:
        logger.info(f"Updating verification code for email: {email}")
        
        # Set expiry time to 30 minutes from now
        expiry_time = datetime.now().timestamp() + 30 * 60
        logger.info(f"New verification expiry: {expiry_time} (in epoch seconds)")
        
        # Update verification code and expiry time
        await db.execute(
            "UPDATE users SET verification_code = ?, verification_expiry = ? WHERE email = ?",
            (verification_code, expiry_time, email)
        )
        await db.commit()
        
        logger.info(f"Verification code updated successfully for: {email}")
        return True
    except Exception as e:
        logger.error(f"Error updating verification code: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# User image limits and rate limiting
async def check_and_update_daily_limit(db, user_id):
    """Check if user has images remaining for the day and reset if needed."""
    try:
        # Check current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get user's last reset date and remaining images
        async with db.execute(
            "SELECT last_reset_date, remaining_images FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            user_data = await cursor.fetchone()
            
        if not user_data:
            logger.warning(f"User not found for limit check: {user_id}")
            return False, "User not found"
        
        last_reset_date = user_data['last_reset_date']
        remaining_images = user_data['remaining_images']
        
        # Reset counter if it's a new day
        if last_reset_date != current_date:
            logger.info(f"Resetting daily image count for user: {user_id}")
            await db.execute(
                "UPDATE users SET last_reset_date = ?, remaining_images = 50 WHERE id = ?",
                (current_date, user_id)
            )
            await db.commit()
            remaining_images = 50
        
        # Check if user has images remaining
        if remaining_images <= 0:
            logger.warning(f"Daily limit reached for user: {user_id}")
            return False, f"Daily limit reached. Try again tomorrow."
        
        return True, remaining_images
    except Exception as e:
        logger.error(f"Error checking daily limit: {str(e)}")
        logger.error(traceback.format_exc())
        return False, f"Error checking limit: {str(e)}"

async def decrement_image_count(db, user_id):
    """Decrement the user's remaining image count for the day."""
    try:
        logger.debug(f"Decrementing image count for user: {user_id}")
        await db.execute(
            "UPDATE users SET remaining_images = remaining_images - 1 WHERE id = ?",
            (user_id,)
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Error decrementing image count: {str(e)}")
        logger.error(traceback.format_exc())

async def get_remaining_images(db, user_id):
    """Get the number of remaining images for a user."""
    try:
        # Check current date first to reset if needed
        await check_and_update_daily_limit(db, user_id)
        
        # Get remaining images
        async with db.execute(
            "SELECT remaining_images FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            user_data = await cursor.fetchone()
            
        if not user_data:
            logger.warning(f"User not found for remaining images check: {user_id}")
            return 0
            
        return user_data['remaining_images']
    except Exception as e:
        logger.error(f"Error getting remaining images: {str(e)}")
        logger.error(traceback.format_exc())
        return 0

async def check_rate_limit(db, user_id):
    """Check if user is within rate limit (10 seconds between generations)."""
    try:
        # Check if user has a rate limit entry
        async with db.execute(
            "SELECT last_generation_time FROM rate_limits WHERE user_id = ?", (user_id,)
        ) as cursor:
            rate_data = await cursor.fetchone()
        
        current_time = datetime.now()
        
        if not rate_data:
            # First generation, create entry
            logger.debug(f"Creating first rate limit entry for user: {user_id}")
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
            logger.debug(f"Rate limit reached for user: {user_id}, wait time: {10 - int(time_diff)}s")
            return False, 10 - int(time_diff)
        
        # Update the last generation time
        await db.execute(
            "UPDATE rate_limits SET last_generation_time = ? WHERE user_id = ?",
            (current_time, user_id)
        )
        await db.commit()
        
        return True, 0
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}")
        logger.error(traceback.format_exc())
        return False, 10  # Default to rate limited in case of error

# Image model operations
async def save_image(db, user_id: int, prompt: str, translated_prompt: str, 
                    file_path: str, width: int, height: int):
    """Save a generated image to the database."""
    try:
        logger.info(f"Saving image for user: {user_id}")
        cursor = await db.execute(
            """
            INSERT INTO images (user_id, prompt, translated_prompt, file_path, width, height)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, prompt, translated_prompt, file_path, width, height)
        )
        await db.commit()
        image_id = cursor.lastrowid
        logger.info(f"Image saved with ID: {image_id}")
        return image_id
    except Exception as e:
        logger.error(f"Error saving image: {str(e)}")
        logger.error(traceback.format_exc())
        raise

async def get_user_images(db, user_id: int):
    """Get all images for a specific user."""
    try:
        logger.debug(f"Getting images for user: {user_id}")
        async with db.execute(
            "SELECT * FROM images WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ) as cursor:
            images = await cursor.fetchall()
            logger.debug(f"Found {len(images)} images for user: {user_id}")
            return images
    except Exception as e:
        logger.error(f"Error getting user images: {str(e)}")
        logger.error(traceback.format_exc())
        return []

async def get_image(db, image_id: int):
    """Get an image by ID."""
    try:
        logger.debug(f"Getting image by ID: {image_id}")
        async with db.execute(
            "SELECT * FROM images WHERE id = ?", (image_id,)
        ) as cursor:
            return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting image: {str(e)}")
        logger.error(traceback.format_exc())
        return None