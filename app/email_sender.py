"""
Asynchronous email sending functionality for DreamMaker
"""
import random
import string
import asyncio
import aiosmtplib
import logging
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl

# Configure logging
logger = logging.getLogger("dreammaker.email")

# Email configuration
SENDER_EMAIL = "manager@aiframe.org"  # Replace with your Zoho email
SENDER_PASSWORD = "YiHnZfZvDsdF"  # Password 
SMTP_SERVER = "smtp.zoho.eu"  # Use smtppro.zoho.com for organization accounts
SMTP_PORT = 465  # Use 587 for TLS instead of SSL if preferred

def generate_verification_code(length=6):
    """Generate a random verification code"""
    code = ''.join(random.choices(string.digits, k=length))
    logger.info(f"Generated verification code: {code}")
    return code

async def send_verification_email(recipient_email, username, verification_code):
    """
    Send verification email to the user asynchronously
    
    Args:
        recipient_email (str): User's email address
        username (str): User's username
        verification_code (str): Verification code to send
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    logger.info(f"Sending verification email to: {recipient_email} with code: {verification_code}")
    
    # Create the email message
    msg = MIMEMultipart('alternative')
    msg["Subject"] = "Verify Your DreamMaker Account"
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient_email
    
    # Create HTML email content
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verify Your DreamMaker Account</title>
        <style>
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9f9f9;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 20px;
                padding-bottom: 20px;
                border-bottom: 1px solid #eee;
            }}
            .header h1 {{
                color: #7c3aed;
                margin: 0;
                font-size: 28px;
            }}
            .content {{
                padding: 20px 0;
            }}
            .verification-code {{
                font-size: 32px;
                letter-spacing: 5px;
                text-align: center;
                margin: 30px 0;
                color: #7c3aed;
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                font-size: 12px;
                color: #666;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
            }}
            .button {{
                display: inline-block;
                background-color: #7c3aed;
                color: white;
                padding: 12px 30px;
                border-radius: 50px;
                text-decoration: none;
                font-weight: bold;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>DreamMaker</h1>
            </div>
            <div class="content">
                <p>Hello {username},</p>
                <p>Thank you for signing up with DreamMaker! To complete your registration and start creating amazing AI-generated images, please verify your email address by entering the code below:</p>
                
                <div class="verification-code">{verification_code}</div>
                
                <p>This code will expire in 30 minutes for security reasons.</p>
                <p>If you didn't sign up for a DreamMaker account, you can safely ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; {2025} DreamMaker. All rights reserved.</p>
                <p>This is an automated message, please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Create plain text version for non-HTML mail clients
    text = f"""
    Hello {username},
    
    Thank you for signing up with DreamMaker!
    
    To complete your registration and start creating amazing AI-generated images, please verify your email address by entering this code: {verification_code}
    
    This code will expire in 30 minutes for security reasons.
    
    If you didn't sign up for a DreamMaker account, you can safely ignore this email.
    
    DreamMaker Team
    """
    
    # Attach parts
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)
    
    # Connect to SMTP server and send the email
    try:
        logger.info(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}")
        
        # Create SSL context for secure connection
        context = ssl.create_default_context()

        # Connect with SSL directly for port 465
        smtp = aiosmtplib.SMTP(hostname=SMTP_SERVER, port=SMTP_PORT, use_tls=True, tls_context=context)
        
        try:
            await smtp.connect()
            logger.info("SMTP connection established, logging in...")
            
            await smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            logger.info("SMTP login successful, sending email...")
            
            await smtp.send_message(msg)
            logger.info(f"Email sent successfully to {recipient_email}")
            
            await smtp.quit()
            logger.info("SMTP connection closed")
            
            return True
        except aiosmtplib.SMTPException as smtp_err:
            logger.error(f"SMTP Error: {str(smtp_err)}")
            logger.error(traceback.format_exc())
            return False
            
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def is_valid_email_domain(email):
    """Check if email is from Gmail or Outlook"""
    email = email.lower()
    is_valid = email.endswith('@gmail.com') or email.endswith('@outlook.com') or email.endswith('@hotmail.com')
    logger.info(f"Email domain validation for {email}: {is_valid}")
    return is_valid

# This function allows sending emails in batches asynchronously
async def send_emails_in_batch(email_tasks):
    """
    Send multiple emails asynchronously in a batch
    
    Args:
        email_tasks: List of tuples (recipient_email, username, verification_code)
        
    Returns:
        List of results (True/False for each email)
    """
    logger.info(f"Starting batch email sending for {len(email_tasks)} tasks")
    async_tasks = []
    for recipient, username, code in email_tasks:
        task = asyncio.create_task(send_verification_email(recipient, username, code))
        async_tasks.append(task)
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*async_tasks, return_exceptions=True)
    
    # Process results
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error sending to {email_tasks[i][0]}: {result}")
            final_results.append(False)
        else:
            final_results.append(result)
    
    logger.info(f"Batch email sending completed: {sum(final_results)}/{len(final_results)} successful")
    return final_results