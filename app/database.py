import aiosqlite
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

DATABASE_PATH = "dreammaker.db"

# Plan constants
PLAN_FREE = "free"
PLAN_PREMIUM = "premium"
PLAN_PRO = "pro"

# Plan definitions
PLANS = {
    PLAN_FREE: {
        "name": "Free",
        "generation_wait": 10,  # seconds between generations
        "queue_wait": 5,        # seconds between queue tasks
        "initial_tokens": 10,   # tokens given upon signup
        "price": 0,             # price in toman
        "description": "Basic plan with limited features"
    },
    PLAN_PREMIUM: {
        "name": "Premium",
        "generation_wait": 5,
        "queue_wait": 4,
        "tokens": 100,
        "price": 120000,  # ~120k toman
        "description": "Faster generation with more tokens"
    },
    PLAN_PRO: {
        "name": "Pro",
        "generation_wait": 4,
        "queue_wait": 3,
        "tokens": 250,
        "price": 270000,  # ~270k toman
        "description": "Our fastest plan with priority queue"
    }
}

# Token packages
TOKEN_PACKAGES = {
    "small": {
        "name": "Basic Package",
        "tokens": 50,
        "price": 70000,  # ~70k toman
        "description": "50 tokens for image generation"
    },
    "medium": {
        "name": "Standard Package",
        "tokens": 120,
        "price": 130000,  # ~130k toman
        "description": "120 tokens for image generation"
    },
    "large": {
        "name": "Premium Package",
        "tokens": 300,
        "price": 280000,  # ~280k toman
        "description": "300 tokens for image generation"
    }
}

# Image token cost
IMAGE_TOKEN_COST = 0.099  # Tokens per image generation

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
        # Create users table with additional fields
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_reset_date TEXT DEFAULT (strftime('%Y-%m-%d', 'now')),
            remaining_images INTEGER DEFAULT 10,
            token_balance REAL DEFAULT 10.0,
            plan TEXT DEFAULT 'free',
            has_selected_plan BOOLEAN DEFAULT FALSE,
            last_payment_date TIMESTAMP NULL
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
            tokens_used REAL DEFAULT 0.099,
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
        
        # Create verification codes table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            hashed_password TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, email)
        )
        """)
        
        # Create generation queue table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS generation_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            steps INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP NULL,
            completed_at TIMESTAMP NULL,
            result_path TEXT NULL,
            error_message TEXT NULL,
            priority INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        
        # Create payments table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            tokens_purchased REAL NOT NULL,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            transaction_id TEXT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            plan_purchased TEXT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        
        # Create profile_changes table for tracking changes
        await db.execute("""
        CREATE TABLE IF NOT EXISTS profile_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            old_value TEXT NOT NULL,
            new_value TEXT NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        
        # Create profile verification table for email/password changes
        await db.execute("""
        CREATE TABLE IF NOT EXISTS profile_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            verification_type TEXT NOT NULL,
            email TEXT NULL,
            code TEXT NOT NULL,
            new_value TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        
        await db.commit()

# User model operations
async def create_user(db, username: str, email: str, hashed_password: str, plan: str = PLAN_FREE):
    """Create a new user in the database."""
    try:
        # Get initial tokens based on plan
        initial_tokens = PLANS[plan]["initial_tokens"]
        
        cursor = await db.execute(
            """
            INSERT INTO users 
            (username, email, hashed_password, token_balance, plan, has_selected_plan) 
            VALUES (?, ?, ?, ?, ?, FALSE)
            """,
            (username, email, hashed_password, initial_tokens, plan)
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

async def update_user_profile(db, user_id: int, **kwargs):
    """Update user profile fields."""
    if not kwargs:
        return False
    
    # Prepare the SQL query
    fields = []
    values = []
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(value)
    
    # Add user_id to values
    values.append(user_id)
    
    # Build the query
    query = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
    
    try:
        await db.execute(query, values)
        await db.commit()
        return True
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return False

async def log_profile_change(db, user_id: int, change_type: str, old_value: str, new_value: str):
    """Log a profile change for audit purposes."""
    try:
        await db.execute(
            """
            INSERT INTO profile_changes 
            (user_id, change_type, old_value, new_value) 
            VALUES (?, ?, ?, ?)
            """,
            (user_id, change_type, old_value, new_value)
        )
        await db.commit()
        return True
    except Exception as e:
        print(f"Error logging profile change: {e}")
        return False

async def create_profile_verification(db, user_id: int, verification_type: str, 
                                     code: str, email: str = None, new_value: str = None,
                                     expiry_hours: int = 24):
    """Create a verification code for profile changes."""
    try:
        # Calculate expiry time
        now = datetime.now()
        expires_at = now + timedelta(hours=expiry_hours)
        
        # Delete any existing verification of the same type for this user
        await db.execute(
            "DELETE FROM profile_verifications WHERE user_id = ? AND verification_type = ?",
            (user_id, verification_type)
        )
        
        # Create new verification
        await db.execute(
            """
            INSERT INTO profile_verifications 
            (user_id, verification_type, email, code, new_value, expires_at) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, verification_type, email, code, new_value, expires_at)
        )
        await db.commit()
        return True
    except Exception as e:
        print(f"Error creating profile verification: {e}")
        return False

async def get_profile_verification(db, user_id: int, verification_type: str):
    """Get a profile verification code."""
    async with db.execute(
        """
        SELECT * FROM profile_verifications 
        WHERE user_id = ? AND verification_type = ? AND expires_at > datetime('now')
        """, 
        (user_id, verification_type)
    ) as cursor:
        return await cursor.fetchone()

async def verify_profile_code(db, user_id: int, verification_type: str, code: str):
    """Verify a profile verification code."""
    # Get the verification entry
    async with db.execute(
        """
        SELECT * FROM profile_verifications 
        WHERE user_id = ? AND verification_type = ? AND code = ? AND expires_at > datetime('now')
        """, 
        (user_id, verification_type, code)
    ) as cursor:
        verification = await cursor.fetchone()
    
    if not verification:
        return False, "Invalid or expired verification code"
    
    # Delete the verification record since it's been used
    await db.execute(
        "DELETE FROM profile_verifications WHERE id = ?", 
        (verification['id'],)
    )
    await db.commit()
    
    return True, verification

# User token operations
async def get_user_tokens(db, user_id: int):
    """Get the token balance for a user."""
    async with db.execute(
        "SELECT token_balance FROM users WHERE id = ?", (user_id,)
    ) as cursor:
        result = await cursor.fetchone()
        
    return result['token_balance'] if result else 0

async def add_user_tokens(db, user_id: int, tokens: float):
    """Add tokens to a user's balance."""
    try:
        await db.execute(
            "UPDATE users SET token_balance = token_balance + ? WHERE id = ?",
            (tokens, user_id)
        )
        await db.commit()
        return True
    except Exception as e:
        print(f"Error adding tokens: {e}")
        return False

async def use_user_tokens(db, user_id: int, tokens: float):
    """Use tokens from a user's balance."""
    # Check if user has enough tokens
    current_tokens = await get_user_tokens(db, user_id)
    if current_tokens < tokens:
        return False, "Insufficient tokens"
    
    try:
        await db.execute(
            "UPDATE users SET token_balance = token_balance - ? WHERE id = ?",
            (tokens, user_id)
        )
        await db.commit()
        return True, current_tokens - tokens
    except Exception as e:
        print(f"Error using tokens: {e}")
        return False, "Database error"

async def update_user_plan(db, user_id: int, plan: str):
    """Update a user's plan."""
    if plan not in PLANS:
        return False, "Invalid plan"
    
    try:
        # Get user's current plan
        async with db.execute(
            "SELECT plan FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            user_data = await cursor.fetchone()
        
        if not user_data:
            return False, "User not found"
        
        old_plan = user_data['plan']
        
        # Update the user's plan
        await db.execute(
            "UPDATE users SET plan = ?, has_selected_plan = TRUE, last_payment_date = datetime('now') WHERE id = ?",
            (plan, user_id)
        )
        await db.commit()
        
        # Log the plan change
        await log_profile_change(db, user_id, "plan_change", old_plan, plan)
        
        return True, "Plan updated successfully"
    except Exception as e:
        print(f"Error updating plan: {e}")
        return False, f"Database error: {str(e)}"

# Payment operations
async def create_payment(db, user_id: int, amount: int, tokens: float, plan: str = None):
    """Create a pending payment record."""
    try:
        cursor = await db.execute(
            """
            INSERT INTO payments 
            (user_id, amount, tokens_purchased, plan_purchased) 
            VALUES (?, ?, ?, ?)
            """,
            (user_id, amount, tokens, plan)
        )
        await db.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error creating payment: {e}")
        return None

async def update_payment_status(db, payment_id: int, status: str, transaction_id: str = None):
    """Update a payment's status."""
    try:
        if transaction_id:
            await db.execute(
                "UPDATE payments SET status = ?, transaction_id = ? WHERE id = ?",
                (status, transaction_id, payment_id)
            )
        else:
            await db.execute(
                "UPDATE payments SET status = ? WHERE id = ?",
                (status, payment_id)
            )
        await db.commit()
        return True
    except Exception as e:
        print(f"Error updating payment: {e}")
        return False

async def get_user_payments(db, user_id: int):
    """Get all payments for a user."""
    async with db.execute(
        """
        SELECT * FROM payments 
        WHERE user_id = ? 
        ORDER BY payment_date DESC
        """, 
        (user_id,)
    ) as cursor:
        return await cursor.fetchall()

async def get_payment(db, payment_id: int):
    """Get a payment by ID."""
    async with db.execute(
        "SELECT * FROM payments WHERE id = ?", (payment_id,)
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
            "UPDATE users SET last_reset_date = ?, remaining_images = 10 WHERE id = ?",
            (current_date, user_id)
        )
        await db.commit()
        remaining_images = 10
    
    # Check if user has images remaining
    if remaining_images <= 0:
        return False, f"Daily limit reached. Try again tomorrow."
    
    return True, remaining_images

async def check_user_can_generate(db, user_id: int):
    """Check if user has tokens and is within rate limits."""
    # Check token balance
    token_balance = await get_user_tokens(db, user_id)
    if token_balance < IMAGE_TOKEN_COST:
        return False, f"Insufficient tokens. You need {IMAGE_TOKEN_COST} tokens to generate an image."
    
    # Check daily limit 
    limit_ok, limit_info = await check_and_update_daily_limit(db, user_id)
    if not limit_ok:
        return False, limit_info
    
    # Check rate limit based on user's plan
    rate_ok, wait_time = await check_rate_limit(db, user_id)
    if not rate_ok:
        return False, f"Please wait {wait_time} seconds before generating another image"
    
    return True, "OK"

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

async def get_user_plan_details(db, user_id: int):
    """Get a user's plan details."""
    async with db.execute(
        "SELECT plan FROM users WHERE id = ?", (user_id,)
    ) as cursor:
        user_data = await cursor.fetchone()
    
    if not user_data:
        return PLANS[PLAN_FREE]
    
    plan = user_data['plan']
    return PLANS.get(plan, PLANS[PLAN_FREE])

async def check_rate_limit(db, user_id):
    """Check if user is within rate limit based on their plan."""
    # Get user's plan details
    plan_details = await get_user_plan_details(db, user_id)
    generation_wait = plan_details["generation_wait"]
    
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
    if time_diff < generation_wait:
        return False, generation_wait - int(time_diff)
    
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
    # Use tokens for the image
    token_result, _ = await use_user_tokens(db, user_id, IMAGE_TOKEN_COST)
    if not token_result:
        # This shouldn't happen as we check balance before generation, but just in case
        raise Exception("Insufficient tokens")
    
    cursor = await db.execute(
        """
        INSERT INTO images (user_id, prompt, translated_prompt, file_path, width, height, tokens_used)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, prompt, translated_prompt, file_path, width, height, IMAGE_TOKEN_COST)
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

# Queue operations
async def add_to_generation_queue(db, user_id: int, prompt: str, width: int, height: int, steps: int):
    """Add an image generation task to the queue."""
    # Get user's plan for priority
    async with db.execute(
        "SELECT plan FROM users WHERE id = ?", (user_id,)
    ) as cursor:
        user_data = await cursor.fetchone()
    
    # Set priority based on plan
    priority = 0  # Default for free plan
    if user_data:
        if user_data['plan'] == PLAN_PREMIUM:
            priority = 1
        elif user_data['plan'] == PLAN_PRO:
            priority = 2
    
    cursor = await db.execute(
        """
        INSERT INTO generation_queue (user_id, prompt, width, height, steps, priority)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, prompt, width, height, steps, priority)
    )
    await db.commit()
    return cursor.lastrowid

async def get_queue_position(db, task_id: int):
    """Get the position of a task in the queue."""
    # Get the task's priority
    async with db.execute(
        "SELECT priority FROM generation_queue WHERE id = ?", (task_id,)
    ) as cursor:
        task_data = await cursor.fetchone()
    
    if not task_data:
        return 0
    
    task_priority = task_data['priority']
    
    # Count tasks with higher or equal priority that were queued earlier
    async with db.execute(
        """
        SELECT COUNT(*) as position
        FROM generation_queue
        WHERE status = 'pending' 
        AND (
            (priority > ?) OR 
            (priority = ? AND id < ?)
        )
        """,
        (task_priority, task_priority, task_id)
    ) as cursor:
        position_data = await cursor.fetchone()
    
    return position_data['position'] + 1 if position_data else 0

async def get_next_pending_task(db):
    """Get the next pending task from the queue ordered by priority."""
    async with db.execute(
        """
        SELECT * FROM generation_queue
        WHERE status = 'pending'
        ORDER BY priority DESC, queued_at ASC
        LIMIT 1
        """
    ) as cursor:
        return await cursor.fetchone()

async def update_task_status(db, task_id: int, status: str, **kwargs):
    """Update the status of a queue task."""
    update_fields = ["status = ?"]
    params = [status]
    
    # Add additional fields to update
    for key, value in kwargs.items():
        update_fields.append(f"{key} = ?")
        params.append(value)
    
    # Add task_id to params
    params.append(task_id)
    
    # Build and execute query
    query = f"UPDATE generation_queue SET {', '.join(update_fields)} WHERE id = ?"
    await db.execute(query, params)
    await db.commit()

async def get_task_by_id(db, task_id: int):
    """Get a task by ID."""
    async with db.execute(
        "SELECT * FROM generation_queue WHERE id = ?", (task_id,)
    ) as cursor:
        return await cursor.fetchone()

async def get_user_queue_tasks(db, user_id: int):
    """Get all queue tasks for a specific user."""
    async with db.execute(
        """
        SELECT * FROM generation_queue 
        WHERE user_id = ? 
        ORDER BY queued_at DESC
        """, 
        (user_id,)
    ) as cursor:
        return await cursor.fetchall()

async def get_active_task_count(db):
    """Get the count of active tasks (pending or processing)."""
    async with db.execute(
        """
        SELECT COUNT(*) as count
        FROM generation_queue
        WHERE status IN ('pending', 'processing')
        """
    ) as cursor:
        count_data = await cursor.fetchone()
    
    return count_data['count'] if count_data else 0

# Verification code operations
async def save_verification_code(db, username: str, email: str, hashed_password: str, code: str):
    """
    Save a verification code for a new user.
    Replaces any existing code for the same username/email.
    
    Args:
        db: Database connection
        username: The username of the new user
        email: The email of the new user
        hashed_password: The hashed password of the new user
        code: The verification code
        
    Returns:
        int: ID of the verification record or None if failed
    """
    try:
        # Delete any existing verification for this user/email
        await db.execute(
            "DELETE FROM verification_codes WHERE username = ? OR email = ?",
            (username, email)
        )
        
        # Insert new verification code
        cursor = await db.execute(
            "INSERT INTO verification_codes (username, email, hashed_password, code) VALUES (?, ?, ?, ?)",
            (username, email, hashed_password, code)
        )
        await db.commit()
        return cursor.lastrowid
    except aiosqlite.IntegrityError:
        return None

async def get_verification_code(db, email: str):
    """
    Get the verification code for an email.
    
    Args:
        db: Database connection
        email: The email to get the verification code for
        
    Returns:
        dict: User details and verification code or None if not found
    """
    async with db.execute(
        "SELECT * FROM verification_codes WHERE email = ?", (email,)
    ) as cursor:
        return await cursor.fetchone()

async def verify_and_create_user(db, email: str, code: str):
    """
    Verify the code for an email and create the user if valid.
    
    Args:
        db: Database connection
        email: The email to verify
        code: The verification code
        
    Returns:
        tuple: (success, user_id or error message)
    """
    # Get the verification record
    async with db.execute(
        "SELECT * FROM verification_codes WHERE email = ?", (email,)
    ) as cursor:
        verification = await cursor.fetchone()
        
    if not verification:
        return False, "Verification not found"
        
    if verification['code'] != code:
        return False, "Invalid verification code"
    
    # Create the user account
    try:
        user_id = await create_user(
            db, 
            verification['username'], 
            verification['email'], 
            verification['hashed_password']
        )
        
        if not user_id:
            return False, "Failed to create user account"
        
        # Delete the verification record
        await db.execute(
            "DELETE FROM verification_codes WHERE id = ?", 
            (verification['id'],)
        )
        await db.commit()
        
        return True, user_id
    except aiosqlite.IntegrityError:
        return False, "Username or email already exists"