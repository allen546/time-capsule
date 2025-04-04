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
    let uuid = localStorage.getItem('userUUID');
    if (!uuid) {
        // Generate a new UUID immediately
        uuid = generateUUID();
        localStorage.setItem('userUUID', uuid);
    }
    
    // Update all elements
    deviceIdElements.forEach(element => {
        element.textContent = uuid.substring(0, 8) + '...'; // Only show first 8 chars for privacy
    });
}

/**
 * Generate a UUID v4
 * @returns {string} A random UUID
 */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

/**
 * Font size control functionality
 * Allows users to increase or decrease text size with multiple levels
 * Shows current level (3-5) on center button
 */
function initFontSizeControls() {
    const decreaseBtn = document.getElementById('decreaseFontBtn');
    const normalBtn = document.getElementById('normalFontBtn');
    const increaseBtn = document.getElementById('increaseFontBtn');
    
    if (!decreaseBtn || !normalBtn || !increaseBtn) return;
    
    // Define size levels from smallest to largest (only normal, large, x-large)
    const sizeLevels = ['normal', 'large', 'x-large'];
    
    // Function to remove all font size classes
    function removeAllFontSizeClasses() {
        // Remove all possible classes including the ones we no longer use
        ['x-small', 'small', 'normal', 'large', 'x-large'].forEach(size => {
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
        const index = sizeLevels.indexOf(currentSize);
        // If stored preference is not in our new levels, default to normal (index 0)
        return index >= 0 ? index : 0;
    }
    
    // Update center button text to show current level (3-5)
    function updateCenterButtonText(index) {
        // Convert 0-2 index to 3-5 display level
        const displayLevel = index + 3;
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
        if (index === 0) { // normal is at index 0 now
            normalBtn.classList.add('active');
        } else if (index > 0) {
            increaseBtn.classList.add('active');
        } else {
            decreaseBtn.classList.add('active');
        }
        
        return index;
    }
    
    // Normal size (level 3)
    normalBtn.addEventListener('click', function() {
        applySizeByIndex(0); // "normal" is at index 0 now
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
    
    // Apply saved font size preference or default to normal
    const savedSize = localStorage.getItem('fontSizePreference') || 'normal';
    const savedIndex = sizeLevels.indexOf(savedSize);
    // If saved size is not in our new range, use normal
    applySizeByIndex(savedIndex >= 0 ? savedIndex : 0);
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

/**
 * Initialize profile form with auto-save functionality
 * Adds event listeners for form fields to auto-save when user types
 */
document.addEventListener('DOMContentLoaded', async function() {
    const profileForm = document.getElementById('profileForm');
    if (!profileForm || !window.UserSession) return;
    
    // Regular form submission handler
    profileForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        try {
            // Get form data
            const name = document.getElementById('userName').value.trim();
            const age = parseInt(document.getElementById('userAge').value, 10) || '';
            
            // Validate
            if (!name) {
                alert('请输入您的姓名');
                return;
            }
            
            // Update profile
            await window.UserSession.updateUserProfile(name, age);
            
            // Show success message
            alert('资料已保存');
            
            // Hide modal if on home page
            const profileModal = bootstrap.Modal.getInstance(document.getElementById('profileModal'));
            if (profileModal) profileModal.hide();
        } catch (error) {
            console.error('Error saving profile:', error);
            alert('保存失败，请稍后再试。');
        }
    });
    
    // Debounce function to prevent too many save requests
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Auto-save function
    const autoSaveProfile = debounce(async function() {
        try {
            // Get form data
            const name = document.getElementById('userName').value.trim();
            const age = parseInt(document.getElementById('userAge').value, 10) || '';
            
            // Don't save if name is empty
            if (!name) {
                console.log('Not auto-saving: name is empty');
                return;
            }
            
            // Update profile
            await window.UserSession.updateUserProfile(name, age);
            console.log('Profile auto-saved successfully');
            
            // Show subtle indicator that save happened
            const saveBtn = profileForm.querySelector('button[type="submit"]');
            if (saveBtn) {
                const originalText = saveBtn.textContent;
                saveBtn.textContent = '已自动保存';
                setTimeout(() => {
                    saveBtn.textContent = originalText;
                }, 1000);
            }
        } catch (error) {
            console.error('Error auto-saving profile:', error);
            // Silently fail on auto-save errors
        }
    }, 2000); // Wait 2 seconds after last input before saving
    
    // Add auto-save to each input
    const nameInput = document.getElementById('userName');
    const ageInput = document.getElementById('userAge');
    
    if (nameInput) {
        nameInput.addEventListener('input', autoSaveProfile);
    }
    
    if (ageInput) {
        ageInput.addEventListener('input', autoSaveProfile);
    }
    
    // Load user data
    try {
        const userData = await window.UserSession.getSessionData();
        if (userData && nameInput && ageInput) {
            nameInput.value = userData.name || '';
            ageInput.value = userData.age || '';
        }
    } catch (error) {
        console.error('Error loading user data:', error);
    }
}); 