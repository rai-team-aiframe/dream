/**
 * DreamMaker - Profile Management Scripts
 * Handles user profile updates and verification processes
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const usernameForm = document.getElementById('username-form');
    const emailForm = document.getElementById('email-form');
    const passwordForm = document.getElementById('password-form');
    const verificationForm = document.getElementById('verification-form');
    const verificationModal = document.getElementById('verification-modal');
    const verificationTypeInput = document.getElementById('verification-type');
    const modalClose = document.querySelector('.modal-close');
    
    // Password toggle functionality
    const togglePasswordButtons = document.querySelectorAll('.toggle-password');
    togglePasswordButtons.forEach(button => {
        button.addEventListener('click', function() {
            const passwordInput = this.previousElementSibling;
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.classList.toggle('fa-eye');
            this.classList.toggle('fa-eye-slash');
        });
    });
    
    // Close modal when clicking the close button
    if (modalClose) {
        modalClose.addEventListener('click', function() {
            verificationModal.classList.remove('show');
        });
    }
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === verificationModal) {
            verificationModal.classList.remove('show');
        }
    });
    
    // Handle username change form
    if (usernameForm) {
        usernameForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const newUsername = document.getElementById('new-username').value;
            
            if (!newUsername) {
                showNotification('Please enter a new username', 'error');
                return;
            }
            
            // Set loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                const response = await fetch('/api/profile/request-username-change', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ new_username: newUsername })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to request username change');
                }
                
                // Show verification modal
                verificationTypeInput.value = 'username';
                verificationModal.classList.add('show');
                
                // Show success notification
                showNotification(data.detail, 'success');
                
            } catch (error) {
                console.error('Error requesting username change:', error);
                showNotification(error.message, 'error');
            } finally {
                setButtonLoading(submitButton, false);
            }
        });
    }
    
    // Handle email change form
    if (emailForm) {
        emailForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const newEmail = document.getElementById('new-email').value;
            
            if (!newEmail) {
                showNotification('Please enter a new email', 'error');
                return;
            }
            
            // Set loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                const response = await fetch('/api/profile/request-email-change', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ new_email: newEmail })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to request email change');
                }
                
                // Show verification modal
                verificationTypeInput.value = 'email';
                verificationModal.classList.add('show');
                
                // Show success notification
                showNotification(data.detail, 'success');
                
            } catch (error) {
                console.error('Error requesting email change:', error);
                showNotification(error.message, 'error');
            } finally {
                setButtonLoading(submitButton, false);
            }
        });
    }
    
    // Handle password change form
    if (passwordForm) {
        passwordForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const currentPassword = document.getElementById('current-password').value;
            const newPassword = document.getElementById('new-password').value;
            const confirmPassword = document.getElementById('confirm-new-password').value;
            
            if (!currentPassword || !newPassword || !confirmPassword) {
                showNotification('Please fill in all password fields', 'error');
                return;
            }
            
            if (newPassword !== confirmPassword) {
                showNotification('New passwords do not match', 'error');
                return;
            }
            
            // Set loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                const response = await fetch('/api/profile/request-password-change', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword
                    })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to request password change');
                }
                
                // Show verification modal
                verificationTypeInput.value = 'password';
                verificationModal.classList.add('show');
                
                // Show success notification
                showNotification(data.detail, 'success');
                
            } catch (error) {
                console.error('Error requesting password change:', error);
                showNotification(error.message, 'error');
            } finally {
                setButtonLoading(submitButton, false);
            }
        });
    }
    
    // Handle verification code form
    if (verificationForm) {
        verificationForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const code = document.getElementById('verification-code').value;
            const verificationType = verificationTypeInput.value;
            
            if (!code) {
                showNotification('Please enter the verification code', 'error');
                return;
            }
            
            // Set loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                let url = '';
                let data = { code: code };
                
                // Determine which endpoint to call based on verification type
                switch (verificationType) {
                    case 'username':
                        url = '/api/profile/verify-username-change';
                        break;
                    case 'email':
                        url = '/api/profile/verify-email-change';
                        break;
                    case 'password':
                        url = '/api/profile/verify-password-change';
                        data.new_password = document.getElementById('new-password').value;
                        break;
                    default:
                        throw new Error('Unknown verification type');
                }
                
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                const responseData = await response.json();
                
                if (!response.ok) {
                    throw new Error(responseData.detail || 'Verification failed');
                }
                
                // Close the verification modal
                verificationModal.classList.remove('show');
                
                // Show success notification
                showNotification(responseData.detail, 'success');
                
                // Reset form fields
                document.getElementById('verification-code').value = '';
                
                // Reset the original form fields
                if (verificationType === 'username') {
                    document.getElementById('new-username').value = '';
                } else if (verificationType === 'email') {
                    document.getElementById('new-email').value = '';
                } else if (verificationType === 'password') {
                    document.getElementById('current-password').value = '';
                    document.getElementById('new-password').value = '';
                    document.getElementById('confirm-new-password').value = '';
                }
                
                // Reload page after success to show updated information
                setTimeout(() => {
                    location.reload();
                }, 2000);
                
            } catch (error) {
                console.error('Error during verification:', error);
                showNotification(error.message, 'error');
            } finally {
                setButtonLoading(submitButton, false);
            }
        });
    }
    
    // Helper function to set button loading state
    function setButtonLoading(button, isLoading) {
        if (isLoading) {
            button.classList.add('loading');
            button.disabled = true;
        } else {
            button.classList.remove('loading');
            button.disabled = false;
        }
    }
    
    // Helper function to show notifications
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
});