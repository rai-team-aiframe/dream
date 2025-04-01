/**
 * DreamMaker - Email Verification Scripts
 * Handles verification code entry and submission
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Verification page loaded');
    
    // Get elements
    const verificationForm = document.getElementById('verification-form');
    const codeInputs = document.querySelectorAll('.code-input');
    const resendLink = document.getElementById('resend-code');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const successMessage = document.getElementById('success-message');
    const successText = document.getElementById('success-text');
    const countdownEl = document.getElementById('countdown');
    
    // Get email from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const email = urlParams.get('email') || '';
    console.log('Email from URL:', email);
    
    // Set user email in the header
    const userEmailEl = document.getElementById('user-email');
    if (userEmailEl) {
        userEmailEl.textContent = email;
    }
    
    // Setup code input behavior (auto-advance and handle backspace)
    codeInputs.forEach((input, index) => {
        input.addEventListener('keydown', function(e) {
            // Allow only numbers
            if (e.key !== 'Backspace' && e.key !== 'Delete' && e.key !== 'Tab' && 
                e.key !== 'ArrowLeft' && e.key !== 'ArrowRight' && 
                !/^[0-9]$/.test(e.key)) {
                e.preventDefault();
            }
            
            // Handle backspace
            if (e.key === 'Backspace' && !this.value) {
                if (index > 0) {
                    codeInputs[index - 1].focus();
                }
            }
        });
        
        input.addEventListener('input', function(e) {
            // Clear any non-numeric input
            this.value = this.value.replace(/[^0-9]/g, '');
            
            // Advance to next input when a digit is entered
            if (this.value && index < codeInputs.length - 1) {
                codeInputs[index + 1].focus();
            }
            
            // Auto-submit if all fields are filled
            if (index === codeInputs.length - 1 && this.value) {
                const allFilled = Array.from(codeInputs).every(input => input.value);
                if (allFilled) {
                    console.log('All code fields filled, auto-submitting...');
                    // Wait a moment to let the UI update
                    setTimeout(() => {
                        verificationForm.dispatchEvent(new Event('submit'));
                    }, 100);
                }
            }
        });
        
        // Allow paste into the first field to fill all inputs
        if (index === 0) {
            input.addEventListener('paste', function(e) {
                e.preventDefault();
                
                // Get pasted content
                const text = (e.clipboardData || window.clipboardData).getData('text');
                const numbers = text.replace(/[^0-9]/g, '');
                console.log('Pasted content (numbers only):', numbers);
                
                // Fill inputs
                for (let i = 0; i < Math.min(numbers.length, codeInputs.length); i++) {
                    codeInputs[i].value = numbers[i];
                }
                
                // Focus next empty input or the last one
                let focusIndex = Math.min(numbers.length, codeInputs.length - 1);
                codeInputs[focusIndex].focus();
                
                // Auto-submit if all fields are filled
                if (numbers.length >= codeInputs.length) {
                    console.log('All code fields filled from paste, auto-submitting...');
                    setTimeout(() => {
                        verificationForm.dispatchEvent(new Event('submit'));
                    }, 100);
                }
            });
        }
    });
    
    // Handle form submission
    verificationForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Get the verification code
        const code = Array.from(codeInputs).map(input => input.value).join('');
        console.log('Submitting verification code:', code);
        
        // Validate code
        if (code.length !== 6) {
            console.error('Validation error: Code must be 6 digits');
            showError('Please enter all 6 digits of the verification code');
            return;
        }
        
        // Set loading state
        const submitButton = this.querySelector('button[type="submit"]');
        setButtonLoading(submitButton, true);
        
        try {
            console.log(`Sending verification request to API - Email: ${email}, Code: ${code}`);
            
            const response = await fetch('/api/verify-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    code: code
                })
            });
            
            console.log('Response status:', response.status, response.statusText);
            
            // Try to get the response as text first
            const responseText = await response.text();
            console.log('Raw response:', responseText);
            
            // Try to parse it as JSON
            let data;
            try {
                data = JSON.parse(responseText);
                console.log('Parsed response data:', data);
            } catch (e) {
                console.error('Error parsing response JSON:', e);
                throw new Error('Invalid response format from server. Please try again.');
            }
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to verify email');
            }
            
            // Show success message and temporarily prevent form resubmission
            console.log('Verification successful');
            submitButton.disabled = true;
            showSuccess('Email verified successfully! Redirecting to login page...');
            
            // Redirect after a delay - use window.location.replace to prevent back button from returning to verify page
            setTimeout(() => {
                console.log('Redirecting to login page...');
                window.location.replace('/login?verified=true');
            }, 2000);
            
        } catch (error) {
            console.error('Verification error:', error);
            showError(error.message);
            setButtonLoading(submitButton, false);
        }
    });
    
    // Handle resend code
    resendLink.addEventListener('click', async function(e) {
        e.preventDefault();
        
        if (this.classList.contains('disabled')) {
            console.log('Resend link is disabled, ignoring click');
            return;
        }
        
        console.log('Resending verification code...');
        
        try {
            const response = await fetch('/api/resend-verification', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email
                })
            });
            
            console.log('Response status:', response.status);
            const data = await response.json();
            console.log('Response data:', data);
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to resend verification code');
            }
            
            // Show success message
            showSuccess('A new verification code has been sent to your email');
            
            // Reset countdown
            startCountdown(30 * 60); // 30 minutes
            
            // Disable resend link
            disableResendLink();
            
            // Clear the inputs
            codeInputs.forEach(input => {
                input.value = '';
            });
            codeInputs[0].focus();
            
        } catch (error) {
            console.error('Error resending code:', error);
            showError(error.message);
        }
    });
    
    // Start the countdown
    function startCountdown(seconds) {
        let timeLeft = seconds;
        console.log(`Starting countdown: ${seconds} seconds`);
        
        function updateCountdown() {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            
            // Update display
            countdownEl.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            
            if (timeLeft <= 0) {
                clearInterval(timer);
                countdownEl.textContent = '00:00';
                console.log('Countdown expired');
                countdownEl.parentElement.innerHTML = 'Code has expired. <a href="#" id="resend-new">Please request a new one</a>';
                
                // Add click handler for new link
                document.getElementById('resend-new').addEventListener('click', async (e) => {
                    e.preventDefault();
                    console.log('Requesting new code after expiry...');
                    try {
                        const response = await fetch('/api/resend-verification', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                email: email
                            })
                        });
                        
                        console.log('Response status:', response.status);
                        const data = await response.json();
                        console.log('Response data:', data);
                        
                        if (!response.ok) {
                            throw new Error(data.detail || 'Failed to resend verification code');
                        }
                        
                        // Show success message
                        showSuccess('A new verification code has been sent to your email');
                        
                        // Reset countdown
                        startCountdown(30 * 60); // 30 minutes
                        
                        // Reset timer display
                        const timerEl = document.getElementById('timer');
                        timerEl.innerHTML = 'Code expires in: <span id="countdown">30:00</span>';
                        countdownEl = document.getElementById('countdown');
                        
                        // Clear the inputs
                        codeInputs.forEach(input => {
                            input.value = '';
                        });
                        codeInputs[0].focus();
                        
                    } catch (error) {
                        console.error('Error requesting new code:', error);
                        showError(error.message);
                    }
                });
            }
            
            timeLeft--;
        }
        
        // Initial call
        updateCountdown();
        
        // Update every second
        const timer = setInterval(updateCountdown, 1000);
        
        // Enable resend link after 1 minute
        setTimeout(() => {
            console.log('Enabling resend link after 1 minute');
            enableResendLink();
        }, 60 * 1000);
    }
    
    // Disable resend link
    function disableResendLink() {
        console.log('Disabling resend link');
        resendLink.classList.add('disabled');
    }
    
    // Enable resend link
    function enableResendLink() {
        console.log('Enabling resend link');
        resendLink.classList.remove('disabled');
    }
    
    // Helper functions
    function showError(message) {
        console.error('Error message:', message);
        errorText.textContent = message;
        errorMessage.style.display = 'flex';
        successMessage.style.display = 'none';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            console.log('Auto-hiding error message');
            errorMessage.style.display = 'none';
        }, 10000); // Increased to 10 seconds for better visibility
    }
    
    function showSuccess(message) {
        console.log('Success message:', message);
        successText.textContent = message;
        successMessage.style.display = 'flex';
        errorMessage.style.display = 'none';
    }
    
    function setButtonLoading(button, isLoading) {
        if (isLoading) {
            console.log('Setting button to loading state');
            button.classList.add('loading');
            button.disabled = true;
        } else {
            console.log('Resetting button state');
            button.classList.remove('loading');
            button.disabled = false;
        }
    }
    
    // Initialize the countdown (30 minutes)
    startCountdown(30 * 60);
    
    // Initially disable resend link
    disableResendLink();
    
    // Focus first input
    codeInputs[0].focus();
    console.log('Verification page fully initialized');
});