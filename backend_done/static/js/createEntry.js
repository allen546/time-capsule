/**
 * Time Capsule - Create Entry Page
 * Handles the creation and editing of diary entries.
 */

// Ensure DiaryAPI is imported or defined
if (typeof DiaryAPI === 'undefined') {
    console.error('DiaryAPI is not defined! Make sure to load the diary.js file before createEntry.js');
    
    // Define a fallback DiaryAPI object to prevent errors
    const DiaryAPI = {
        getEntries: async function() {
            console.error('Using fallback DiaryAPI.getEntries');
            return [];
        },
        createEntry: async function(entry) {
            console.error('Using fallback DiaryAPI.createEntry');
            alert('Unable to save entry. Please try again later.');
            return entry;
        },
        updateEntry: async function(entry) {
            console.error('Using fallback DiaryAPI.updateEntry');
            alert('Unable to update entry. Please try again later.');
            return entry;
        }
    };
}

// Log that the script is being loaded
console.log('Create Entry script is loading...');

document.addEventListener('DOMContentLoaded', function() {
    // Log page initialization
    console.log('Create Entry page initialized');
    
    // Check if userUUID exists in localStorage
    const currentUUID = localStorage.getItem('userUUID');
    console.log('Current UUID in localStorage:', currentUUID);
    
    // If no UUID, try to get it from UserSession and save it
    if (!currentUUID) {
        console.warn('No UUID found in localStorage, attempting to retrieve from UserSession');
        try {
            // Initialize the user session first
            UserSession.initialize().then(sessionData => {
                if (sessionData && sessionData.uuid) {
                    console.log('Retrieved UUID from UserSession:', sessionData.uuid);
                    localStorage.setItem('userUUID', sessionData.uuid);
                } else {
                    console.error('Could not get UUID from UserSession');
                    
                    // Emergency fallback - generate a temporary UUID
                    const tempUUID = 'temp-' + Date.now() + '-' + Math.random().toString(36).substring(2, 15);
                    console.warn('Using emergency temporary UUID:', tempUUID);
                    localStorage.setItem('userUUID', tempUUID);
                }
            }).catch(error => {
                console.error('Error initializing UserSession:', error);
            });
        } catch (e) {
            console.error('Error accessing UserSession:', e);
        }
    }
    
    // UI elements
    const createEntryForm = document.getElementById('createEntryForm');
    const diaryEntryId = document.getElementById('diaryEntryId');
    const diaryTitle = document.getElementById('diaryTitle');
    const diaryDate = document.getElementById('diaryDate');
    const diaryContent = document.getElementById('diaryContent');
    const diaryMood = document.getElementById('diaryMood');
    const diaryPin = document.getElementById('diaryPin');
    const saveEntryBtn = document.getElementById('saveEntryBtn');
    const entrySuccessAlert = document.getElementById('entrySuccessAlert');
    const successAlertMessage = document.getElementById('successAlertMessage');
    
    // Debug logs for UI elements
    console.log('Form element exists:', !!createEntryForm);
    console.log('Save button exists:', !!saveEntryBtn);
    
    // Get query parameters to check if we're editing
    const urlParams = new URLSearchParams(window.location.search);
    const editId = urlParams.get('edit');
    console.log('Edit ID from URL:', editId);
    
    // Set default date to today
    if (diaryDate) {
        diaryDate.valueAsDate = new Date();
    } else {
        console.error('Date input element not found');
    }
    
    // Helper to show success alert
    function showSuccess(message) {
        if (!successAlertMessage || !entrySuccessAlert) {
            console.error('Success alert elements not found');
            alert(message); // Fallback to regular alert
            return;
        }
        
        successAlertMessage.textContent = message;
        entrySuccessAlert.classList.remove('d-none');
        setTimeout(() => {
            entrySuccessAlert.classList.add('d-none');
        }, 3000);
    }
    
    // Load entry if editing
    async function loadEntryForEdit(entryId) {
        try {
            console.log('Loading entry for edit:', entryId);
            // Get diary entries from local storage or server
            const entries = await DiaryAPI.getEntries();
            console.log('Got entries:', entries.length);
            const entry = entries.find(e => e.id === entryId);
            
            if (!entry) {
                console.error("Entry not found:", entryId);
                alert("无法找到要编辑的日记");
                window.location.href = '/diary';
                return;
            }
            
            console.log('Found entry to edit:', entry.title);
            
            // Fill form with entry data
            diaryEntryId.value = entry.id;
            diaryTitle.value = entry.title;
            diaryDate.value = entry.date;
            diaryContent.value = entry.content;
            if (diaryMood) diaryMood.value = entry.mood || 'calm';
            if (diaryPin) diaryPin.checked = entry.pinned;
            
            // Update page title
            document.title = `编辑日记: ${entry.title} - 时光胶囊`;
            const heading = document.querySelector('h1');
            if (heading) {
                heading.innerHTML = `<i class="fas fa-edit me-2"></i> 编辑日记`;
            }
            
        } catch (error) {
            console.error("Error loading entry for edit:", error);
            alert("加载日记失败: " + error.message);
        }
    }
    
    // Save diary entry
    async function saveEntry() {
        console.log('Save entry function called');
        
        if (!diaryTitle || !diaryDate || !diaryContent) {
            console.error('Required form elements not found');
            alert('表单元素没有找到，无法保存日记');
            return;
        }
        
        // Validate form
        if (!diaryTitle.value.trim()) {
            alert("请输入日记标题");
            diaryTitle.focus();
            return;
        }
        
        if (!diaryDate.value) {
            alert("请选择日期");
            diaryDate.focus();
            return;
        }
        
        if (!diaryContent.value.trim()) {
            alert("请输入日记内容");
            diaryContent.focus();
            return;
        }
        
        // Get the save button
        const saveButton = document.getElementById('saveEntryBtn');
        // Disable button and show loading state to prevent multiple submissions
        if (saveButton) {
            saveButton.disabled = true;
            saveButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 保存中...';
        }
        
        try {
            // Prepare entry data
            const entryData = {
                title: diaryTitle.value.trim(),
                date: diaryDate.value,
                content: diaryContent.value.trim(),
                mood: diaryMood ? diaryMood.value : 'calm',
                pinned: diaryPin ? diaryPin.checked : false
            };
            
            console.log('Saving entry data:', entryData);
            
            // Check if editing existing or creating new
            if (diaryEntryId && diaryEntryId.value) {
                // Update existing entry
                entryData.id = diaryEntryId.value;
                await DiaryAPI.updateEntry(entryData);
                showSuccess("日记已更新");
            } else {
                // Create new entry
                await DiaryAPI.createEntry(entryData);
                showSuccess("日记已保存");
            }
            
            // Clear form after successful save
            if (createEntryForm && (!diaryEntryId || !diaryEntryId.value)) {
                createEntryForm.reset();
                if (diaryDate) diaryDate.valueAsDate = new Date();
            }
            
            // Redirect back to diary list after a short delay
            setTimeout(() => {
                window.location.href = '/diary';
            }, 1500);
            
        } catch (error) {
            console.error("Failed to save diary entry:", error);
            alert("保存日记失败: " + error.message);
            
            // Re-enable button on error
            if (saveButton) {
                saveButton.disabled = false;
                saveButton.innerHTML = '<i class="fas fa-save me-1"></i> 保存日记';
            }
        }
    }
    
    // Setup event listeners
    console.log('Setting up event listeners');
    
    if (saveEntryBtn) {
        console.log('Adding click event to saveEntryBtn');
        saveEntryBtn.addEventListener('click', function(e) {
            console.log('Save button clicked');
            e.preventDefault();
            saveEntry();
        });
    } else {
        console.error('Save button not found!');
        
        // Try to find the button by alternative ways if needed
        const anySubmitBtn = document.querySelector('button[type="submit"], button.btn-primary');
        if (anySubmitBtn) {
            console.log('Found alternative submit button');
            anySubmitBtn.addEventListener('click', function(e) {
                console.log('Alternative save button clicked');
                e.preventDefault();
                saveEntry();
            });
        }
    }
    
    // Handle form submission (prevent default)
    if (createEntryForm) {
        createEntryForm.addEventListener('submit', (e) => {
            console.log('Form submission detected');
            e.preventDefault();
            saveEntry();
        });
    } else {
        console.error('Form element not found!');
    }
    
    // Check if we're editing an entry
    if (editId) {
        loadEntryForEdit(editId);
    }
});

// Add a global error handler
window.addEventListener('error', function(e) {
    console.error('Global error caught in createEntry.js:', e.error);
}); 