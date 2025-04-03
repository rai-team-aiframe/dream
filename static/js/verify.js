/**
 * DreamMaker - Email Verification Scripts
 * Handles verification code submission and redirection
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const verificationForm = document.getElementById('verification-form');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const resendBtn = document.getElementById('resend-btn');
    const email = document.getElementById('email').value;
    
    // Handle form submission
    if (verificationForm) {
        verificationForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const code = document.getElementById('verification-code').value;
            
            if (!code || code.length !== 6) {
                showError('Please enter a valid 6-digit code');
                return;
            }
            
            // Set loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                const formData = new FormData();
                formData.append('email', email);
                formData.append('code', code);
                
                const response = await fetch('/api/verify-account', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to verify account');
                }
                
                // Show success message
                showSuccess('Account verified successfully!');
                
                // Redirect to plans page (will be mentioned in the response)
                if (data.redirect) {
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 1500);
                } else {
                    // Fallback to studio if no redirect is specified
                    setTimeout(() => {
                        window.location.href = '/studio';
                    }, 1500);
                }
                
            } catch (error) {
                console.error('Error verifying account:', error);
                showError(error.message);
                setButtonLoading(submitButton, false);
            }
        });
    }
    
    // Handle resend button
    if (resendBtn) {
        resendBtn.addEventListener('click', async function() {
            try {
                // Retrieve stored user details
                const userData = JSON.parse(localStorage.getItem('pendingUser'));
                
                if (!userData) {
                    showError('Unable to resend verification code. Please try signing up again.');
                    return;
                }
                
                const response = await fetch('/api/send-verification', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(userData)
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to resend verification code');
                }
                
                showSuccess('Verification code resent. Please check your email.');
                
            } catch (error) {
                showError(error.message);
            }
        });
    }
    
    // Helper functions
    function showError(message) {
        errorText.textContent = message;
        errorMessage.classList.remove('success-alert');
        errorMessage.classList.add('error-alert');
        errorMessage.style.display = 'flex';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorMessage.style.display = 'none';
        }, 5000);
    }
    
    function showSuccess(message) {
        errorText.textContent = message;
        errorMessage.classList.remove('error-alert');
        errorMessage.classList.add('success-alert');
        errorMessage.style.display = 'flex';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorMessage.style.display = 'none';
        }, 5000);
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
});