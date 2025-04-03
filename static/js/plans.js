/**
 * DreamMaker - Plans and Payments Scripts
 * Handles plan upgrades and token purchases
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const upgradePlanButtons = document.querySelectorAll('.upgrade-plan-btn');
    const selectPlanButtons = document.querySelectorAll('.select-plan-btn');
    const purchasePackageButtons = document.querySelectorAll('.purchase-package-btn');
    const paymentSuccessModal = document.getElementById('payment-success-modal');
    const closePaymentModalButton = document.getElementById('close-payment-modal');
    const paymentAmountElement = document.getElementById('payment-amount');
    const paymentTokensElement = document.getElementById('payment-tokens');
    const modalCloseButton = document.querySelector('.modal-close');
    const smoothScrollButtons = document.querySelectorAll('.smooth-scroll');
    
    // Check if we're in new user mode
    const isNewUser = window.location.search.includes('new_user=true');
    
    // Modal close button
    if (modalCloseButton) {
        modalCloseButton.addEventListener('click', function() {
            paymentSuccessModal.classList.remove('show');
        });
    }
    
    // Close payment modal
    if (closePaymentModalButton) {
        closePaymentModalButton.addEventListener('click', function() {
            paymentSuccessModal.classList.remove('show');
            // Reload the page to show updated token balance
            location.reload();
        });
    }
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === paymentSuccessModal) {
            paymentSuccessModal.classList.remove('show');
        }
    });
    
    // Smooth scroll functionality
    if (smoothScrollButtons) {
        smoothScrollButtons.forEach(button => {
            button.addEventListener('click', function() {
                const targetId = this.getAttribute('data-target');
                const targetElement = document.getElementById(targetId);
                
                if (targetElement) {
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }
    
    // Handle initial plan selection for new users
    if (selectPlanButtons) {
        selectPlanButtons.forEach(button => {
            button.addEventListener('click', async function() {
                const planId = this.getAttribute('data-plan');
                
                // Set loading state
                setButtonLoading(this, true);
                
                try {
                    const response = await fetch('/api/select-initial-plan', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ plan_id: planId })
                    });
                    
                    const data = await response.json();
                    
                    if (!response.ok) {
                        throw new Error(data.detail || 'Failed to select plan');
                    }
                    
                    if (planId !== 'free') {
                        // Show success modal for paid plans
                        showPaymentSuccessModal(planDetails[planId]);
                        
                        // Show success notification
                        showNotification(data.detail, 'success');
                        
                        // Redirect to the studio after a delay
                        setTimeout(() => {
                            window.location.href = data.redirect || '/studio';
                        }, 3000);
                    } else {
                        // For free plan, just redirect
                        showNotification('Free plan selected. Redirecting to studio...', 'success');
                        
                        setTimeout(() => {
                            window.location.href = data.redirect || '/studio';
                        }, 1500);
                    }
                    
                } catch (error) {
                    console.error('Error selecting plan:', error);
                    showNotification(error.message, 'error');
                    setButtonLoading(this, false);
                }
            });
        });
    }
    
    // Handle plan upgrade
    if (upgradePlanButtons) {
        upgradePlanButtons.forEach(button => {
            button.addEventListener('click', async function() {
                const planId = this.getAttribute('data-plan');
                
                // Set loading state
                setButtonLoading(this, true);
                
                try {
                    const response = await fetch('/api/payments/upgrade-plan', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ plan_id: planId })
                    });
                    
                    const data = await response.json();
                    
                    if (!response.ok) {
                        throw new Error(data.detail || 'Failed to upgrade plan');
                    }
                    
                    // Show success modal
                    showPaymentSuccessModal(planDetails[planId]);
                    
                    // Show success notification
                    showNotification(data.detail, 'success');
                    
                } catch (error) {
                    console.error('Error upgrading plan:', error);
                    showNotification(error.message, 'error');
                } finally {
                    setButtonLoading(this, false);
                }
            });
        });
    }
    
    // Handle token package purchase
    if (purchasePackageButtons) {
        purchasePackageButtons.forEach(button => {
            button.addEventListener('click', async function() {
                const packageId = this.getAttribute('data-package');
                
                // Set loading state
                setButtonLoading(this, true);
                
                try {
                    const response = await fetch('/api/payments/purchase-tokens', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ package_id: packageId })
                    });
                    
                    const data = await response.json();
                    
                    if (!response.ok) {
                        throw new Error(data.detail || 'Failed to purchase tokens');
                    }
                    
                    // Show success modal
                    showPaymentSuccessModal(packageDetails[packageId]);
                    
                    // Show success notification
                    showNotification(data.detail, 'success');
                    
                } catch (error) {
                    console.error('Error purchasing tokens:', error);
                    showNotification(error.message, 'error');
                } finally {
                    setButtonLoading(this, false);
                }
            });
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
    
    // Helper function to show payment success modal
    function showPaymentSuccessModal(details) {
        if (paymentAmountElement && paymentTokensElement) {
            paymentAmountElement.textContent = `${details.price.toLocaleString()} Toman`;
            paymentTokensElement.textContent = `${details.tokens} Tokens`;
        }
        
        paymentSuccessModal.classList.add('show');
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
    
    // Define plan and package details
    const planDetails = {
        premium: {
            price: 120000,
            tokens: 100
        },
        pro: {
            price: 270000,
            tokens: 250
        }
    };
    
    const packageDetails = {
        small: {
            price: 70000,
            tokens: 50
        },
        medium: {
            price: 130000,
            tokens: 120
        },
        large: {
            price: 280000,
            tokens: 300
        }
    };
});