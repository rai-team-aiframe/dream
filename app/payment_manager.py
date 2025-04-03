import random
import string
from datetime import datetime
from typing import Tuple, Dict, Any, Optional, List  # Added List here

from . import database
from . import email_service

async def purchase_token_package(db, user_id: int, package_id: str) -> Tuple[bool, str, Optional[int]]:
    """
    Process a token package purchase.
    
    Args:
        db: Database connection
        user_id: User ID
        package_id: Token package ID (e.g., 'small', 'medium', 'large')
        
    Returns:
        Tuple of (success, message, payment_id)
    """
    try:
        # Check if package exists
        if package_id not in database.TOKEN_PACKAGES:
            return False, "Invalid token package", None
        
        # Get package details
        package = database.TOKEN_PACKAGES[package_id]
        
        # Create payment record
        payment_id = await database.create_payment(
            db, 
            user_id, 
            package["price"], 
            package["tokens"]
        )
        
        if not payment_id:
            return False, "Failed to create payment record", None
        
        # In a real-world scenario, you would redirect to a payment gateway here
        # For this example, we'll simulate a successful payment
        
        # Simulate payment processing
        transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        # Update payment status
        await database.update_payment_status(db, payment_id, "completed", transaction_id)
        
        # Add tokens to user's account
        added = await database.add_user_tokens(db, user_id, package["tokens"])
        if not added:
            return False, "Failed to add tokens to your account", payment_id
        
        # Get user for email
        user = await database.get_user_by_id(db, user_id)
        if user:
            # Send confirmation email
            email_service.send_payment_confirmation_email(
                user["email"],
                user["username"],
                package["price"],
                package["tokens"]
            )
        
        return True, f"Successfully purchased {package['tokens']} tokens", payment_id
    
    except Exception as e:
        print(f"Error purchasing token package: {e}")
        return False, f"Error: {str(e)}", None

async def upgrade_user_plan(db, user_id: int, plan_id: str) -> Tuple[bool, str, Optional[int]]:
    """
    Process a plan upgrade.
    
    Args:
        db: Database connection
        user_id: User ID
        plan_id: Plan ID (e.g., 'premium', 'pro')
        
    Returns:
        Tuple of (success, message, payment_id)
    """
    try:
        # Check if plan exists
        if plan_id not in database.PLANS or plan_id == database.PLAN_FREE:
            return False, "Invalid plan", None
        
        # Get plan details
        plan = database.PLANS[plan_id]
        
        # Check user's current plan
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return False, "User not found", None
        
        if user["plan"] == plan_id:
            return False, "You already have this plan", None
        
        # Create payment record
        payment_id = await database.create_payment(
            db, 
            user_id, 
            plan["price"], 
            plan["tokens"],
            plan=plan_id
        )
        
        if not payment_id:
            return False, "Failed to create payment record", None
        
        # In a real-world scenario, you would redirect to a payment gateway here
        # For this example, we'll simulate a successful payment
        
        # Simulate payment processing
        transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        # Update payment status
        await database.update_payment_status(db, payment_id, "completed", transaction_id)
        
        # Update user's plan
        success, message = await database.update_user_plan(db, user_id, plan_id)
        if not success:
            return False, message, payment_id
        
        # Add tokens to user's account
        added = await database.add_user_tokens(db, user_id, plan["tokens"])
        if not added:
            return False, "Failed to add tokens to your account", payment_id
        
        # Send confirmation email
        if user:
            email_service.send_payment_confirmation_email(
                user["email"],
                user["username"],
                plan["price"],
                plan["tokens"],
                plan=plan["name"]
            )
        
        return True, f"Successfully upgraded to {plan['name']} plan", payment_id
    
    except Exception as e:
        print(f"Error upgrading plan: {e}")
        return False, f"Error: {str(e)}", None

async def get_available_plans(db, user_id: int) -> Dict[str, Any]:
    """
    Get available plans with user's current plan highlighted.
    
    Args:
        db: Database connection
        user_id: User ID
        
    Returns:
        Dict with plans and user's current plan
    """
    try:
        # Get user's current plan
        user = await database.get_user_by_id(db, user_id)
        if not user:
            return {"plans": database.PLANS, "current_plan": database.PLAN_FREE}
        
        current_plan = user["plan"]
        
        # Return all plans with current plan marked
        return {
            "plans": database.PLANS,
            "current_plan": current_plan
        }
    
    except Exception as e:
        print(f"Error getting available plans: {e}")
        return {"plans": database.PLANS, "current_plan": database.PLAN_FREE}

async def get_token_packages() -> Dict[str, Any]:
    """
    Get available token packages.
    
    Returns:
        Dict with token packages
    """
    return database.TOKEN_PACKAGES

async def get_payment_history(db, user_id: int) -> List[Dict[str, Any]]:
    """
    Get payment history for a user.
    
    Args:
        db: Database connection
        user_id: User ID
        
    Returns:
        List of payment records
    """
    try:
        payments = await database.get_user_payments(db, user_id)
        
        return [
            {
                "id": payment["id"],
                "amount": payment["amount"],
                "tokens": payment["tokens_purchased"],
                "date": payment["payment_date"],
                "status": payment["status"],
                "transaction_id": payment["transaction_id"],
                "plan": payment["plan_purchased"]
            }
            for payment in payments
        ] if payments else []
    
    except Exception as e:
        print(f"Error getting payment history: {e}")
        return []