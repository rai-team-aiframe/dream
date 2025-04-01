import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email configuration
SENDER_EMAIL = "manager@aiframe.org"
SENDER_PASSWORD = "YiHnZfZvDsdF"
SMTP_SERVER = "smtp.zoho.eu"
SMTP_PORT = 465

def generate_verification_code():
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(recipient_email, username, verification_code):
    """
    Send a verification email with the provided code.
    
    Args:
        recipient_email: The recipient's email address
        username: The username of the new user
        verification_code: The verification code to include in the email
    
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        # Create the email message
        msg = MIMEMultipart()
        msg["Subject"] = "Verify Your DreamMaker Account"
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email

        # HTML email body with better styling
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Helvetica', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                    border-radius: 10px;
                }}
                .header {{
                    text-align: center;
                    padding: 20px 0;
                    background: linear-gradient(45deg, #7c3aed, #8b5cf6);
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    color: white;
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    padding: 30px;
                    background-color: white;
                    border-radius: 0 0 10px 10px;
                }}
                .code {{
                    font-size: 28px;
                    font-weight: bold;
                    text-align: center;
                    letter-spacing: 5px;
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #f0f0f0;
                    border-radius: 5px;
                }}
                .footer {{
                    text-align: center;
                    font-size: 12px;
                    color: #666666;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>DreamMaker</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>Thank you for creating an account with DreamMaker. To complete your registration, please enter the verification code below:</p>
                    <div class="code">{verification_code}</div>
                    <p>If you didn't request this verification code, you can safely ignore this email.</p>
                    <p>Happy creating!</p>
                    <p>The DreamMaker Team</p>
                </div>
                <div class="footer">
                    <p>&copy; 2025 DreamMaker. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Attach HTML content
        msg.attach(MIMEText(html, 'html'))

        # Connect to Zoho SMTP server and send the email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        return False

def is_valid_email_domain(email):
    """
    Check if the email domain is valid (only Gmail and Outlook are accepted).
    
    Args:
        email: The email address to check
    
    Returns:
        bool: True if the email domain is valid, False otherwise
    """
    valid_domains = [
        'gmail.com', 
        'outlook.com', 
        'hotmail.com', 
        'live.com', 
        'msn.com', 
        'outlook.it',
        'outlook.de',
        'outlook.fr',
        'outlook.es'
    ]
    
    try:
        domain = email.lower().split('@')[1]
        return domain in valid_domains
    except (IndexError, AttributeError):
        return False