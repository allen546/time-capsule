/**
 * Time Capsule - Diary System
 * Handles diary entry management with IndexedDB for local storage and server API sync.
 */

// Diary database store
const DIARY_STORE = "diaryEntries";

// Initialize IndexedDB for diary entries
function initializeDiaryDB() {
    return new Promise((resolve, reject) => {
        // Check if DB is already initialized
        if (!window.indexedDB) {
            reject("您的浏览器不支持本地存储，日记功能将无法正常工作。");
            return;
        }
        
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        
        // Handle version change (create/upgrade)
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            
            // Create diary store if it doesn't exist
            if (!db.objectStoreNames.contains(DIARY_STORE)) {
                const store = db.createObjectStore(DIARY_STORE, { keyPath: "id" });
                store.createIndex('date', 'date', { unique: false });
                store.createIndex('pinned', 'pinned', { unique: false });
            }
        };
        
        request.onsuccess = (event) => {
            const db = event.target.result;
            console.log("Diary database initialized successfully");
            resolve(db);
        };
        
        request.onerror = (event) => {
            console.error("IndexedDB error:", event.target.error);
            reject("无法访问本地存储");
        };
    });
}

// Save diary entries to IndexedDB
async function saveDiaryEntryLocal(entry) {
    const db = await initializeDiaryDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([DIARY_STORE], "readwrite");
        const store = transaction.objectStore(DIARY_STORE);
        
        const request = store.put(entry);
        
        request.onsuccess = () => {
            console.log("Diary entry saved locally");
            resolve(entry);
        };
        
        request.onerror = (event) => {
            console.error("Error saving diary entry:", event.target.error);
            reject("保存日记时出错");
        };
        
        transaction.oncomplete = () => db.close();
    });
}

// Get diary entries from IndexedDB
async function getDiaryEntriesLocal() {
    const db = await initializeDiaryDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([DIARY_STORE], "readonly");
        const store = transaction.objectStore(DIARY_STORE);
        
        const request = store.getAll();
        
        request.onsuccess = () => {
            const entries = request.result || [];
            resolve(entries);
        };
        
        request.onerror = (event) => {
            console.error("Error getting diary entries:", event.target.error);
            reject("获取日记时出错");
        };
        
        transaction.oncomplete = () => db.close();
    });
}

// Delete a diary entry from IndexedDB
async function deleteDiaryEntryLocal(entryId) {
    const db = await initializeDiaryDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([DIARY_STORE], "readwrite");
        const store = transaction.objectStore(DIARY_STORE);
        
        const request = store.delete(entryId);
        
        request.onsuccess = () => {
            console.log("Diary entry deleted locally");
            resolve(true);
        };
        
        request.onerror = (event) => {
            console.error("Error deleting diary entry:", event.target.error);
            reject("删除日记时出错");
        };
        
        transaction.oncomplete = () => db.close();
    });
}

// API functions
const DiaryAPI = {
    // Get all diary entries
    async getEntries() {
        try {
            // First try to get from server
            const uuid = localStorage.getItem('userUUID');
            if (!uuid) {
                throw new Error("用户ID未找到");
            }
            
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
                // Save to local storage for offline use
                for (const entry of data.data) {
                    await saveDiaryEntryLocal(entry);
                }
                return data.data;
            } else {
                throw new Error(data.message || "获取日记时出错");
            }
        } catch (error) {
            console.warn("Error fetching from server, using local data:", error);
            // Fallback to local database if server fails
            return await getDiaryEntriesLocal();
        }
    },
    
    // Create a new diary entry
    async createEntry(entry) {
        try {
            const uuid = localStorage.getItem('userUUID');
            if (!uuid) {
                throw new Error("用户ID未找到");
            }
            
            const response = await fetch('/api/diary/entries', {
                method: 'POST',
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
                // Save to local storage
                await saveDiaryEntryLocal(data.data);
                return data.data;
            } else {
                throw new Error(data.message || "创建日记时出错");
            }
        } catch (error) {
            console.warn("Error creating entry on server:", error);
            
            // Generate a temporary ID for local storage
            entry.id = entry.id || `temp_${Date.now()}`;
            entry.created_at = entry.created_at || new Date().toISOString();
            entry.updated_at = entry.updated_at || new Date().toISOString();
            entry.local_only = true;
            
            // Save locally only
            await saveDiaryEntryLocal(entry);
            return entry;
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
                // Update local storage
                await saveDiaryEntryLocal(data.data);
                return data.data;
            } else {
                throw new Error(data.message || "更新日记时出错");
            }
        } catch (error) {
            console.warn("Error updating entry on server:", error);
            
            // Update local entry
            entry.updated_at = new Date().toISOString();
            entry.local_only = true;
            
            // Save locally only
            await saveDiaryEntryLocal(entry);
            return entry;
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
                // Delete from local storage
                await deleteDiaryEntryLocal(entryId);
                return true;
            } else {
                throw new Error(data.message || "删除日记时出错");
            }
        } catch (error) {
            console.warn("Error deleting entry on server:", error);
            
            // Delete locally only
            await deleteDiaryEntryLocal(entryId);
            return true;
        }
    }
};

// UI Functions
document.addEventListener('DOMContentLoaded', function() {
    // UI elements
    const diaryEntriesList = document.getElementById('diaryEntriesList');
    const emptyDiaryState = document.getElementById('emptyDiaryState');
    const diaryPagination = document.getElementById('diaryPagination');
    const newDiaryBtn = document.getElementById('newDiaryBtn');
    const emptyStateNewBtn = document.getElementById('emptyStateNewBtn');
    const diaryEntryModal = new bootstrap.Modal(document.getElementById('diaryEntryModal'));
    const deleteDiaryModal = new bootstrap.Modal(document.getElementById('deleteDiaryModal'));
    const diaryForm = document.getElementById('diaryForm');
    const saveDiaryBtn = document.getElementById('saveDiaryBtn');
    const confirmDeleteDiaryBtn = document.getElementById('confirmDeleteDiaryBtn');
    const successAlert = document.getElementById('diarySuccessAlert');
    const successAlertMessage = document.getElementById('successAlertMessage');
    
    let editingEntryId = null;
    let entries = [];
    
    // Helper to show success alert
    function showSuccess(message) {
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
                    ${entry.local_only ? '<span class="badge bg-secondary me-2"><i class="fas fa-wifi-slash"></i> 未同步</span>' : ''}
                    <button class="btn btn-sm btn-outline-primary edit-entry-btn" data-id="${entry.id}">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger delete-entry-btn" data-id="${entry.id}" data-title="${entry.title}">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </div>
            <div class="card-body">
                <div class="diary-content">${entry.content.replace(/\n/g, '<br>')}</div>
            </div>
        `;
        
        // Add event listeners
        entryElement.querySelector('.edit-entry-btn').addEventListener('click', () => {
            openEditModal(entry);
        });
        
        entryElement.querySelector('.delete-entry-btn').addEventListener('click', () => {
            openDeleteModal(entry);
        });
        
        return entryElement;
    }
    
    // Render all diary entries
    function renderEntries() {
        // Clear existing entries
        diaryEntriesList.innerHTML = '';
        
        // Check if there are entries
        if (entries.length === 0) {
            emptyDiaryState.classList.remove('d-none');
            return;
        }
        
        // Hide empty state and render entries
        emptyDiaryState.classList.add('d-none');
        
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
    }
    
    // Load all diary entries
    async function loadEntries() {
        try {
            entries = await DiaryAPI.getEntries();
            renderEntries();
        } catch (error) {
            console.error("Failed to load diary entries:", error);
            alert("加载日记失败: " + error.message);
        }
    }
    
    // Open modal for new entry
    function openNewModal() {
        // Reset form
        diaryForm.reset();
        document.getElementById('diaryEntryId').value = '';
        document.getElementById('diaryModalLabel').textContent = '新建日记';
        
        // Set default date to today
        document.getElementById('diaryDate').valueAsDate = new Date();
        
        // Reset editing entry id
        editingEntryId = null;
        
        // Show modal
        diaryEntryModal.show();
    }
    
    // Open modal for editing
    function openEditModal(entry) {
        // Fill form with entry data
        document.getElementById('diaryEntryId').value = entry.id;
        document.getElementById('diaryTitle').value = entry.title;
        document.getElementById('diaryDate').value = entry.date;
        document.getElementById('diaryContent').value = entry.content;
        document.getElementById('diaryMood').value = entry.mood;
        document.getElementById('diaryPin').checked = entry.pinned;
        
        // Set modal title
        document.getElementById('diaryEntryModalLabel').textContent = '编辑日记';
        
        // Set editing entry id
        editingEntryId = entry.id;
        
        // Show modal
        diaryEntryModal.show();
    }
    
    // Open delete confirmation modal
    function openDeleteModal(entry) {
        // Set entry id and title
        document.getElementById('deleteDiaryTitle').textContent = entry.title;
        confirmDeleteDiaryBtn.dataset.entryId = entry.id;
        
        // Show modal
        deleteDiaryModal.show();
    }
    
    // Save diary entry
    async function saveDiaryEntry() {
        // Get form data
        const entryId = document.getElementById('diaryEntryId').value;
        const title = document.getElementById('diaryTitle').value.trim();
        const date = document.getElementById('diaryDate').value;
        const content = document.getElementById('diaryContent').value.trim();
        const mood = document.getElementById('diaryMood').value;
        const pinned = document.getElementById('diaryPin').checked;
        
        // Validate form
        if (!title) {
            alert("请输入日记标题");
            return;
        }
        
        if (!date) {
            alert("请选择日期");
            return;
        }
        
        if (!content) {
            alert("请输入日记内容");
            return;
        }
        
        try {
            let savedEntry;
            
            // Prepare entry data
            const entryData = {
                title,
                date,
                content,
                mood,
                pinned
            };
            
            if (editingEntryId) {
                // Update existing entry
                entryData.id = editingEntryId;
                savedEntry = await DiaryAPI.updateEntry(entryData);
                showSuccess("日记已更新");
            } else {
                // Create new entry
                savedEntry = await DiaryAPI.createEntry(entryData);
                showSuccess("日记已保存");
            }
            
            // Close modal
            diaryEntryModal.hide();
            
            // Reload entries
            await loadEntries();
        } catch (error) {
            console.error("Failed to save diary entry:", error);
            alert("保存日记失败: " + error.message);
        }
    }
    
    // Delete diary entry
    async function deleteDiaryEntry(entryId) {
        try {
            await DiaryAPI.deleteEntry(entryId);
            
            // Close modal
            deleteDiaryModal.hide();
            
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
        // Load all entries
        await loadEntries();
        
        // Setup event listeners
        newDiaryBtn.addEventListener('click', openNewModal);
        emptyStateNewBtn.addEventListener('click', openNewModal);
        saveDiaryBtn.addEventListener('click', saveDiaryEntry);
        
        // Delete confirmation
        confirmDeleteDiaryBtn.addEventListener('click', function() {
            const entryId = this.dataset.entryId;
            if (entryId) {
                deleteDiaryEntry(entryId);
            }
        });
    }
    
    // Initialize on load
    initDiaryPage();
}); 