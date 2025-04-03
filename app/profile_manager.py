import random
import string
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional

from . import database
from . import auth
from . import email_service

async def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))

async def request_password_change(db, user_id: int, email: str) -> Tuple[bool, str]:
    """
    Request a password change by sending a verification code.
    
    Args:
        db: Database connection
        user_id: User ID
        email: User's email
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Generate verification code
        code = await generate_verification_code()
        
        # Create verification record
        success = await database.create_profile_verification(
            db, 
            user_id, 
            "password_change", 
            code, 
            email
        )
        
        if not success:
            return False, "Failed to create verification request"
        
        # Get user info
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return False, "User not found"
        
        # Send email with verification code
        email_sent = email_service.send_profile_verification_email(
            email,
            user["username"],
            code,
            "Password Change"
        )
        
        if not email_sent:
            return False, "Failed to send verification email"
        
        return True, "Verification code sent to your email"
    
    except Exception as e:
        print(f"Error requesting password change: {e}")
        return False, f"Error: {str(e)}"

async def verify_and_change_password(db, user_id: int, code: str, new_password: str) -> Tuple[bool, str]:
    """
    Verify code and change user password.
    
    Args:
        db: Database connection
        user_id: User ID
        code: Verification code
        new_password: New password
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Verify the code
        success, verification = await database.verify_profile_code(db, user_id, "password_change", code)
        
        if not success:
            return False, "Invalid or expired verification code"
        
        # Hash the new password
        hashed_password = auth.get_password_hash(new_password)
        
        # Get current password
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return False, "User not found"
        
        old_password = user["hashed_password"]
        
        # Update the user's password
        success = await database.update_user_profile(db, user_id, hashed_password=hashed_password)
        
        if not success:
            return False, "Failed to update password"
        
        # Log the change
        await database.log_profile_change(
            db, 
            user_id, 
            "password_change", 
            "********", 
            "********"
        )
        
        return True, "Password updated successfully"
    
    except Exception as e:
        print(f"Error changing password: {e}")
        return False, f"Error: {str(e)}"

async def request_username_change(db, user_id: int, email: str, new_username: str) -> Tuple[bool, str]:
    """
    Request a username change by sending a verification code.
    
    Args:
        db: Database connection
        user_id: User ID
        email: User's email
        new_username: New username
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if the new username is already taken
        existing_user = await database.get_user_by_username(db, new_username)
        if existing_user:
            return False, "Username already taken"
        
        # Generate verification code
        code = await generate_verification_code()
        
        # Create verification record
        success = await database.create_profile_verification(
            db, 
            user_id, 
            "username_change", 
            code, 
            email,
            new_value=new_username
        )
        
        if not success:
            return False, "Failed to create verification request"
        
        # Get user info
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return False, "User not found"
        
        # Send email with verification code
        email_sent = email_service.send_profile_verification_email(
            email,
            user["username"],
            code,
            "Username Change"
        )
        
        if not email_sent:
            return False, "Failed to send verification email"
        
        return True, "Verification code sent to your email"
    
    except Exception as e:
        print(f"Error requesting username change: {e}")
        return False, f"Error: {str(e)}"

async def verify_and_change_username(db, user_id: int, code: str) -> Tuple[bool, str]:
    """
    Verify code and change username.
    
    Args:
        db: Database connection
        user_id: User ID
        code: Verification code
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Verify the code
        success, verification = await database.verify_profile_code(db, user_id, "username_change", code)
        
        if not success:
            return False, "Invalid or expired verification code"
        
        # Get the new username
        new_username = verification["new_value"]
        if not new_username:
            return False, "New username not found"
        
        # Get current username
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return False, "User not found"
        
        old_username = user["username"]
        
        # Double-check that the new username is still available
        existing_user = await database.get_user_by_username(db, new_username)
        if existing_user:
            return False, "Username already taken"
        
        # Update the username
        success = await database.update_user_profile(db, user_id, username=new_username)
        
        if not success:
            return False, "Failed to update username"
        
        # Log the change
        await database.log_profile_change(
            db, 
            user_id, 
            "username_change", 
            old_username, 
            new_username
        )
        
        return True, "Username updated successfully"
    
    except Exception as e:
        print(f"Error changing username: {e}")
        return False, f"Error: {str(e)}"

async def request_email_change(db, user_id: int, current_email: str, new_email: str) -> Tuple[bool, str]:
    """
    Request an email change by sending verification codes to both old and new emails.
    
    Args:
        db: Database connection
        user_id: User ID
        current_email: Current email
        new_email: New email
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if the new email is already taken
        existing_user = await database.get_user_by_email(db, new_email)
        if existing_user:
            return False, "Email already registered"
        
        # Check email domain
        if not email_service.is_valid_email_domain(new_email):
            return False, "Only Gmail and Outlook email accounts are accepted"
        
        # Generate verification code
        code = await generate_verification_code()
        
        # Create verification record
        success = await database.create_profile_verification(
            db, 
            user_id, 
            "email_change", 
            code, 
            new_email,
            new_value=new_email
        )
        
        if not success:
            return False, "Failed to create verification request"
        
        # Get user info
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return False, "User not found"
        
        # Send email with verification code to the new email
        email_sent = email_service.send_profile_verification_email(
            new_email,
            user["username"],
            code,
            "Email Change Verification"
        )
        
        if not email_sent:
            return False, "Failed to send verification email"
        
        return True, "Verification code sent to your new email address"
    
    except Exception as e:
        print(f"Error requesting email change: {e}")
        return False, f"Error: {str(e)}"

async def verify_and_change_email(db, user_id: int, code: str) -> Tuple[bool, str]:
    """
    Verify code and change email.
    
    Args:
        db: Database connection
        user_id: User ID
        code: Verification code
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Verify the code
        success, verification = await database.verify_profile_code(db, user_id, "email_change", code)
        
        if not success:
            return False, "Invalid or expired verification code"
        
        # Get the new email
        new_email = verification["new_value"]
        if not new_email:
            return False, "New email not found"
        
        # Get current email
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return False, "User not found"
        
        old_email = user["email"]
        
        # Double-check that the new email is still available
        existing_user = await database.get_user_by_email(db, new_email)
        if existing_user:
            return False, "Email already registered"
        
        # Update the email
        success = await database.update_user_profile(db, user_id, email=new_email)
        
        if not success:
            return False, "Failed to update email"
        
        # Log the change
        await database.log_profile_change(
            db, 
            user_id, 
            "email_change", 
            old_email, 
            new_email
        )
        
        return True, "Email updated successfully"
    
    except Exception as e:
        print(f"Error changing email: {e}")
        return False, f"Error: {str(e)}"

async def get_user_profile_data(db, user_id: int) -> Dict[str, Any]:
    """
    Get complete profile data for a user.
    
    Args:
        db: Database connection
        user_id: User ID
        
    Returns:
        Dict containing user profile data
    """
    try:
        # Get basic user data
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return {}
        
        # Get user's plan details
        plan_details = await database.get_user_plan_details(db, user_id)
        
        # Get token balance
        token_balance = await database.get_user_tokens(db, user_id)
        
        # Get image count
        images = await database.get_user_images(db, user_id)
        
        # Get payment history
        payments = await database.get_user_payments(db, user_id)
        
        # Prepare the result
        result = {
            "user_id": user_id,
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"],
            "plan": {
                "name": plan_details["name"],
                "plan_id": user["plan"],
                "generation_wait": plan_details["generation_wait"],
                "queue_wait": plan_details["queue_wait"],
            },
            "tokens": {
                "balance": token_balance,
                "cost_per_image": database.IMAGE_TOKEN_COST
            },
            "stats": {
                "total_images": len(images),
                "tokens_spent": sum(img["tokens_used"] for img in images) if images else 0,
                "last_image": images[0]["created_at"] if images else None
            },
            "payments": [
                {
                    "id": payment["id"],
                    "amount": payment["amount"],
                    "tokens": payment["tokens_purchased"],
                    "date": payment["payment_date"],
                    "status": payment["status"],
                    "plan": payment["plan_purchased"]
                }
                for payment in payments
            ] if payments else []
        }
        
        return result
    
    except Exception as e:
        print(f"Error getting user profile data: {e}")
        return {}