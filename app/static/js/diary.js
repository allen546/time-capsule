/**
 * Time Capsule - Diary System
 * Handles diary entry management with server API
 */

// API functions
const DiaryAPI = {
    // Track if a submission is in progress
    _isSubmitting: false,
    
    // Get all diary entries
    async getEntries() {
        try {
            console.log('DiaryAPI: Retrieving entries from server');
            // Get user UUID from localStorage
            const uuid = localStorage.getItem('userUUID');
            if (!uuid) {
                throw new Error("用户ID未找到");
            }
            
            console.log('DiaryAPI: Using UUID:', uuid);
            const response = await fetch('/api/diary/entries', {
                headers: {
                    'X-User-UUID': uuid
                }
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                // Ensure data.data is an array
                const entries = Array.isArray(data.data) ? data.data : [];
                console.log(`DiaryAPI: Retrieved ${entries.length} entries from server`);
                return entries;
            } else {
                throw new Error(data.message || "获取日记时出错");
            }
        } catch (error) {
            console.error("DiaryAPI: Error fetching entries from server:", error);
            // On error, return empty array to show empty state
            return [];
        }
    },
    
    // Create a new diary entry
    async createEntry(entryData) {
        console.log('Creating diary entry:', entryData);
        
        // Prevent multiple simultaneous submissions
        if (this._isSubmitting) {
            console.warn('Submission already in progress, ignoring duplicate request');
            throw new Error('提交正在处理中，请稍候');
        }
        
        // Lock submission
        this._isSubmitting = true;
        
        try {
            // Ensure we have a userUUID
            let userUUID = localStorage.getItem('userUUID');
            console.log('User UUID from localStorage:', userUUID);
            
            if (!userUUID) {
                console.warn('No UUID found in localStorage for diary entry creation, attempting to retrieve');
                try {
                    // Try to initialize user session and get UUID
                    if (typeof UserSession !== 'undefined') {
                        const sessionData = await UserSession.initialize();
                        if (sessionData && sessionData.uuid) {
                            userUUID = sessionData.uuid;
                            console.log('Retrieved UUID from UserSession:', userUUID);
                            localStorage.setItem('userUUID', userUUID);
                        }
                    }
                } catch (e) {
                    console.error('Error retrieving UUID from UserSession:', e);
                }
                
                // If still no UUID, create an emergency one
                if (!userUUID) {
                    userUUID = 'emergency-' + Date.now() + '-' + Math.random().toString(36).substring(2, 15);
                    console.warn('Using emergency UUID for diary entry:', userUUID);
                    localStorage.setItem('userUUID', userUUID);
                }
            }
            
            // Add timestamp if not present
            if (!entryData.timestamp) {
                entryData.timestamp = new Date().toISOString();
            }
            
            // Format the date correctly if needed
            if (entryData.date && typeof entryData.date === 'object' && entryData.date instanceof Date) {
                entryData.date = entryData.date.toISOString().split('T')[0];
            }
            
            let retryCount = 0;
            const maxRetries = 2;
            
            const attemptCreate = async () => {
                try {
                    console.log(`Attempt ${retryCount + 1} to send entry to server`);
                    
                    const response = await fetch('/api/diary/entries', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-User-UUID': userUUID
                        },
                        body: JSON.stringify(entryData)
                    });
                    
                    console.log('Server response status:', response.status);
                    
                    // Check if the request was successful
                    if (!response.ok) {
                        const errorText = await response.text();
                        console.error('Server error response:', errorText);
                        
                        let errorJson;
                        try {
                            errorJson = JSON.parse(errorText);
                        } catch (e) {
                            console.warn('Could not parse error response as JSON');
                        }
                        
                        const errorMessage = errorJson?.message || `Server error: ${response.status}`;
                        console.error('Error creating diary entry:', errorMessage);
                        
                        // Retry logic
                        if (retryCount < maxRetries) {
                            retryCount++;
                            console.log(`Retrying... (${retryCount}/${maxRetries})`);
                            return await attemptCreate();
                        }
                        
                        throw new Error(errorMessage);
                    }
                    
                    // Parse the JSON response
                    let data;
                    try {
                        data = await response.json();
                        console.log('Server response data:', data);
                    } catch (e) {
                        console.error('Error parsing server response:', e);
                        throw new Error('Invalid server response');
                    }
                    
                    if (data.status === 'success') {
                        console.log('Entry created successfully:', data.data);
                        return data.data;
                    } else {
                        const errorMessage = data.message || 'Unknown error';
                        console.error('Error in server response:', errorMessage);
                        
                        // Retry logic
                        if (retryCount < maxRetries) {
                            retryCount++;
                            console.log(`Retrying... (${retryCount}/${maxRetries})`);
                            return await attemptCreate();
                        }
                        
                        throw new Error(errorMessage);
                    }
                } catch (error) {
                    console.error('Network or processing error:', error);
                    
                    // Retry logic for network errors
                    if (retryCount < maxRetries) {
                        retryCount++;
                        console.log(`Retrying after error... (${retryCount}/${maxRetries})`);
                        // Add exponential backoff
                        await new Promise(resolve => setTimeout(resolve, 1000 * retryCount));
                        return await attemptCreate();
                    }
                    
                    throw error;
                }
            };
            
            return await attemptCreate();
        } catch (error) {
            console.error('Error in createEntry:', error);
            throw error;
        } finally {
            // Always unlock submission when done
            this._isSubmitting = false;
        }
    },
    
    // Update an existing diary entry
    async updateEntry(entry) {
        try {
            const uuid = localStorage.getItem('userUUID');
            if (!uuid) {
                throw new Error("用户ID未找到");
            }
            
            const response = await fetch(`/api/diary/entries/${entry.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-UUID': uuid
                },
                body: JSON.stringify(entry)
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                return data.data;
            } else {
                throw new Error(data.message || "更新日记时出错");
            }
        } catch (error) {
            console.error("Error updating entry on server:", error);
            throw error;
        }
    },
    
    // Delete a diary entry
    async deleteEntry(entryId) {
        try {
            const uuid = localStorage.getItem('userUUID');
            if (!uuid) {
                throw new Error("用户ID未找到");
            }
            
            const response = await fetch(`/api/diary/entries/${entryId}`, {
                method: 'DELETE',
                headers: {
                    'X-User-UUID': uuid
                }
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                return true;
            } else {
                throw new Error(data.message || "删除日记时出错");
            }
        } catch (error) {
            console.error("Error deleting entry on server:", error);
            throw error;
        }
    }
};

// UI Functions
document.addEventListener('DOMContentLoaded', function() {
    console.log('Diary.js: DOM content loaded');
    
    // UI elements - with fallback creation if not found
    let diaryEntriesList = document.getElementById('diaryEntriesList');
    if (!diaryEntriesList) {
        console.warn('Creating diaryEntriesList element as it was not found');
        diaryEntriesList = document.createElement('div');
        diaryEntriesList.id = 'diaryEntriesList';
        diaryEntriesList.className = 'd-none';
        const mainContent = document.querySelector('#main-content .container .row .col-lg-10');
        if (mainContent) {
            mainContent.appendChild(diaryEntriesList);
        } else {
            document.body.appendChild(diaryEntriesList);
        }
    }
    
    let emptyDiaryState = document.getElementById('emptyDiaryState');
    if (!emptyDiaryState) {
        console.warn('Creating emptyDiaryState element as it was not found');
        emptyDiaryState = document.createElement('div');
        emptyDiaryState.id = 'emptyDiaryState';
        emptyDiaryState.className = 'text-center py-5 my-4 bg-light rounded';
        emptyDiaryState.innerHTML = `
            <div class="py-4">
                <i class="fas fa-book-open fa-4x text-muted mb-3"></i>
                <h3>还没有日记</h3>
                <p class="text-muted">点击"新建日记"按钮开始记录您的想法和回忆</p>
                <a href="/create-entry" id="emptyStateNewBtn" class="btn btn-primary mt-3">
                    <i class="fas fa-plus me-2"></i> 创建第一篇日记
                </a>
            </div>
        `;
        if (diaryEntriesList.parentNode) {
            diaryEntriesList.parentNode.insertBefore(emptyDiaryState, diaryEntriesList);
        } else {
            document.body.appendChild(emptyDiaryState);
        }
    }
    
    const diaryPagination = document.getElementById('diaryPagination');
    const newDiaryBtn = document.getElementById('newDiaryBtn');
    const emptyStateNewBtn = document.getElementById('emptyStateNewBtn') || 
                             emptyDiaryState.querySelector('#emptyStateNewBtn');
    const successAlert = document.getElementById('diarySuccessAlert');
    const successAlertMessage = document.getElementById('successAlertMessage');
    
    // Safely initialize Bootstrap modal
    let deleteDiaryModal = null;
    const deleteDiaryModalElement = document.getElementById('deleteDiaryModal');
    if (deleteDiaryModalElement) {
        try {
            deleteDiaryModal = new bootstrap.Modal(deleteDiaryModalElement);
            console.log("Delete diary modal initialized successfully");
        } catch (error) {
            console.error("Error initializing delete diary modal:", error);
        }
    } else {
        console.warn("Delete diary modal element not found in DOM");
    }
    
    const confirmDeleteDiaryBtn = document.getElementById('confirmDeleteDiaryBtn');
    
    let entries = [];
    
    // Helper to show success alert
    function showSuccess(message) {
        if (!successAlertMessage || !successAlert) {
            console.warn("Success alert elements not found, using window.alert instead");
            window.alert(message);
            return;
        }
        
        successAlertMessage.textContent = message;
        successAlert.classList.remove('d-none');
        setTimeout(() => {
            successAlert.classList.add('d-none');
        }, 3000);
    }
    
    // Format date for display
    function formatDate(dateString) {
        const options = { year: 'numeric', month: 'long', day: 'numeric' };
        return new Date(dateString).toLocaleDateString('zh-CN', options);
    }
    
    // Get mood emoji
    function getMoodEmoji(mood) {
        const moods = {
            'happy': '😊',
            'calm': '😌',
            'sad': '😢',
            'excited': '🤩',
            'angry': '😠',
            'tired': '😫',
            'nostalgic': '🥹'
        };
        return moods[mood] || '😌';
    }
    
    // Create diary entry element
    function createDiaryEntryElement(entry) {
        const entryElement = document.createElement('div');
        entryElement.className = 'diary-entry card mb-4' + (entry.pinned ? ' border-warning' : '');
        entryElement.innerHTML = `
            <div class="card-header d-flex justify-content-between align-items-center">
                <div>
                    <h2 class="h5 mb-0">${entry.title}</h2>
                    <small class="text-muted">${formatDate(entry.date)} · ${getMoodEmoji(entry.mood)}</small>
                </div>
                <div class="entry-actions">
                    ${entry.pinned ? '<span class="badge bg-warning me-2"><i class="fas fa-thumbtack"></i> 已置顶</span>' : ''}
                    <a href="/create-entry?edit=${entry.id}" class="btn btn-sm btn-outline-primary">
                        <i class="fas fa-edit"></i>
                    </a>
                    <button class="btn btn-sm btn-outline-danger delete-entry-btn" data-id="${entry.id}" data-title="${entry.title}">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </div>
            <div class="card-body">
                <div class="diary-content">${entry.content.replace(/\n/g, '<br>')}</div>
            </div>
        `;
        
        // Add delete event listener
        entryElement.querySelector('.delete-entry-btn').addEventListener('click', () => {
            openDeleteModal(entry);
        });
        
        return entryElement;
    }
    
    // Render all diary entries
    function renderEntries() {
        // Clear existing entries
        diaryEntriesList.innerHTML = '';
        
        // Sort entries: pinned first, then by date
        const sortedEntries = [...entries].sort((a, b) => {
            // First by pinned status
            if (a.pinned && !b.pinned) return -1;
            if (!a.pinned && b.pinned) return 1;
            
            // Then by date (newest first)
            return new Date(b.date) - new Date(a.date);
        });
        
        // Render each entry
        sortedEntries.forEach(entry => {
            diaryEntriesList.appendChild(createDiaryEntryElement(entry));
        });
        
        console.log(`Rendered ${sortedEntries.length} diary entries`);
    }
    
    // Load all diary entries
    async function loadEntries() {
        try {
            console.log('Loading diary entries...');
            entries = await DiaryAPI.getEntries();
            console.log(`Loaded ${entries.length} diary entries`);
            
            // Directly manage empty state here for clarity
            if (!entries || entries.length === 0) {
                console.log("No entries found, showing empty state");
                if (emptyDiaryState) {
                    emptyDiaryState.classList.remove('d-none');
                }
                if (diaryEntriesList) {
                    diaryEntriesList.classList.add('d-none');
                }
            } else {
                if (emptyDiaryState) {
                    emptyDiaryState.classList.add('d-none');
                }
                if (diaryEntriesList) {
                    diaryEntriesList.classList.remove('d-none');
                }
                renderEntries();
            }
        } catch (error) {
            console.error("Failed to load diary entries:", error);
            alert("加载日记失败: " + error.message);
            
            // On error, still show empty state
            if (emptyDiaryState) {
                emptyDiaryState.classList.remove('d-none');
            }
            if (diaryEntriesList) {
                diaryEntriesList.classList.add('d-none');
            }
        }
    }
    
    // Redirect to create entry page
    function redirectToCreatePage() {
        console.log('redirectToCreatePage called');
        try {
            window.location.href = '/create-entry';
            console.log('Redirecting to /create-entry');
        } catch (error) {
            console.error('Error redirecting:', error);
            // Fallback method
            window.open('/create-entry', '_self');
        }
    }
    
    // Open delete confirmation modal
    function openDeleteModal(entry) {
        // Handle case where modal might not be initialized
        if (!deleteDiaryModal) {
            console.error("Delete modal not available, using confirm dialog instead");
            if (confirm(`确定要删除 "${entry.title}" 吗？此操作不可撤销。`)) {
                deleteDiaryEntry(entry.id);
            }
            return;
        }
        
        try {
            // Set entry id and title
            const titleElement = document.getElementById('deleteDiaryTitle');
            if (titleElement) {
                titleElement.textContent = entry.title;
            }
            
            if (confirmDeleteDiaryBtn) {
                confirmDeleteDiaryBtn.dataset.entryId = entry.id;
            }
            
            // Show modal
            deleteDiaryModal.show();
        } catch (error) {
            console.error("Error showing delete modal:", error);
            // Fallback to simple confirmation
            if (confirm(`确定要删除 "${entry.title}" 吗？此操作不可撤销。`)) {
                deleteDiaryEntry(entry.id);
            }
        }
    }
    
    // Delete diary entry
    async function deleteDiaryEntry(entryId) {
        try {
            await DiaryAPI.deleteEntry(entryId);
            
            // Close modal if it exists
            if (deleteDiaryModal) {
                try {
                    deleteDiaryModal.hide();
                } catch (modalError) {
                    console.warn("Error hiding modal:", modalError);
                }
            }
            
            // Show success message
            showSuccess("日记已删除");
            
            // Reload entries
            await loadEntries();
        } catch (error) {
            console.error("Failed to delete diary entry:", error);
            alert("删除日记失败: " + error.message);
        }
    }
    
    // Initialize diary page
    async function initDiaryPage() {
        console.log('Initializing diary page');
        
        console.log('Empty state element present:', !!emptyDiaryState);
        console.log('Entries list element present:', !!diaryEntriesList);
                
        // Update user name in navigation if needed
        try {
            const userData = await UserSession.getSessionData();
            if (userData && userData.name) {
                const userNavLink = document.querySelector('.nav-item a[href="/profile"]');
                if (userNavLink) {
                    userNavLink.innerHTML = `<i class="fas fa-user me-1"></i> ${userData.name}`;
                }
            }
        } catch (error) {
            console.warn("Could not update user name in navigation:", error);
        }
        
        // Load all entries
        await loadEntries();
        
        // Setup event listeners for new and create buttons to redirect
        console.log('Setting up click event listeners for diary buttons');
        
        if (newDiaryBtn) {
            console.log('Found newDiaryBtn, attaching click handler');
            newDiaryBtn.addEventListener('click', function(event) {
                console.log('newDiaryBtn clicked');
                // Only prevent default if it's not an anchor tag
                if (newDiaryBtn.tagName !== 'A') {
                    event.preventDefault();
                }
                redirectToCreatePage();
            });
        } else {
            console.error('newDiaryBtn not found in the document!');
        }
        
        if (emptyStateNewBtn) {
            console.log('Found emptyStateNewBtn, attaching click handler');
            emptyStateNewBtn.addEventListener('click', function(event) {
                console.log('emptyStateNewBtn clicked');
                // Only prevent default if it's not an anchor tag
                if (emptyStateNewBtn.tagName !== 'A') {
                    event.preventDefault();
                }
                redirectToCreatePage();
            });
        } else {
            console.error('emptyStateNewBtn not found in the document!');
        }
        
        // Delete confirmation
        if (confirmDeleteDiaryBtn) {
            confirmDeleteDiaryBtn.addEventListener('click', function() {
                const entryId = this.dataset.entryId;
                if (entryId) {
                    deleteDiaryEntry(entryId);
                } else {
                    console.error("No entry ID found for delete operation");
                }
            });
        } else {
            console.warn("Confirm delete button not found");
        }
    }
    
    // Initialize on load
    initDiaryPage();
}); 