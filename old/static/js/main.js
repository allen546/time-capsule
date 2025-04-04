/**
 * Time Capsule - Main JavaScript
 * 
 * This script handles:
 * - Accessibility features (font size controls, high contrast mode)
 * - Authentication (login, register, logout)
 * - API interactions
 * - UI interactions
 */

$(document).ready(function() {
    // Constants
    const API_BASE_URL = 'http://localhost:8080/api';
    
    // State management
    let currentFontSize = 'normal';
    let isLoggedIn = false;
    
    // Check if user is already logged in (token exists in localStorage)
    initializeAuthState();
    
    // Initialize accessibility settings from localStorage
    initializeAccessibilitySettings();
    
    // ==============================
    // Accessibility Features
    // ==============================
    
    // Font size controls
    $('#increaseFontBtn').click(function() {
        if (currentFontSize === 'normal') {
            $('body').addClass('font-size-large').removeClass('font-size-x-large');
            currentFontSize = 'large';
            updateFontSizeUI('large');
        } else if (currentFontSize === 'large') {
            $('body').removeClass('font-size-large').addClass('font-size-x-large');
            currentFontSize = 'x-large';
            updateFontSizeUI('x-large');
        }
        localStorage.setItem('fontSize', currentFontSize);
        announceChange('字体大小已增加');
    });
    
    $('#decreaseFontBtn').click(function() {
        if (currentFontSize === 'x-large') {
            $('body').addClass('font-size-large').removeClass('font-size-x-large');
            currentFontSize = 'large';
            updateFontSizeUI('large');
        } else if (currentFontSize === 'large') {
            $('body').removeClass('font-size-large font-size-x-large');
            currentFontSize = 'normal';
            updateFontSizeUI('normal');
        }
        localStorage.setItem('fontSize', currentFontSize);
        announceChange('字体大小已减小');
    });
    
    $('#resetFontBtn').click(function() {
        $('body').removeClass('font-size-large font-size-x-large');
        currentFontSize = 'normal';
        updateFontSizeUI('normal');
        localStorage.setItem('fontSize', currentFontSize);
        announceChange('字体大小已重置');
    });
    
    // Function to update font size UI elements
    function updateFontSizeUI(size) {
        // Remove active class from all buttons
        $('#decreaseFontBtn, #resetFontBtn, #increaseFontBtn').removeClass('active');
        
        // Update indicator text
        let indicatorText = '正常';
        let activeButton = $('#resetFontBtn');
        
        if (size === 'large') {
            indicatorText = '大';
            // For 'large' size, neither increase nor decrease is fully accurate,
            // but we'll use neither to indicate an intermediate state
            $('#resetFontBtn, #increaseFontBtn').addClass('active');
        } else if (size === 'x-large') {
            indicatorText = '超大';
            activeButton = $('#increaseFontBtn');
            activeButton.addClass('active');
        } else {
            // Normal size
            activeButton = $('#resetFontBtn');
            activeButton.addClass('active');
        }
        
        // Update the indicator text
        $('#currentFontSizeIndicator').text(indicatorText);
    }
    
    // High contrast mode toggle
    $('#highContrastToggle').change(function() {
        $('body').toggleClass('high-contrast');
        const isHighContrast = $('body').hasClass('high-contrast');
        localStorage.setItem('highContrast', isHighContrast);
        announceChange(isHighContrast ? '高对比度模式已开启' : '高对比度模式已关闭');
    });
    
    // Back to top button
    $(window).scroll(function() {
        if ($(this).scrollTop() > 300) {
            $('#backToTopBtn').addClass('visible');
        } else {
            $('#backToTopBtn').removeClass('visible');
        }
    });
    
    $('#backToTopBtn').click(function() {
        $('html, body').animate({ scrollTop: 0 }, 500);
        return false;
    });
    
    // Learn more button scrolls to how-it-works section
    $('#learnMoreBtn').click(function() {
        $('html, body').animate({
            scrollTop: $('.how-it-works').offset().top - 100
        }, 500);
    });
    
    // ==============================
    // Authentication
    // ==============================
    
    // Login form submission
    $('#loginForm').submit(function(e) {
        e.preventDefault();
        
        const username = $('#loginUsername').val();
        const password = $('#loginPassword').val();
        
        login(username, password);
    });
    
    // Register form submission
    $('#registerForm').submit(function(e) {
        e.preventDefault();
        
        const username = $('#registerUsername').val();
        const password = $('#registerPassword').val();
        const realName = $('#registerName').val();
        const age = $('#registerAge').val();
        
        register(username, password, realName, age);
    });
    
    // Logout button
    $('#logoutBtn').click(function() {
        logout();
    });
    
    // Start chat button
    $('#startChatBtn').click(function() {
        if (isLoggedIn) {
            window.location.href = 'conversations.html';
        } else {
            $('#loginModal').modal('show');
            announceChange('请先登录以开始对话');
        }
    });
    
    // ==============================
    // Helper Functions
    // ==============================
    
    // Initialize authentication state
    function initializeAuthState() {
        const token = localStorage.getItem('token');
        
        if (token) {
            isLoggedIn = true;
            updateUIForLoggedInUser();
            
            // Fetch user data
            fetchUserProfile();
        }
    }
    
    // Initialize accessibility settings
    function initializeAccessibilitySettings() {
        // Set font size
        const savedFontSize = localStorage.getItem('fontSize');
        if (savedFontSize) {
            currentFontSize = savedFontSize;
            
            if (currentFontSize === 'large') {
                $('body').addClass('font-size-large');
            } else if (currentFontSize === 'x-large') {
                $('body').addClass('font-size-x-large');
            }
            
            // Update UI to show current font size
            updateFontSizeUI(currentFontSize);
        }
        
        // Set high contrast mode
        const highContrast = localStorage.getItem('highContrast') === 'true';
        if (highContrast) {
            $('body').addClass('high-contrast');
            $('#highContrastToggle').prop('checked', true);
        }
    }
    
    // Update UI for logged in user
    function updateUIForLoggedInUser() {
        $('#loginBtn, #registerBtn').addClass('d-none');
        $('#userInfo').removeClass('d-none');
    }
    
    // Update UI for logged out user
    function updateUIForLoggedOutUser() {
        $('#loginBtn, #registerBtn').removeClass('d-none');
        $('#userInfo').addClass('d-none');
    }
    
    // Announce changes for screen readers
    function announceChange(message) {
        // Create a live region if it doesn't exist
        if (!$('#announce').length) {
            $('body').append('<div id="announce" class="visually-hidden" aria-live="assertive"></div>');
        }
        
        // Set the message
        $('#announce').text(message);
        
        // Clear after a short delay
        setTimeout(function() {
            $('#announce').text('');
        }, 3000);
    }
    
    // Show alert message
    function showAlert(message, type = 'danger') {
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
        // Create alert container if it doesn't exist
        if (!$('#alertContainer').length) {
            $('body').prepend('<div id="alertContainer" class="container mt-3"></div>');
        }
        
        // Add alert to container
        $('#alertContainer').html(alertHtml);
        
        // Announce for screen readers
        announceChange(message);
        
        // Auto dismiss after 5 seconds
        setTimeout(function() {
            $('.alert').alert('close');
        }, 5000);
    }
    
    // ==============================
    // API Functions
    // ==============================
    
    // Login function
    function login(username, password) {
        $.ajax({
            url: `${API_BASE_URL}/users/login`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                username: username,
                password: password
            }),
            success: function(response) {
                // Store token
                localStorage.setItem('token', response.access_token);
                isLoggedIn = true;
                
                // Update UI
                updateUIForLoggedInUser();
                
                // Close modal
                $('#loginModal').modal('hide');
                
                // Show success message
                showAlert('登录成功！', 'success');
                
                // Fetch user profile
                fetchUserProfile();
            },
            error: function(xhr) {
                let errorMessage = '登录失败，请稍后再试';
                
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                }
                
                showAlert(errorMessage);
            }
        });
    }
    
    // Register function
    function register(username, password, realName, age) {
        $.ajax({
            url: `${API_BASE_URL}/users/register`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                username: username,
                password_hash: password,
                real_name: realName,
                age: parseInt(age)
            }),
            success: function(response) {
                // Store token
                localStorage.setItem('token', response.access_token);
                isLoggedIn = true;
                
                // Update UI
                updateUIForLoggedInUser();
                
                // Close modal
                $('#registerModal').modal('hide');
                
                // Show success message
                showAlert('注册成功！欢迎加入时光胶囊', 'success');
            },
            error: function(xhr) {
                let errorMessage = '注册失败，请稍后再试';
                
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                }
                
                showAlert(errorMessage);
            }
        });
    }
    
    // Logout function
    function logout() {
        // Clear token
        localStorage.removeItem('token');
        isLoggedIn = false;
        
        // Update UI
        updateUIForLoggedOutUser();
        
        // Show message
        showAlert('已成功退出登录', 'success');
    }
    
    // Fetch user profile
    function fetchUserProfile() {
        const token = localStorage.getItem('token');
        
        if (!token) {
            return;
        }
        
        $.ajax({
            url: `${API_BASE_URL}/users/me`,
            type: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            success: function(response) {
                // Store user info
                localStorage.setItem('userProfile', JSON.stringify(response));
                
                // Update UI with user info
                const userName = response.real_name || response.username;
                $('#userInfo').prepend(`<span class="me-2 fs-5">欢迎, ${userName}</span>`);
            },
            error: function(xhr) {
                if (xhr.status === 401) {
                    // Token expired or invalid
                    logout();
                    showAlert('会话已过期，请重新登录');
                }
            }
        });
    }
}); 