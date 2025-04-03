/**
 * DreamMaker - Studio Scripts
 * Handles image generation and UI interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const sidebarToggle = document.querySelector('.toggle-sidebar');
    const sidebar = document.querySelector('.sidebar');
    const userButton = document.querySelector('.user-button');
    const userDropdown = document.querySelector('.user-dropdown');
    const logoutBtn = document.getElementById('logout-btn');
    const mobileLogout = document.getElementById('mobile-logout');
    const imageGeneratorForm = document.getElementById('image-generator-form');
    const resultCard = document.getElementById('result-card');
    const widthInput = document.getElementById('width');
    const heightInput = document.getElementById('height');
    const widthValue = document.getElementById('width-value');
    const heightValue = document.getElementById('height-value');
    const downloadBtn = document.getElementById('download-btn');
    const newImageBtn = document.getElementById('new-image-btn');
    const galleryItems = document.querySelectorAll('.gallery-item');
    const downloadGalleryBtns = document.querySelectorAll('.download-gallery-image');
    const queueStatus = document.getElementById('queue-status');
    const queuePosition = document.getElementById('queue-position');
    const estimatedTime = document.getElementById('estimated-time');
    const queueProgress = document.getElementById('queue-progress');
    const remainingImages = document.getElementById('remaining-images');
    const loaderMessage = document.getElementById('loader-message');
    const activeTaskInfo = document.querySelector('.active-task-info');
    
    // Current image data
    let currentImageId = null;
    
    // Queue polling
    let pollingInterval = null;
    let currentTaskId = null;
    
    // Check for active task on page load
    if (activeTaskInfo) {
        const taskId = activeTaskInfo.getAttribute('data-task-id');
        if (taskId) {
            currentTaskId = taskId;
            showResultCardWithLoading();
            startPollingTaskStatus(taskId);
        }
    }
    
    // Toggle sidebar
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
        });
    }
    
    // Toggle user dropdown
    if (userButton) {
        userButton.addEventListener('click', function(e) {
            e.stopPropagation();
            userDropdown.classList.toggle('show');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function() {
            if (userDropdown.classList.contains('show')) {
                userDropdown.classList.remove('show');
            }
        });
    }
    
    // Handle logout
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
    
    if (mobileLogout) {
        mobileLogout.addEventListener('click', logout);
    }
    
    // Slider input changes
    if (widthInput) {
        widthInput.addEventListener('input', function() {
            widthValue.textContent = this.value;
        });
    }
    
    if (heightInput) {
        heightInput.addEventListener('input', function() {
            heightValue.textContent = this.value;
        });
    }
    
    // Periodically check remaining images
    function startRemainingImagesCheck() {
        // Initial check
        checkRemainingImages();
        
        // Check every 30 seconds
        setInterval(checkRemainingImages, 30000);
    }
    
    async function checkRemainingImages() {
        try {
            const response = await fetch('/api/remaining-images', {
                method: 'GET',
                credentials: 'include'
            });
            
            if (!response.ok) {
                console.error('Failed to get remaining images');
                return;
            }
            
            const data = await response.json();
            
            // Update the UI
            remainingImages.textContent = data.remaining_images;
            
            // Enable/disable the form submit button based on remaining images
            const submitButton = imageGeneratorForm.querySelector('button[type="submit"]');
            
            if (data.remaining_images <= 0) {
                submitButton.disabled = true;
                submitButton.title = "Daily limit reached";
            } else if (data.rate_limited) {
                submitButton.disabled = true;
                submitButton.title = `Wait ${data.wait_time} seconds before next generation`;
                
                // Enable after wait time
                setTimeout(() => {
                    submitButton.disabled = false;
                    submitButton.title = "";
                    showNotification("You can generate a new image now!", "info");
                }, data.wait_time * 1000);
            } else if (!currentTaskId) {
                submitButton.disabled = false;
                submitButton.title = "";
            }
        } catch (error) {
            console.error('Error checking remaining images:', error);
        }
    }
    
    // Start checking remaining images
    if (remainingImages) {
        startRemainingImagesCheck();
    }
    
    // Image generation form
    if (imageGeneratorForm) {
        imageGeneratorForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Get form values
            const prompt = document.getElementById('prompt').value;
            const width = parseInt(widthInput.value);
            const height = parseInt(heightInput.value);
            
            // Validate inputs
            if (!prompt.trim()) {
                showNotification('Please enter a description for your image', 'error');
                return;
            }
            
            // Start loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                // Show result card with loading state
                showResultCardWithLoading();
                
                // Set initial details
                document.getElementById('result-prompt').textContent = prompt;
                document.getElementById('result-dimensions').textContent = `${width}px × ${height}px`;
                
                // Make API request to queue generation
                const response = await fetch('/api/generate-image', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        prompt,
                        width,
                        height,
                        steps: 4 // Default steps
                    }),
                    credentials: 'include' // Include cookies in the request
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to generate image');
                }
                
                const data = await response.json();
                
                // If we have a task_id, start polling for status
                if (data.task_id) {
                    currentTaskId = data.task_id;
                    startPollingTaskStatus(data.task_id);
                    showNotification('Your image has been queued!', 'info');
                }
                
            } catch (error) {
                console.error('Error generating image:', error);
                showNotification(error.message, 'error');
                document.querySelector('.image-loader').style.display = 'none';
                submitButton.disabled = false;
            } finally {
                setButtonLoading(submitButton, false);
            }
        });
    }
    
    // Function to show result card with loading
    function showResultCardWithLoading() {
        resultCard.style.display = 'block';
        document.querySelector('.image-loader').style.display = 'flex';
        document.getElementById('result-image').style.opacity = '0';
        
        // Scroll to result card
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Function to start polling for task status
    function startPollingTaskStatus(taskId) {
        // Clear any existing interval
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
        
        // Show queue status
        queueStatus.style.display = 'block';
        
        // Initial poll
        pollTaskStatus(taskId);
        
        // Set interval for polling (every 2 seconds)
        pollingInterval = setInterval(() => pollTaskStatus(taskId), 2000);
    }
    
    // Function to poll for task status
    async function pollTaskStatus(taskId) {
        try {
            const response = await fetch(`/api/task-status/${taskId}`, {
                method: 'GET',
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error('Failed to get task status');
            }
            
            const data = await response.json();
            
            // Update UI based on status
            if (data.status === 'pending') {
                // Update queue position and estimated time
                queuePosition.textContent = data.position;
                estimatedTime.textContent = data.estimated_time;
                loaderMessage.textContent = 'Your image is in the queue...';
                
                // Update progress bar if we have position data
                if (data.position > 0 && data.estimated_time > 0) {
                    const maxEstimatedTime = data.position * 2 + 10; // Rough estimate
                    const progress = Math.max(0, (maxEstimatedTime - data.estimated_time) / maxEstimatedTime * 100);
                    queueProgress.style.width = `${progress}%`;
                }
            } 
            else if (data.status === 'processing') {
                // Show processing status
                queuePosition.textContent = 'Processing';
                estimatedTime.textContent = data.estimated_time;
                loaderMessage.textContent = 'Creating your masterpiece...';
                queueProgress.style.width = '75%';
            } 
            else if (data.status === 'completed') {
                // Task completed, show the result
                clearInterval(pollingInterval);
                currentTaskId = null;
                
                const resultImage = document.getElementById('result-image');
                resultImage.src = '/' + data.result_path;
                currentImageId = data.result_path.split('/').pop().split('_')[0]; // Extract image ID
                
                // Show the image when loaded
                resultImage.onload = function() {
                    document.querySelector('.image-loader').style.display = 'none';
                    resultImage.style.opacity = '1';
                    
                    // Enable the form button
                    const submitButton = imageGeneratorForm.querySelector('button[type="submit"]');
                    submitButton.disabled = false;
                    
                    // Success notification
                    showNotification('Image generated successfully!', 'success');
                    
                    // Update remaining images
                    checkRemainingImages();
                    
                    // Refresh the page after 3 seconds to update the gallery
                    setTimeout(() => {
                        location.reload();
                    }, 3000);
                };
            } 
            else if (data.status === 'failed') {
                // Task failed
                clearInterval(pollingInterval);
                currentTaskId = null;
                
                // Hide the loading overlay
                document.querySelector('.image-loader').style.display = 'none';
                
                // Show error message
                showNotification(`Generation failed: ${data.error_message}`, 'error');
                
                // Enable the form button
                const submitButton = imageGeneratorForm.querySelector('button[type="submit"]');
                submitButton.disabled = false;
            }
        } catch (error) {
            console.error('Error polling task status:', error);
        }
    }
    
    // Download button
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            if (currentImageId) {
                downloadImage(currentImageId);
            }
        });
    }
    
    // New image button
    if (newImageBtn) {
        newImageBtn.addEventListener('click', function() {
            // Hide result card and scroll to form
            resultCard.style.display = 'none';
            imageGeneratorForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
            
            // Optionally clear the form
            document.getElementById('prompt').value = '';
        });
    }
    
    // Download gallery images
    if (downloadGalleryBtns) {
        downloadGalleryBtns.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                const imageId = this.getAttribute('data-id');
                downloadImage(imageId);
            });
        });
    }
    
    // Helper Functions
    async function logout() {
        try {
            const response = await fetch('/api/logout', {
                method: 'POST'
            });
            
            if (response.ok) {
                window.location.href = '/login';
            }
        } catch (error) {
            console.error('Logout error:', error);
            showNotification('Failed to logout. Please try again.', 'error');
        }
    }
    
    function setButtonLoading(button, isLoading) {
        if (isLoading) {
            button.classList.add('loading');
            button.disabled = true;
        } else {
            button.classList.remove('loading');
            button.disabled = currentTaskId !== null;
        }
    }
    
    function showNotification(message, type = 'info') {
        const container = document.getElementById('notification-container');
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        
        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        if (type === 'error') icon = 'exclamation-circle';
        if (type === 'warning') icon = 'exclamation-triangle';
        
        notification.innerHTML = `
            <i class="fas fa-${icon} icon"></i>
            <div class="message">${message}</div>
        `;
        
        container.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Remove after 4 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                container.removeChild(notification);
            }, 300);
        }, 4000);
    }
    
    async function downloadImage(imageId) {
        try {
            window.location.href = `/api/download/${imageId}`;
            showNotification('Image download started', 'success');
        } catch (error) {
            console.error('Download error:', error);
            showNotification('Failed to download image', 'error');
        }
    }
    
    // Mobile sidebar toggle
    const mobileSidebarToggle = document.createElement('button');
    mobileSidebarToggle.className = 'mobile-menu-toggle';
    mobileSidebarToggle.innerHTML = '<i class="fas fa-bars"></i>';
    document.body.appendChild(mobileSidebarToggle);
    
    mobileSidebarToggle.addEventListener('click', function() {
        sidebar.classList.toggle('show');
        document.querySelector('.studio-container').classList.toggle('sidebar-open');
        
        // Change icon
        const icon = this.querySelector('i');
        if (sidebar.classList.contains('show')) {
            icon.className = 'fas fa-times';
        } else {
            icon.className = 'fas fa-bars';
        }
    });
    
    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 900 && 
            sidebar.classList.contains('show') && 
            !sidebar.contains(e.target) && 
            e.target !== mobileSidebarToggle &&
            !mobileSidebarToggle.contains(e.target)) {
            
            sidebar.classList.remove('show');
            document.querySelector('.studio-container').classList.remove('sidebar-open');
            mobileSidebarToggle.querySelector('i').className = 'fas fa-bars';
        }
    });
});