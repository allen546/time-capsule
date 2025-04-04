/**
 * Time Capsule - Main JavaScript
 * Handles accessibility features and user interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initFontSizeControls();
    initHighContrastMode();
    initBackToTopButton();
    initFormValidation();
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
 * Form validation
 * Handles login and registration form validation
 */
function initFormValidation() {
    // Login form validation
    const loginForm = document.getElementById('loginForm');
    loginForm?.addEventListener('submit', function(e) {
        e.preventDefault();
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;
        
        if (username && password) {
            // Demo login message - in a real app this would make an API call
            alert('登录功能即将上线，敬请期待！');
            
            // Close the modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
            if (modal) modal.hide();
        }
    });
    
    // Registration form validation
    const registerForm = document.getElementById('registerForm');
    registerForm?.addEventListener('submit', function(e) {
        e.preventDefault();
        const username = document.getElementById('registerUsername').value;
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        if (username && email && password) {
            if (password !== confirmPassword) {
                alert('两次输入的密码不匹配，请重新输入！');
                return;
            }
            
            // Demo registration message - in a real app this would make an API call
            alert('注册功能即将上线，敬请期待！');
            
            // Close the modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('registerModal'));
            if (modal) modal.hide();
        }
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