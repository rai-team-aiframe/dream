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
    
    // Current image data
    let currentImageId = null;
    
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
                resultCard.style.display = 'block';
                document.querySelector('.image-loader').style.display = 'flex';
                document.getElementById('result-image').style.opacity = '0';
                
                // Set initial details
                document.getElementById('result-prompt').textContent = prompt;
                document.getElementById('result-dimensions').textContent = `${width}px × ${height}px`;
                
                // Scroll to result card
                resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
                
                // Make API request
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
                
                // Update UI with the generated image
                const resultImage = document.getElementById('result-image');
                resultImage.src = '/' + data.file_path;
                currentImageId = data.id;
                
                // Hide loader when image is loaded
                resultImage.onload = function() {
                    document.querySelector('.image-loader').style.display = 'none';
                    resultImage.style.opacity = '1';
                    
                    // Success notification
                    showNotification('Image generated successfully!', 'success');
                    
                    // Update gallery (optional: could reload just the gallery section)
                    setTimeout(() => {
                        location.reload();
                    }, 3000);
                };
                
            } catch (error) {
                console.error('Error generating image:', error);
                showNotification(error.message, 'error');
                document.querySelector('.image-loader').style.display = 'none';
            } finally {
                setButtonLoading(submitButton, false);
            }
        });
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
            button.disabled = false;
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