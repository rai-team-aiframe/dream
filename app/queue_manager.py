import asyncio
import os
import time
from datetime import datetime
import logging
from typing import Dict, Optional, List

from . import database
from . import image_generator
from . import translator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("queue_manager")

# Queue manager singleton
class QueueManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QueueManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        """Initialize the queue manager."""
        self.processing_task = None
        self.is_running = False
        self.current_task_id = None
        self.last_task_time = 0
        self.tasks_processed = 0
        self.last_user_id = None
    
    async def start(self):
        """Start the queue processing loop."""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Starting queue processing loop")
        
        # Start the processing task
        self.processing_task = asyncio.create_task(self._process_queue())
    
    async def stop(self):
        """Stop the queue processing loop."""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Stopping queue processing loop")
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                logger.info("Queue processing task cancelled")
    
    async def _process_queue(self):
        """Process tasks in the queue."""
        try:
            while self.is_running:
                async for db in database.get_db():
                    # Get the next pending task (ordered by priority)
                    task = await database.get_next_pending_task(db)
                    
                    if task:
                        # Get the user's plan details
                        user_id = task['user_id']
                        plan_details = await database.get_user_plan_details(db, user_id)
                        queue_wait = plan_details["queue_wait"]
                        
                        # Check if we need to wait because we're processing tasks for different users
                        current_time = time.time()
                        time_since_last = current_time - self.last_task_time
                        
                        if self.last_user_id is not None and self.last_user_id != user_id and time_since_last < queue_wait:
                            # Wait between users based on the plan's queue wait time
                            await asyncio.sleep(queue_wait - time_since_last)
                        
                        # Process the task
                        await self._process_task(task)
                        
                        # Update last task time, count, and user_id
                        self.last_task_time = time.time()
                        self.tasks_processed += 1
                        self.last_user_id = user_id
                    else:
                        # No pending tasks, wait before checking again
                        await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Queue processing loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in queue processing loop: {e}")
            self.is_running = False
            # Restart the processing task after a delay
            await asyncio.sleep(5)
            await self.start()
    
    async def _process_task(self, task):
        """Process a single queue task."""
        task_id = task['id']
        user_id = task['user_id']
        prompt = task['prompt']
        width = task['width']
        height = task['height']
        steps = task['steps']
        
        logger.info(f"Processing task {task_id} for user {user_id}")
        
        self.current_task_id = task_id
        
        try:
            async for db in database.get_db():
                # Update task status to processing
                await database.update_task_status(
                    db, 
                    task_id, 
                    'processing', 
                    started_at=datetime.now()
                )
                
                # Check if the user can generate (has tokens, not rate limited)
                can_generate, message = await database.check_user_can_generate(db, user_id)
                if not can_generate:
                    error_message = f"Cannot generate image: {message}"
                    logger.warning(f"Task {task_id}: {error_message}")
                    await database.update_task_status(
                        db, 
                        task_id, 
                        'failed', 
                        error_message=error_message,
                        completed_at=datetime.now()
                    )
                    return
                
                # Translate the prompt
                try:
                    translated_prompt = await translator.translate_to_english(prompt)
                except Exception as e:
                    logger.error(f"Translation error: {e}")
                    translated_prompt = prompt
                
                # Generate the image
                try:
                    file_path = await image_generator.generate_image(
                        prompt=translated_prompt,
                        width=width,
                        height=height,
                        steps=steps
                    )
                    
                    # Save the image in the database
                    image_id = await database.save_image(
                        db, 
                        user_id, 
                        prompt, 
                        translated_prompt, 
                        file_path, 
                        width, 
                        height
                    )
                    
                    # Decrement the user's daily image count
                    await database.decrement_image_count(db, user_id)
                    
                    # Update the queue task
                    await database.update_task_status(
                        db, 
                        task_id, 
                        'completed', 
                        completed_at=datetime.now(),
                        result_path=file_path
                    )
                    
                    logger.info(f"Task {task_id} completed successfully")
                    
                except Exception as e:
                    error_message = f"Image generation failed: {str(e)}"
                    logger.error(f"Task {task_id}: {error_message}")
                    await database.update_task_status(
                        db, 
                        task_id, 
                        'failed', 
                        error_message=error_message,
                        completed_at=datetime.now()
                    )
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
        finally:
            self.current_task_id = None
    
    async def add_task(self, user_id: int, prompt: str, width: int, height: int, steps: int) -> int:
        """
        Add a new task to the generation queue.
        
        Args:
            user_id: The ID of the user adding the task
            prompt: The image generation prompt
            width: The image width
            height: The image height
            steps: The number of generation steps
            
        Returns:
            int: The ID of the created task
        """
        async for db in database.get_db():
            # Check if the user can generate (has tokens, within rate limits)
            can_generate, message = await database.check_user_can_generate(db, user_id)
            if not can_generate:
                raise Exception(message)
                
            # Check if the user has any active tasks
            user_tasks = await database.get_user_queue_tasks(db, user_id)
            active_tasks = [t for t in user_tasks if t['status'] in ('pending', 'processing')]
            
            if active_tasks:
                # User already has tasks in the queue or processing
                existing_task_id = active_tasks[0]['id']
                logger.info(f"User {user_id} already has task {existing_task_id} in queue")
                return existing_task_id
            
            # Add the task to the queue
            task_id = await database.add_to_generation_queue(
                db, user_id, prompt, width, height, steps
            )
            
            logger.info(f"Added task {task_id} to queue for user {user_id}")
            
            # Make sure the queue processor is running
            if not self.is_running:
                await self.start()
            
            return task_id
    
    async def get_task_status(self, task_id: int) -> dict:
        """
        Get the status and details of a task.
        
        Args:
            task_id: The ID of the task
            
        Returns:
            dict: Task details including status and queue position
        """
        result = {
            'task_id': task_id,
            'status': 'unknown',
            'position': 0,
            'estimated_time': 0,
            'result_path': None,
            'error_message': None
        }
        
        async for db in database.get_db():
            task = await database.get_task_by_id(db, task_id)
            
            if not task:
                return result
            
            result['status'] = task['status']
            
            if task['status'] == 'pending':
                # Calculate position in queue
                position = await database.get_queue_position(db, task_id)
                result['position'] = position
                
                # Get the user's plan for queue wait time
                user_id = task['user_id']
                plan_details = await database.get_user_plan_details(db, user_id)
                queue_wait = plan_details["queue_wait"]
                
                # Estimate time: queue_wait seconds per task in front + processing time
                result['estimated_time'] = (position - 1) * queue_wait + plan_details["generation_wait"]
            
            elif task['status'] == 'processing':
                result['position'] = 0
                
                # Get the user's plan for generation wait time
                user_id = task['user_id']
                plan_details = await database.get_user_plan_details(db, user_id)
                result['estimated_time'] = plan_details["generation_wait"]
            
            elif task['status'] == 'completed':
                result['position'] = 0
                result['estimated_time'] = 0
                result['result_path'] = task['result_path']
            
            elif task['status'] == 'failed':
                result['position'] = 0
                result['estimated_time'] = 0
                result['error_message'] = task['error_message']
            
            return result

# Create the singleton instance
queue_manager = QueueManager()