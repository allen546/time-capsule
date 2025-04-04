/**
 * Time Capsule - Main JavaScript
 * Handles accessibility features and user interactions
 */

// Add timestamp to all script and CSS requests to prevent caching
(function() {
    // Only run in development environment
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        const timestamp = new Date().getTime();
        const linkElements = document.querySelectorAll('link[rel="stylesheet"]');
        const scriptElements = document.querySelectorAll('script[src]');
        
        // Add timestamp to CSS files
        linkElements.forEach(link => {
            if (link.href.includes('/static/')) {
                link.href = link.href + (link.href.includes('?') ? '&' : '?') + '_t=' + timestamp;
            }
        });
        
        // Add timestamp to JS files
        scriptElements.forEach(script => {
            if (script.src.includes('/static/')) {
                script.src = script.src + (script.src.includes('?') ? '&' : '?') + '_t=' + timestamp;
            }
        });
        
        console.log('Development mode: Cache busting enabled');
    }
})();

document.addEventListener('DOMContentLoaded', async function() {
    // Initialize all components
    initFontSizeControls();
    initHighContrastMode();
    initBackToTopButton();
    initNavbarToggle();
    initHelpButtons();
    initDeviceId();
    
    // Demo functionality for the start chat button
    document.getElementById('startChatBtn')?.addEventListener('click', function() {
        alert('对话功能即将上线，敬请期待！');
    });
    
    // Demo functionality for the learn more button
    document.getElementById('learnMoreBtn')?.addEventListener('click', function() {
        window.scrollTo({
            top: document.querySelector('.how-it-works').offsetTop - 100,
            behavior: 'smooth'
        });
    });
});

/**
 * Update device ID display
 * Shows the device ID wherever it needs to be displayed
 */
function initDeviceId() {
    // Find elements that need device ID
    const deviceIdElements = document.querySelectorAll('#userUUID');
    if (!deviceIdElements.length) return;
    
    // Get UUID from localStorage
    const uuid = localStorage.getItem('userUUID');
    if (!uuid) {
        // If no UUID exists yet, check again after a short delay
        // This handles cases where UUID is created by another script
        setTimeout(() => {
            const newUuid = localStorage.getItem('userUUID');
            if (newUuid) {
                deviceIdElements.forEach(element => {
                    element.textContent = newUuid.substring(0, 8) + '...';
                });
            } else {
                deviceIdElements.forEach(element => {
                    element.textContent = '未找到';
                });
            }
        }, 500);
        return;
    }
    
    // Update all elements
    deviceIdElements.forEach(element => {
        element.textContent = uuid.substring(0, 8) + '...'; // Only show first 8 chars for privacy
    });
}

/**
 * Font size control functionality
 * Allows users to increase or decrease text size with multiple levels
 * Shows current level (1-5) on center button
 */
function initFontSizeControls() {
    const decreaseBtn = document.getElementById('decreaseFontBtn');
    const normalBtn = document.getElementById('normalFontBtn');
    const increaseBtn = document.getElementById('increaseFontBtn');
    
    if (!decreaseBtn || !normalBtn || !increaseBtn) return;
    
    // Define size levels from smallest to largest
    const sizeLevels = ['x-small', 'small', 'normal', 'large', 'x-large'];
    
    // Function to remove all font size classes
    function removeAllFontSizeClasses() {
        sizeLevels.forEach(size => {
            document.body.classList.remove(`font-size-${size}`);
        });
        
        // Reset active state on buttons
        decreaseBtn.classList.remove('active');
        normalBtn.classList.remove('active');
        increaseBtn.classList.remove('active');
    }
    
    // Get current size level index
    function getCurrentSizeIndex() {
        const currentSize = localStorage.getItem('fontSizePreference') || 'normal';
        return sizeLevels.indexOf(currentSize);
    }
    
    // Update center button text to show current level (1-5)
    function updateCenterButtonText(index) {
        // Convert 0-4 index to 1-5 display level
        const displayLevel = index + 1;
        normalBtn.textContent = displayLevel.toString();
    }
    
    // Apply size by index
    function applySizeByIndex(index) {
        // Ensure index is within bounds
        index = Math.max(0, Math.min(index, sizeLevels.length - 1));
        
        const size = sizeLevels[index];
        removeAllFontSizeClasses();
        document.body.classList.add(`font-size-${size}`);
        localStorage.setItem('fontSizePreference', size);
        
        // Update center button text
        updateCenterButtonText(index);
        
        // Update active button
        if (index === 2) { // normal is at index 2
            normalBtn.classList.add('active');
        } else if (index > 2) {
            increaseBtn.classList.add('active');
        } else {
            decreaseBtn.classList.add('active');
        }
        
        return index;
    }
    
    // Normal size (level 3)
    normalBtn.addEventListener('click', function() {
        applySizeByIndex(2); // "normal" is at index 2
    });
    
    // Increase size
    increaseBtn.addEventListener('click', function() {
        const currentIndex = getCurrentSizeIndex();
        applySizeByIndex(currentIndex + 1);
    });
    
    // Decrease size
    decreaseBtn.addEventListener('click', function() {
        const currentIndex = getCurrentSizeIndex();
        applySizeByIndex(currentIndex - 1);
    });
    
    // Apply saved font size preference
    const savedSize = localStorage.getItem('fontSizePreference') || 'normal';
    applySizeByIndex(sizeLevels.indexOf(savedSize));
}

/**
 * High contrast mode toggle
 * Improves visibility for users with visual impairments
 */
function initHighContrastMode() {
    const contrastToggle = document.getElementById('highContrastToggle');
    
    if (!contrastToggle) return;
    
    contrastToggle.addEventListener('change', function() {
        if (this.checked) {
            document.body.classList.add('high-contrast');
            localStorage.setItem('highContrast', 'enabled');
        } else {
            document.body.classList.remove('high-contrast');
            localStorage.setItem('highContrast', 'disabled');
        }
    });
    
    // Apply saved contrast preference
    const savedContrast = localStorage.getItem('highContrast');
    if (savedContrast === 'enabled') {
        document.body.classList.add('high-contrast');
        contrastToggle.checked = true;
    }
}

/**
 * Back to top button functionality
 * Shows a button to return to the top of the page after scrolling
 */
function initBackToTopButton() {
    const backToTopBtn = document.getElementById('backToTopBtn');
    
    if (!backToTopBtn) return;
    
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopBtn.classList.add('visible');
        } else {
            backToTopBtn.classList.remove('visible');
        }
    });
    
    backToTopBtn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

/**
 * Navbar toggle for mobile devices
 * Ensures the mobile menu closes when a link is clicked
 */
function initNavbarToggle() {
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const menuToggle = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (!navLinks.length || !menuToggle || !navbarCollapse) return;
    
    navLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth < 992) {
                navbarCollapse.classList.remove('show');
                menuToggle.setAttribute('aria-expanded', 'false');
            }
        });
    });
}

/**
 * Help buttons functionality
 * Shows the welcome modal when clicked
 */
function initHelpButtons() {
    // Help button in modal
    const modalShowHelpBtn = document.getElementById('modalShowHelpBtn');
    if (modalShowHelpBtn && window.UserSession) {
        modalShowHelpBtn.addEventListener('click', function() {
            // Close profile modal if open
            const profileModal = bootstrap.Modal.getInstance(document.getElementById('profileModal'));
            if (profileModal) profileModal.hide();
            
            // Force showing the welcome modal
            localStorage.setItem('firstVisit', 'true');
            window.UserSession.showWelcomeModal();
        });
    }
} 