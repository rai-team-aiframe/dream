/**
 * DreamMaker - Authentication Scripts
 * Handles login, signup, and form validations
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get form elements
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    
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
    
    // Password strength indicator for signup
    if (signupForm) {
        const passwordInput = document.getElementById('password');
        const barLevel = document.getElementById('bar-level');
        const strengthText = document.getElementById('strength-text');
        const confirmPassword = document.getElementById('confirm-password');
        
        passwordInput.addEventListener('input', function() {
            const password = this.value;
            const strength = calculatePasswordStrength(password);
            
            // Update strength bar
            barLevel.style.width = strength.percent + '%';
            barLevel.className = 'bar-level ' + strength.level;
            strengthText.textContent = strength.message;
        });
        
        // Check password match
        confirmPassword.addEventListener('input', function() {
            if (this.value !== passwordInput.value) {
                this.setCustomValidity("Passwords don't match");
            } else {
                this.setCustomValidity('');
            }
        });
        
        // Handle signup form submission
        signupForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Simple validation
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = passwordInput.value;
            
            if (password !== confirmPassword.value) {
                showError('Passwords do not match');
                return;
            }
            
            // Set loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                // Store user data temporarily for potential resend
                const userData = {
                    username,
                    email,
                    password
                };
                localStorage.setItem('pendingUser', JSON.stringify(userData));
                
                const response = await fetch('/api/send-verification', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(userData)
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to create account');
                }
                
                // Redirect to verification page
                window.location.href = `/verify?email=${encodeURIComponent(email)}`;
                
            } catch (error) {
                showError(error.message);
                setButtonLoading(submitButton, false);
            }
        });
    }
    
    // Handle login form submission
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            // Set loading state
            const submitButton = this.querySelector('button[type="submit"]');
            setButtonLoading(submitButton, true);
            
            try {
                // Use FormData for OAuth2 password flow
                const formData = new FormData();
                formData.append('username', username);
                formData.append('password', password);
                
                const response = await fetch('/api/token', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to login');
                }
                
                // Redirect to studio page
                window.location.href = '/studio';
                
            } catch (error) {
                showError(error.message);
                setButtonLoading(submitButton, false);
            }
        });
        
        // Check for success message from signup
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('signup') === 'success') {
            showSuccess('Account created successfully! You can now log in.');
        }
    }
    
    // Helper functions
    function showError(message) {
        errorText.textContent = message;
        errorMessage.style.display = 'flex';
        errorMessage.classList.remove('success-alert');
        errorMessage.classList.add('error-alert');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorMessage.style.display = 'none';
        }, 5000);
    }
    
    function showSuccess(message) {
        errorMessage.classList.remove('error-alert');
        errorMessage.classList.add('success-alert');
        errorText.textContent = message;
        errorMessage.style.display = 'flex';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorMessage.style.display = 'none';
            errorMessage.classList.add('error-alert');
            errorMessage.classList.remove('success-alert');
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
    
    function calculatePasswordStrength(password) {
        let strength = {
            percent: 0,
            level: '',
            message: 'Password strength'
        };
        
        if (!password) {
            return strength;
        }
        
        let score = 0;
        
        // Length check
        if (password.length >= 8) score += 1;
        if (password.length >= 12) score += 1;
        
        // Complexity checks
        if (/[A-Z]/.test(password)) score += 1;  // Has uppercase
        if (/[a-z]/.test(password)) score += 1;  // Has lowercase
        if (/[0-9]/.test(password)) score += 1;  // Has number
        if (/[^A-Za-z0-9]/.test(password)) score += 1;  // Has special char
        
        // Determine strength level
        if (score <= 1) {
            strength.percent = 25;
            strength.level = 'weak';
            strength.message = 'Weak password';
        } else if (score <= 3) {
            strength.percent = 50;
            strength.level = 'medium';
            strength.message = 'Medium strength';
        } else if (score <= 5) {
            strength.percent = 75;
            strength.level = 'strong';
            strength.message = 'Strong password';
        } else {
            strength.percent = 100;
            strength.level = 'very-strong';
            strength.message = 'Very strong password';
        }
        
        return strength;
    }
});