/**
 * User Session Management System
 * Handles device identification and user data persistence
 */

// Initialize database
const DB_NAME = "TimeCapsuleDB";
const DB_VERSION = 1;
const USER_STORE = "userProfile";

// Database initialization
function initializeDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    // Create/upgrade database structure
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      // Create user session store if it doesn't exist
      if (!db.objectStoreNames.contains(USER_STORE)) {
        const store = db.createObjectStore(USER_STORE, { keyPath: "id" });
        store.createIndex('uuid', 'uuid', { unique: true });
      }
    };
    
    request.onsuccess = (event) => {
      const db = event.target.result;
      console.log("Database initialized successfully");
      resolve(db);
    };
    request.onerror = (event) => {
      console.error("IndexedDB error:", event.target.error);
      reject("无法访问存储。将使用备用存储方式。");
    };
  });
}

// Get database connection
async function getDB() {
  return await initializeDB();
}

// Session data storage functions
const UserSession = {
  /**
   * Store user session data in multiple storage mechanisms for redundancy
   */
  async saveSessionData(data) {
    const sessionData = { ...data };
    
    // Primary storage: IndexedDB
    try {
      await this._saveToIndexedDB(sessionData);
    } catch (e) {
      console.error("Error saving to IndexedDB:", e);
    }
    
    // Backup storage 1: Cookies
    try {
      this._saveToCookies(sessionData);
    } catch (e) {
      console.error("Error saving to cookies:", e);
    }
    
    // Backup storage 2: localStorage
    try {
      localStorage.setItem('userSessionData', JSON.stringify(sessionData));
    } catch (e) {
      console.error("Error saving to localStorage:", e);
    }
    
    return sessionData;
  },
  
  /**
   * Get user session data with fallbacks
   */
  async getSessionData() {
    let sessionData = null;
    
    // Try IndexedDB first (primary storage)
    try {
      sessionData = await this._getFromIndexedDB();
      if (sessionData && sessionData.uuid) {
        return sessionData;
      }
    } catch (e) {
      console.warn("Could not retrieve session from IndexedDB:", e);
    }
    
    // Try localStorage next
    try {
      const localData = localStorage.getItem('userSessionData');
      if (localData) {
        sessionData = JSON.parse(localData);
        if (sessionData && sessionData.uuid) {
          // Restore to IndexedDB
          await this.saveSessionData(sessionData);
          return sessionData;
        }
      }
    } catch (e) {
      console.warn("Could not retrieve session from localStorage:", e);
    }
    
    // Try cookies last
    try {
      const cookieData = this._getFromCookies();
      if (cookieData && cookieData.uuid) {
        // Restore to other storage mechanisms
        await this.saveSessionData(cookieData);
        return cookieData;
      }
    } catch (e) {
      console.warn("Could not retrieve session from cookies:", e);
    }
    
    // No valid session found
    return null;
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
   * Initialize or retrieve user session
   */
  async initialize() {
    // Try to get existing session
    let sessionData = await this.getSessionData();
    
    // If no session exists, create one
    if (!sessionData || !sessionData.uuid) {
      const uuid = await this.requestNewUUID();
      sessionData = { uuid, name: null, age: null };
      await this.saveSessionData(sessionData);
    }
    
    return sessionData;
  },
  
  /**
   * Update user profile information
   */
  async updateUserProfile(name, age) {
    let sessionData = await this.getSessionData();
    
    if (!sessionData || !sessionData.uuid) {
      // No session found, initialize first
      sessionData = await this.initialize();
    }
    
    // Update user data
    sessionData.name = name;
    sessionData.age = age;
    
    // Save updated data
    await this.saveSessionData(sessionData);
    
    // Optionally sync with server
    try {
      await fetch('/api/users/profile', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-UUID': sessionData.uuid
        },
        body: JSON.stringify({ name, age })
      });
    } catch (e) {
      console.warn("Could not sync profile with server:", e);
      // Continue anyway, we have local storage
    }
    
    return sessionData;
  },
  
  // PRIVATE METHODS
  
  /**
   * Save data to IndexedDB
   */
  async _saveToIndexedDB(data) {
    const db = await getDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([USER_STORE], "readwrite");
      const store = transaction.objectStore(USER_STORE);
      
      // Update session data
      const request = store.put({ id: 1, ...data });
      
      request.onsuccess = () => {
        console.log("User profile saved successfully");
        // Also save to localStorage as backup
        localStorage.setItem('userProfile', JSON.stringify(data));
        resolve(data);
      };
      request.onerror = (event) => {
        console.error("Error saving profile:", event.target.error);
        reject("保存资料时出错");
      };
      
      // Close db when transaction complete
      transaction.oncomplete = () => db.close();
    });
  },
  
  /**
   * Get data from IndexedDB
   */
  async _getFromIndexedDB() {
    const db = await getDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([USER_STORE], "readonly");
      const store = transaction.objectStore(USER_STORE);
      
      // Get session data
      const request = store.get(1);
      
      request.onsuccess = (event) => {
        const result = event.target.result;
        if (result) {
          // Remove the key property for cleaner data
          const { id, ...sessionData } = result;
          resolve(sessionData);
        } else {
          resolve(null);
        }
      };
      
      request.onerror = (event) => reject(event.target.error);
      
      // Close db when transaction complete
      transaction.oncomplete = () => db.close();
    });
  },
  
  /**
   * Save data to cookies (backup method)
   */
  _saveToCookies(data) {
    // Set a long expiration (10 years)
    const expires = new Date();
    expires.setFullYear(expires.getFullYear() + 10);
    
    // Stringify data
    const serialized = JSON.stringify(data);
    
    // Set cookie with expiration
    document.cookie = `userUUID=${data.uuid};expires=${expires.toUTCString()};path=/;SameSite=Strict`;
    document.cookie = `userData=${encodeURIComponent(serialized)};expires=${expires.toUTCString()};path=/;SameSite=Strict`;
  },
  
  /**
   * Get data from cookies
   */
  _getFromCookies() {
    const uuidMatch = document.cookie.match(/userUUID=([^;]+)/);
    const dataMatch = document.cookie.match(/userData=([^;]+)/);
    
    if (uuidMatch && dataMatch) {
      try {
        return JSON.parse(decodeURIComponent(dataMatch[1]));
      } catch (e) {
        // If parsing fails, try to reconstruct from UUID
        if (uuidMatch[1]) {
          return { uuid: uuidMatch[1], name: null, age: null };
        }
      }
    } else if (uuidMatch) {
      // At least we have a UUID
      return { uuid: uuidMatch[1], name: null, age: null };
    }
    
    return null;
  },
  
  /**
   * Generate a UUID client-side (fallback if server is unreachable)
   */
  _generateClientUUID() {
    // Simple UUID v4 generation
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
};

// Export the session manager
window.UserSession = UserSession;

document.addEventListener('DOMContentLoaded', function() {
    const DB_NAME = 'TimeCapsuleDB';
    const DB_VERSION = 1;
    const USER_STORE = 'userProfile';
    let db;
    
    // Initialize IndexedDB
    function initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            
            request.onerror = function(event) {
                console.error("IndexedDB error:", event.target.error);
                reject("无法访问存储。将使用备用存储方式。");
            };
            
            request.onupgradeneeded = function(event) {
                const db = event.target.result;
                
                // Create object store for user profile if it doesn't exist
                if (!db.objectStoreNames.contains(USER_STORE)) {
                    const store = db.createObjectStore(USER_STORE, { keyPath: 'id' });
                    store.createIndex('uuid', 'uuid', { unique: true });
                }
            };
            
            request.onsuccess = function(event) {
                db = event.target.result;
                console.log("Database initialized successfully");
                resolve(db);
            };
        });
    }
    
    // Get UUID from localStorage or create new one
    function getOrCreateUUID() {
        let uuid = localStorage.getItem('userUUID');
        
        if (!uuid) {
            // Generate UUID (simplified version)
            uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
            localStorage.setItem('userUUID', uuid);
        }
        
        return uuid;
    }
    
    // Save user profile to IndexedDB
    function saveUserProfile(profile) {
        return new Promise((resolve, reject) => {
            if (!db) {
                reject("数据库未初始化");
                return;
            }
            
            const transaction = db.transaction([USER_STORE], 'readwrite');
            const store = transaction.objectStore(USER_STORE);
            
            // Use ID 1 for the single user profile
            profile.id = 1;
            profile.uuid = getOrCreateUUID();
            
            const request = store.put(profile);
            
            request.onsuccess = function() {
                console.log("User profile saved successfully");
                // Also save to localStorage as backup
                localStorage.setItem('userProfile', JSON.stringify(profile));
                resolve(profile);
            };
            
            request.onerror = function(event) {
                console.error("Error saving profile:", event.target.error);
                reject("保存资料时出错");
            };
        });
    }
    
    // Load user profile from IndexedDB
    function loadUserProfile() {
        return new Promise((resolve, reject) => {
            // First try to load from IndexedDB
            if (db) {
                const transaction = db.transaction([USER_STORE], 'readonly');
                const store = transaction.objectStore(USER_STORE);
                const request = store.get(1); // Get the single user profile
                
                request.onsuccess = function(event) {
                    if (request.result) {
                        console.log("User profile loaded from IndexedDB");
                        resolve(request.result);
                        return;
                    }
                    
                    // If not in IndexedDB, try localStorage
                    fallbackToLocalStorage();
                };
                
                request.onerror = function(event) {
                    console.error("Error loading profile from IndexedDB:", event.target.error);
                    fallbackToLocalStorage();
                };
            } else {
                fallbackToLocalStorage();
            }
            
            function fallbackToLocalStorage() {
                const profileJson = localStorage.getItem('userProfile');
                if (profileJson) {
                    try {
                        const profile = JSON.parse(profileJson);
                        console.log("User profile loaded from localStorage");
                        resolve(profile);
                    } catch (e) {
                        console.error("Error parsing profile from localStorage:", e);
                        resolve(null);
                    }
                } else {
                    console.log("No user profile found");
                    resolve(null);
                }
            }
        });
    }
    
    // Initialize the system
    async function initUserSystem() {
        try {
            await initDB();
            const profile = await loadUserProfile();
            
            if (profile) {
                updateUIWithProfile(profile);
            } else {
                console.log("No existing profile found");
            }
            
            setupProfileForm();
        } catch (error) {
            console.error("Error initializing user system:", error);
        }
    }
    
    // Update UI with user profile
    function updateUIWithProfile(profile) {
        // Only proceed if these elements exist on the page
        const profileNavItem = document.getElementById('profileNavItem');
        const authButtons = document.getElementById('authButtons');
        const navUserName = document.getElementById('navUserName');
        
        if (profileNavItem && authButtons) {
            profileNavItem.style.display = 'block';
            authButtons.style.display = 'none';
        }
        
        if (navUserName && profile.name) {
            navUserName.textContent = profile.name;
        }
        
        // Additional UI updates can be done here
        console.log("UI updated with profile:", profile);
    }
    
    // Setup profile form - now works with both modal and dedicated page
    function setupProfileForm() {
        // Check if we're on the profile page
        const isProfilePage = window.location.pathname === '/profile';
        
        const profileForm = isProfilePage 
            ? document.getElementById('profileForm')
            : document.getElementById('profileForm');
            
        if (profileForm) {
            // Pre-fill form if profile exists
            loadUserProfile().then(profile => {
                if (profile) {
                    const nameInput = document.getElementById('userName');
                    const ageInput = document.getElementById('userAge');
                    
                    if (nameInput && profile.name) nameInput.value = profile.name;
                    if (ageInput && profile.age) ageInput.value = profile.age;
                }
            });
            
            // Add form submission handler
            profileForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const nameInput = document.getElementById('userName');
                const ageInput = document.getElementById('userAge');
                
                if (!nameInput || !ageInput) {
                    console.error("Form inputs not found");
                    return;
                }
                
                const profile = {
                    name: nameInput.value.trim(),
                    age: parseInt(ageInput.value, 10) || null
                };
                
                if (!profile.name) {
                    alert("请输入您的名字");
                    return;
                }
                
                saveUserProfile(profile).then(savedProfile => {
                    updateUIWithProfile(savedProfile);
                    
                    if (isProfilePage) {
                        // If on profile page, show success message
                        const successAlert = document.getElementById('profileSuccessAlert');
                        if (successAlert) {
                            successAlert.classList.remove('d-none');
                            setTimeout(() => {
                                successAlert.classList.add('d-none');
                            }, 3000);
                        }
                    } else {
                        // If in modal, close it
                        const profileModal = bootstrap.Modal.getInstance(document.getElementById('profileModal'));
                        if (profileModal) profileModal.hide();
                    }
                }).catch(error => {
                    console.error("Error saving profile:", error);
                    alert("保存个人资料时出错，请重试。");
                });
            });
        }
    }
    
    // Start the user system
    initUserSystem();
}); 