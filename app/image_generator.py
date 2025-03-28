import os
import base64
from datetime import datetime
import uuid
from PIL import Image
import io
from together import Together

# API key directly in the code as per requirements (not using .env)
API_KEY = "d292b79dda4f87085a633743a84dcc46ab4d70fdee4b25b7acb4691b80c7ad92"

# Create the client
client = Together(api_key=API_KEY)

# Ensure images directory exists
os.makedirs("static/images/generated", exist_ok=True)

async def generate_image(prompt: str, width: int = 1024, height: int = 1024, steps: int = 4) -> str:
    """
    Generate an image using the Together AI API.
    
    Args:
        prompt: The text prompt to generate the image from
        width: Image width (max 1440)
        height: Image height (max 1440)
        steps: Number of inference steps
        
    Returns:
        Path to the saved image file
    """
    # Ensure dimensions don't exceed limits
    width = min(width, 1440)
    height = min(height, 1440)
    
    try:
        # Generate the image
        response = client.images.generate(
            prompt=prompt,
            model="black-forest-labs/FLUX.1-schnell-Free",
            width=width,
            height=height,
            steps=steps,
            n=1,
            response_format="b64_json",
            stop=[]
        )
        
        # Get the base64-encoded image
        b64_image = response.data[0].b64_json
        
        # Decode and save the image
        image_data = base64.b64decode(b64_image)
        image = Image.open(io.BytesIO(image_data))
        
        # Create a unique filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_name = f"{timestamp}_{unique_id}.png"
        file_path = os.path.join("static/images/generated", file_name)
        
        # Save the image
        image.save(file_path)
        
        return file_path
    except Exception as e:
        print(f"Error generating image: {e}")
        raise