/**
 * User Session Management System
 * Only handles device identification while all user data is stored server-side
 */

// Define an extremely simplified UserSession singleton
const UserSession = {
    /**
     * Initialize or retrieve user UUID
     * This is the only method that should be called on page load
     */
    async initialize() {
        console.log('UserSession: Initializing');
        
        // Check if UUID already exists in localStorage
        let uuid = localStorage.getItem('userUUID');
        console.log('UserSession: Stored UUID:', uuid);
        
        if (!uuid) {
            console.log('UserSession: No UUID found, requesting from server');
            // Try to get a UUID from the server
            try {
                uuid = await this.requestNewUUID();
                console.log('UserSession: Received UUID from server:', uuid);
            } catch (error) {
                console.error('UserSession: Error getting UUID from server, generating locally', error);
                uuid = this._generateClientUUID();
                console.warn('UserSession: Generated emergency UUID:', uuid);
            }
            
            // Save the UUID to localStorage
            localStorage.setItem('userUUID', uuid);
        }
        
        // Return session data from server
        try {
            const sessionData = await this.getSessionDataFromServer();
            return sessionData;
        } catch (error) {
            console.error('UserSession: Could not fetch session data from server:', error);
            // Return minimal data with just the UUID
            return { uuid };
        }
    },
    
    /**
     * Get session data from server
     */
    async getSessionDataFromServer() {
        const uuid = localStorage.getItem('userUUID');
        if (!uuid) {
            console.error('UserSession: No UUID available for server request');
            return null;
        }
        
        try {
            const response = await fetch('/api/users/profile', {
                method: 'GET',
                headers: {
                    'X-User-UUID': uuid
                }
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            if (data.status === 'success') {
                console.log('UserSession: Retrieved session data from server', data.data);
                return data.data;
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        } catch (error) {
            console.error('UserSession: Error getting session data from server:', error);
            // Fallback to minimal data
            return { uuid };
        }
    },
    
    /**
     * Get current user session data (or initialize if needed)
     */
    async getSessionData() {
        const uuid = localStorage.getItem('userUUID');
        if (!uuid) {
            // No UUID - need to initialize
            return this.initialize();
        }
        
        // Try to get data from server
        return this.getSessionDataFromServer();
    },
    
    /**
     * Request a new UUID from the server
     */
    async requestNewUUID() {
        try {
            const response = await fetch('/api/users/generate-uuid', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            return data.uuid;
        } catch (e) {
            console.error("Failed to get UUID from server:", e);
            // Fallback: Generate client-side UUID if server fails
            return this._generateClientUUID();
        }
    },
    
    /**
     * Update user profile on server
     */
    async updateUserProfile(name, age, profileData = {}) {
        const uuid = localStorage.getItem('userUUID');
        if (!uuid) {
            throw new Error('No user UUID found');
        }
        
        try {
            const response = await fetch('/api/users/profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-UUID': uuid
                },
                body: JSON.stringify({ 
                    name, 
                    age,
                    profile_data: profileData
                })
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            if (data.status === 'success') {
                // Get updated profile from server
                return this.getSessionDataFromServer();
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        } catch (error) {
            console.error('Error updating profile:', error);
            throw error;
        }
    },
    
    /**
     * Get profile questions
     */
    async getProfileQuestions() {
        try {
            const response = await fetch('/api/profile-questions', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            if (data.status === 'success') {
                return data.data;
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        } catch (error) {
            console.error('Error fetching profile questions:', error);
            throw error;
        }
    },
    
    /**
     * Reset device - generates a new device ID
     */
    async resetDevice() {
        const oldUUID = localStorage.getItem('userUUID');
        
        // Clear localStorage
        localStorage.removeItem('userUUID');
        
        // Try to notify the server about the reset
        let serverMessage = '设备已重置';
        if (oldUUID) {
            try {
                const response = await fetch('/api/users/reset', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ old_uuid: oldUUID })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    serverMessage = data.message || serverMessage;
                }
            } catch (err) {
                console.warn('Could not notify server about device reset:', err);
            }
        }
        
        // Generate new UUID
        const newUUID = await this.requestNewUUID();
        localStorage.setItem('userUUID', newUUID);
        
        console.log('Device reset completed, new UUID:', newUUID);
        return { success: true, message: serverMessage, newUUID };
    },
    
    /**
     * Show welcome modal for first-time visitors
     */
    showWelcomeModal() {
        // Check if this is the first visit
        if (localStorage.getItem('firstVisit') !== 'true') {
            return;
        }
        
        // Create welcome modal if it doesn't exist
        if (!document.getElementById('welcomeModal')) {
            const modalHTML = `
                <div class="modal fade" id="welcomeModal" tabindex="-1" aria-labelledby="welcomeModalLabel" aria-hidden="true">
                    <div class="modal-dialog modal-dialog-centered">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="welcomeModalLabel">欢迎使用时光胶囊！</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="关闭"></button>
                            </div>
                            <div class="modal-body">
                                <div class="text-center mb-4">
                                    <i class="fas fa-hourglass-half fa-4x text-primary mb-3"></i>
                                    <h4>简便登录系统</h4>
                                </div>
                                
                                <div class="welcome-info">
                                    <p><i class="fas fa-check-circle me-2 text-success"></i> <strong>无需记住密码</strong> - 我们使用您的设备来识别您，无需记住任何密码。</p>
                                    <p><i class="fas fa-check-circle me-2 text-success"></i> <strong>自动保存信息</strong> - 您的个人信息会自动保存在我们的服务器上。</p>
                                    <p><i class="fas fa-check-circle me-2 text-success"></i> <strong>简单易用</strong> - 每次访问时，系统会自动识别您，无需重新登录。</p>
                                </div>
                                
                                <div class="alert alert-info mt-4">
                                    <i class="fas fa-info-circle me-2"></i> 请注意：如果您更换设备或清除浏览器数据，您将需要重新设置个人资料。
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-primary" data-bs-dismiss="modal">我知道了</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Add modal to body
            const div = document.createElement('div');
            div.innerHTML = modalHTML;
            document.body.appendChild(div.firstElementChild);
            
            // Show modal
            const welcomeModal = new bootstrap.Modal(document.getElementById('welcomeModal'));
            welcomeModal.show();
            
            // Mark as visited when modal is closed
            document.getElementById('welcomeModal').addEventListener('hidden.bs.modal', function() {
                localStorage.setItem('firstVisit', 'false');
            });
        }
    },
    
    /**
     * Generate a UUID client-side (fallback if server is unreachable)
     * @private
     */
    _generateClientUUID() {
        // Very simplified UUID generation (not a real UUID)
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },
    
    /**
     * Ensure the user session is initialized
     */
    async ensureInitialized() {
        // Get stored UUID
        if (!localStorage.getItem('userUUID')) {
            await this.initialize();
        }
        
        // Mark as first visit if not set
        if (localStorage.getItem('firstVisit') === null) {
            localStorage.setItem('firstVisit', 'true');
        }
        
        return localStorage.getItem('userUUID');
    }
};

// Initialize UserSession when script loads (in background)
UserSession.ensureInitialized().then(() => {
    console.log('UserSession initialized');
    
    // Show welcome modal if it's a first visit
    if (localStorage.getItem('firstVisit') === 'true') {
        // Wait a bit before showing the modal to ensure page is loaded
        setTimeout(() => {
            UserSession.showWelcomeModal();
        }, 1000);
    }
}).catch(err => {
    console.error('Error initializing UserSession:', err);
});

// Export the session manager
window.UserSession = UserSession; 