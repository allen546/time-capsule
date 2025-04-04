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
    // Initialize user session
    await initUserSession();
    
    // Initialize all components
    initFontSizeControls();
    initHighContrastMode();
    initBackToTopButton();
    initProfileForm();
    initNavbarToggle();
    
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
 * Initialize user session
 * Gets or creates user UUID and loads profile data
 */
async function initUserSession() {
    try {
        // Initialize user session
        const sessionData = await UserSession.initialize();
        
        // Display UUID (truncated for privacy)
        const truncatedUUID = sessionData.uuid.substring(0, 8) + '...';
        document.getElementById('userUUID').textContent = truncatedUUID;
        
        // Update UI with user data if available
        if (sessionData.name) {
            document.getElementById('userName').value = sessionData.name;
            document.getElementById('navUserName').textContent = sessionData.name;
            document.getElementById('profileNavItem').style.display = 'block';
        }
        
        if (sessionData.age) {
            document.getElementById('userAge').value = sessionData.age;
        }
        
        console.log('User session initialized:', { uuid: truncatedUUID });
    } catch (error) {
        console.error('Failed to initialize user session:', error);
    }
}

/**
 * Profile form handling
 * Saves user profile data
 */
function initProfileForm() {
    const profileForm = document.getElementById('profileForm');
    
    profileForm?.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const name = document.getElementById('userName').value.trim();
        const age = parseInt(document.getElementById('userAge').value, 10);
        
        if (!name) {
            alert('请输入您的姓名');
            return;
        }
        
        if (isNaN(age) || age < 50 || age > 120) {
            alert('请输入有效的年龄（50-120之间）');
            return;
        }
        
        try {
            // Update user profile
            await UserSession.updateUserProfile(name, age);
            
            // Update UI
            document.getElementById('navUserName').textContent = name;
            document.getElementById('profileNavItem').style.display = 'block';
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('profileModal'));
            if (modal) modal.hide();
            
            // Show success message
            alert('个人资料已成功保存！');
        } catch (error) {
            console.error('Failed to update profile:', error);
            alert('保存个人资料时出错，请稍后再试');
        }
    });
}

/**
 * Font size control functionality
 * Allows users to increase or decrease text size
 */
function initFontSizeControls() {
    const decreaseBtn = document.getElementById('decreaseFontBtn');
    const normalBtn = document.getElementById('normalFontBtn');
    const increaseBtn = document.getElementById('increaseFontBtn');
    
    // Function to remove all font size classes
    function removeAllFontSizeClasses() {
        document.body.classList.remove('font-size-large', 'font-size-x-large');
        
        // Reset active state on buttons
        decreaseBtn.classList.remove('active');
        normalBtn.classList.remove('active');
        increaseBtn.classList.remove('active');
    }
    
    // Default text size
    normalBtn?.addEventListener('click', function() {
        removeAllFontSizeClasses();
        normalBtn.classList.add('active');
        
        // Save preference
        localStorage.setItem('fontSizePreference', 'normal');
    });
    
    // Large text size
    increaseBtn?.addEventListener('click', function() {
        removeAllFontSizeClasses();
        document.body.classList.add('font-size-large');
        increaseBtn.classList.add('active');
        
        // Save preference
        localStorage.setItem('fontSizePreference', 'large');
    });
    
    // Smaller text size (but still larger than typical websites)
    decreaseBtn?.addEventListener('click', function() {
        removeAllFontSizeClasses();
        document.body.classList.add('font-size-x-large');
        decreaseBtn.classList.add('active');
        
        // Save preference
        localStorage.setItem('fontSizePreference', 'x-large');
    });
    
    // Apply saved font size preference
    const savedFontSize = localStorage.getItem('fontSizePreference');
    if (savedFontSize === 'large') {
        document.body.classList.add('font-size-large');
        increaseBtn?.classList.add('active');
    } else if (savedFontSize === 'x-large') {
        document.body.classList.add('font-size-x-large');
        decreaseBtn?.classList.add('active');
    } else {
        normalBtn?.classList.add('active');
    }
}

/**
 * High contrast mode toggle
 * Improves visibility for users with visual impairments
 */
function initHighContrastMode() {
    const contrastToggle = document.getElementById('highContrastToggle');
    
    contrastToggle?.addEventListener('change', function() {
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
        if (contrastToggle) contrastToggle.checked = true;
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
    
    navLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth < 992) {
                navbarCollapse.classList.remove('show');
                menuToggle.setAttribute('aria-expanded', 'false');
            }
        });
    });
} 