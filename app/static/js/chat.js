/**
 * Chat System for Time Capsule
 * Handles messaging via AJAX and voice input for elderly users.
 */

// Ensure UserSession exists
if (typeof UserSession === 'undefined') {
    console.error('UserSession not found! Make sure userSession.js is loaded before chat.js');
    // Create minimal version to prevent errors
    window.UserSession = {
        getSessionData: async function() {
            const uuid = localStorage.getItem('userUUID');
            return uuid ? { uuid } : null;
        },
        initialize: async function() {
            const uuid = localStorage.getItem('userUUID');
            if (uuid) return { uuid };
            
            // Fallback to fetch a new UUID if needed
            try {
                const response = await fetch('/api/users/generate-uuid', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem('userUUID', data.uuid);
                    return { uuid: data.uuid };
                }
            } catch (e) {
                console.error("Failed to get UUID:", e);
            }
            return null;
        }
    };
}

// Chat configuration
let currentSessionId = null;  // Will be set to user-specific ID during initialization
let isRecording = false;
let recordingTimer = null;
let recordingTime = 0;
let recognition = null;
let messagesSent = 0;
let messagesReceived = 0;
let clientId = generateShortId();
let isPendingResponse = false;
let messageQueue = [];
let reconnectAttempts = 0;
let maxReconnectAttempts = 5;

// Log levels
const LOG_LEVEL = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3
};

// Current log level - change to adjust verbosity
const CURRENT_LOG_LEVEL = LOG_LEVEL.INFO;

// DOM elements
const chatInput = document.getElementById('chatInput');
const sendMessageBtn = document.getElementById('sendMessageBtn');
const voiceInputBtn = document.getElementById('voiceInputBtn');
const chatMessages = document.getElementById('chatMessages');
const currentChatTitle = document.getElementById('currentChatTitle');
const emptyChatState = document.getElementById('emptyChatState');
const clearChatBtn = document.getElementById('clearChatBtn');
const recordingStatus = document.getElementById('recordingStatus');
const recordingTimeElement = document.getElementById('recordingTime');
const loadingIndicator = document.getElementById('loadingIndicator');

// Initialize chat functionality when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', async () => {
    logInfo('Chat system initializing...');
    
    // Add connection info to window object for debugging
    window.chatDebug = {
        getConnectionInfo: getConnectionInfo,
        reconnect: resetAndReconnect,
        logLevel: CURRENT_LOG_LEVEL,
        flushQueue: processMessageQueue
    };
    
    // Initialize components
    await initChat();
    setupEventListeners();
    initSpeechRecognition();
    
    // Create loading indicator if it doesn't exist
    if (!loadingIndicator) {
        const indicator = document.createElement('div');
        indicator.id = 'loadingIndicator';
        indicator.className = 'loading-indicator';
        indicator.innerHTML = '<div class="spinner"></div><div class="loading-text">思考中...</div>';
        indicator.style.display = 'none';
        document.body.appendChild(indicator);
    }
    
    // Ensure chat is scrolled to bottom when page loads
    scrollToBottom();
    
    // Add an additional scroll event after all resources are loaded
    window.addEventListener('load', () => {
        setTimeout(scrollToBottom, 500);
    });
});

/**
 * Initialize the chat system
 */
async function initChat() {
    try {
        // Get user session data from the global UserSession object
        let sessionData = await UserSession.getSessionData();
        
        // If no session data, try to initialize one
        if (!sessionData || !sessionData.uuid) {
            logInfo('No session data found, initializing...');
            sessionData = await UserSession.initialize();
        }
        
        if (!sessionData || !sessionData.uuid) {
            logError('Cannot initialize user session, redirecting to profile page');
            window.location.href = '/profile';
            return;
        }
        
        // Explicitly log the UUID and verify it exists
        logInfo(`Initializing chat for user UUID: ${sessionData.uuid}`);
        
        // Ensure UUID is properly stored in localStorage for API calls
        localStorage.setItem('userUUID', sessionData.uuid);
        
        // Verify the UUID is actually set correctly
        const storedUUID = localStorage.getItem('userUUID');
        if (!storedUUID) {
            logError('Failed to store user UUID in localStorage');
            window.location.href = '/profile';
            return;
        }
        
        if (storedUUID !== sessionData.uuid) {
            logWarn(`UUID mismatch: sessionData.uuid (${sessionData.uuid}) doesn't match localStorage (${storedUUID})`);
            // Force synchronize
            localStorage.setItem('userUUID', sessionData.uuid);
        }
        
        // Generate a user-specific session ID
        currentSessionId = generateSessionId(sessionData.uuid);
        logInfo(`Using chat session ID: ${currentSessionId}`);
        
        // Update chat title if needed
        if (currentChatTitle) {
            currentChatTitle.textContent = "与20岁的自己对话";
        }
        
        // Load previous messages from this session or show initial welcome
        const hasMessages = await loadChatMessages(currentSessionId);
        
        // If there were no messages loaded, show a welcome message
        if (!hasMessages) {
            // Add a welcome message from the AI to explain what happened
            const welcomeMessage = `欢迎来到新的聊天会话！请开始输入您的消息，与20岁的自己对话吧！`;
            addMessageToChat(welcomeMessage, false);
            
            // Hide the empty state since we're showing a welcome message
            emptyChatState.style.display = 'none';
        }
        
        logInfo('Chat system initialized successfully');
    } catch (error) {
        logError('Error initializing chat:', error);
        showError('无法初始化聊天系统，请稍后再试');
    }
}

/**
 * Generate a predictable session ID based on user UUID
 * This ensures the same user always gets the same session ID
 */
function generateSessionId(userUuid) {
    if (!userUuid) return 'default-session';
    
    // We'll use a temporary placeholder session ID
    // The actual session ID will be determined during loadChatMessages
    // when we query the database for existing sessions
    return userUuid;
}

/**
 * Generate a unique ID
 */
function generateShortId() {
    return Math.random().toString(36).substring(2, 10);
}

/**
 * Set up event listeners for chat interactions
 */
function setupEventListeners() {
    logDebug('Setting up event listeners');
    
    // Send message on button click
    sendMessageBtn.addEventListener('click', sendMessage);
    
    // Send message on Enter key (but allow Shift+Enter for new line)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Voice input button
    voiceInputBtn.addEventListener('click', toggleVoiceInput);
    
    // Clear chat - check if the button exists first
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', clearChat);
    } else {
        logInfo('Clear chat button not found in the DOM');
    }
    
    logDebug('Event listeners set up complete');
}

/**
 * Get connection diagnostic information
 */
function getConnectionInfo() {
    return {
        clientId,
        messagesSent,
        messagesReceived,
        queueLength: messageQueue.length,
        isPendingResponse,
        reconnectAttempts,
        sessionId: currentSessionId,
        userUUID: localStorage.getItem('userUUID')
    };
}

/**
 * API request with cache busting
 * Wraps fetch with proper headers and cache control
 */
async function apiRequest(url, options = {}) {
    // Ensure options has the structure we need
    options = {
        method: 'GET',
        headers: {},
        ...options
    };
    
    // Ensure headers exist
    options.headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    // Add cache control headers
    options.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
    options.headers['Pragma'] = 'no-cache';
    options.headers['Expires'] = '0';
    
    // Add timestamp to URL for GET requests to prevent caching
    if (options.method === 'GET') {
        const separator = url.includes('?') ? '&' : '?';
        url = `${url}${separator}_t=${Date.now()}`;
    }
    
    logDebug(`API Request: ${options.method} ${url}`);
    return fetch(url, options);
}

/**
 * Load chat messages for a session
 */
async function loadChatMessages(sessionId) {
    if (!sessionId) {
        logWarn('No session ID provided to loadChatMessages');
        return false;
    }
    
    try {
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            logError('Fatal error: No user UUID found in localStorage during loadChatMessages');
            throw new Error('No user UUID found');
        }
        
        logInfo(`Loading chat messages for user ${userUUID}, using user UUID as session ID`);
        
        // Always use the user's UUID as the session ID
        currentSessionId = userUUID;
        
        // Clear chat display
        chatMessages.innerHTML = '';
        
        // Remove loaded class while loading
        chatMessages.classList.remove('loaded');
        
        // Show loading indicator
        showLoadingIndicator();
        
        // Explicitly log the headers we're going to send
        const headers = {
            'X-User-UUID': userUUID
        };
        logInfo(`API Request headers for messages:`, headers);
        
        // Always directly fetch messages using the user UUID as session ID
        logInfo(`Directly fetching messages for user session ${currentSessionId}`);
        const response = await apiRequest(`/api/chat/sessions/${currentSessionId}/messages`, {
            method: 'GET',
            headers: headers
        });
        
        logInfo(`Messages API Response status: ${response.status}, ${response.statusText}`);
        
        if (response.status === 404) {
            logInfo(`No chat session found for ${userUUID}, creating one`);
            
            // Create a session with the user UUID as ID
            const createResponse = await apiRequest('/api/chat/sessions', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ user_uuid: userUUID, session_id: userUUID })
            });
            
            if (!createResponse.ok) {
                logWarn(`Failed to create session: ${createResponse.status}, continuing with empty chat`);
            } else {
                logInfo(`Created user session: ${userUUID}`);
            }
            
            // Show empty state
            emptyChatState.style.display = 'flex';
            hideLoadingIndicator();
            return false;
        }
        
        if (!response.ok) {
            logError(`Messages fetch failed with status: ${response.status}, ${response.statusText}`);
            throw new Error(`Server responded with ${response.status}`);
        }
        
        // Get raw response text for debugging
        const rawResponseText = await response.text();
        logInfo(`Raw messages response: ${rawResponseText.substring(0, 200)}...`);
        
        // Parse as JSON
        let data;
        try {
            data = JSON.parse(rawResponseText);
        } catch (e) {
            logError(`Error parsing messages response as JSON: ${e.message}`);
            throw new Error(`Invalid JSON in server response: ${e.message}`);
        }
        
        logInfo(`Received chat history for session ${currentSessionId}`);
        
        // Extract messages from the response, handling different response formats
        let messages = [];
        
        if (data.status === 'success' && Array.isArray(data.data)) {
            messages = data.data;
        } else if (Array.isArray(data)) {
            messages = data;
        } else if (data.data && Array.isArray(data.data)) {
            messages = data.data;
        } else if (data.messages && Array.isArray(data.messages)) {
            messages = data.messages;
        }
        
        logInfo(`Extracted ${messages.length} messages from response for session ${currentSessionId}`);
        
        // If we have messages, display them
        if (messages.length > 0) {
            emptyChatState.style.display = 'none';
            
            // Process and display each message
            logInfo(`Processing ${messages.length} messages to display`);
            for (const msg of messages) {
                const isUser = msg.is_user;
                const content = msg.content || msg.message;
                const timestamp = msg.created_at || msg.timestamp || new Date().toISOString();
                const isError = content && content.startsWith('Error:');
                const isMock = content && (content.startsWith('Echo:') || content.includes('this is just a mock response'));
                
                logDebug(`Adding message to chat: ${isUser ? 'User' : 'AI'}, ${new Date(timestamp).toISOString()}, ${content.substring(0, 30)}...`);
                
                // Add with appropriate styling
                addMessageToChat(content, isUser, new Date(timestamp), isError, isMock);
            }
            
            // Mark chat as loaded to trigger CSS auto-scroll
            markChatAsLoaded();
            
            // Ensure chat is scrolled to bottom with history
            scrollToBottom();
            
            // Hide empty state since we have messages
            emptyChatState.style.display = 'none';
            
            hideLoadingIndicator();
            logInfo(`Successfully loaded ${messages.length} messages for session ${currentSessionId}`);
            return true;
        } else {
            // No messages found
            logInfo(`No messages found in session ${currentSessionId}`);
            emptyChatState.style.display = 'flex';
            hideLoadingIndicator();
            return false;
        }
    } catch (error) {
        logError(`Error loading chat messages for session ${sessionId}:`, error);
        showError('无法加载聊天记录，请刷新页面重试');
        
        // Hide loading indicator
        hideLoadingIndicator();
        
        // Show empty state on error
        emptyChatState.style.display = 'flex';
        return false;
    }
}

/**
 * Reset connection and retry
 */
function resetAndReconnect() {
    reconnectAttempts = 0;
    processMessageQueue();
}

/**
 * Send message from input field
 */
async function sendMessage() {
    // Get message from input
    const message = chatInput.value.trim();
    if (!message) return;
    
    // Clear input field
    chatInput.value = '';
    
    try {
        // Add user message to chat
        addMessageToChat(message, true);
        
        // If chat was empty, hide the empty state
        emptyChatState.style.display = 'none';
        
        // Ensure scroll is at bottom after adding message
        scrollToBottom();
        
        // Count messages sent
        messagesSent++;
        
        // Check if we're already processing a message
        if (isPendingResponse) {
            logInfo('Another message is being processed, queueing this one');
            messageQueue.push(message);
            return;
        }
        
        // Mark that we're processing a response
        isPendingResponse = true;
        
        // Send message to the server
        await sendUserMessage(message);
    } catch (error) {
        logError('Error in message handling:', error);
    }
}

/**
 * Process any messages in the queue
 */
async function processMessageQueue() {
    // Check if we're already processing a message
    if (isPendingResponse) {
        logInfo('Already processing a message, waiting for response');
        return;
    }
    
    // Check if the queue is empty
    if (messageQueue.length === 0) {
        logInfo('Message queue is empty');
        return;
    }
    
    // Get the next message
    const message = messageQueue.shift();
    logInfo(`Processing message from queue (${messageQueue.length} remaining)`);
    
    try {
        // Mark that we're processing a response
        isPendingResponse = true;
        
        // Send message to the server
        await sendUserMessage(message);
    } catch (error) {
        logError('Error processing queued message:', error);
        
        // Continue with next message after a short delay
        setTimeout(processMessageQueue, 1000);
    }
}

/**
 * Add a message to the chat display
 * @param {string} message - The message content
 * @param {boolean} isUserMessage - Whether this is a user message
 * @param {Date} timestamp - Message timestamp
 * @param {boolean} isError - Whether this is an error message
 * @param {boolean} isMock - Whether this is a mock response
 */
function addMessageToChat(message, isUserMessage, timestamp = new Date(), isError = false, isMock = false) {
    // Create message element
    const messageContainer = document.createElement('div');
    
    // Add appropriate classes
    let classes = ['message'];
    if (isUserMessage) {
        classes.push('user-message');
    } else {
        classes.push('ai-message');
        
        if (isError) {
            classes.push('error-message');
        } else if (isMock) {
            classes.push('mock-message');
        }
    }
    
    messageContainer.className = classes.join(' ');
    
    // Format timestamp
    const formattedTime = formatTime(timestamp);
    
    // Add content with timestamp
    messageContainer.innerHTML = `
        <div class="message-content">${formatMessage(message)}</div>
        <div class="message-time">${formattedTime}</div>
    `;
    
    // Add to chat
    chatMessages.appendChild(messageContainer);
    
    // Mark chat as loaded to trigger CSS auto-scroll
    markChatAsLoaded();
    
    // Scroll to bottom
    scrollToBottom();
}

/**
 * Format the message text with simple Markdown-like syntax
 */
function formatMessage(message) {
    // Convert linebreaks to <br>
    let formatted = message.replace(/\n/g, '<br>');
    
    // Simple formatting for bold and italics
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    return formatted;
}

/**
 * Format timestamp as HH:MM
 */
function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Extremely robust scroll-to-bottom implementation
 * Makes multiple attempts with different techniques to ensure scrolling works
 */
function scrollToBottom() {
    // Get the chat messages element
    const messages = document.getElementById('chatMessages');
    if (!messages) return;
    
    // First immediate scroll attempt with multiple methods
    if (messages.scrollTo) {
        messages.scrollTo({ top: messages.scrollHeight, behavior: 'auto' });
    }
    messages.scrollTop = messages.scrollHeight;
    
    // Force body scroll as well for mobile browsers
    window.scrollTo(0, document.body.scrollHeight);
    
    // Use requestAnimationFrame for a better-timed scroll after layout/paint
    window.requestAnimationFrame(() => {
        messages.scrollTop = messages.scrollHeight;
        window.scrollTo(0, document.body.scrollHeight);
    });
    
    // Create a series of increasingly delayed scroll attempts to handle dynamic content
    const scrollAttempts = [10, 100, 300, 500, 1000, 2000];
    
    // Apply multiple techniques at each interval
    scrollAttempts.forEach(delay => {
        setTimeout(() => {
            // Standard scroll
            if (messages) {
                messages.scrollTop = messages.scrollHeight;
                
                // Try smooth scrolling API
                if (messages.scrollTo) {
                    messages.scrollTo({
                        top: messages.scrollHeight,
                        behavior: 'smooth'
                    });
                }
                
                // Force body scroll as well for mobile browsers
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
                
                // Try scrollIntoView on the last message
                const lastMessage = messages.lastElementChild;
                if (lastMessage) {
                    lastMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            }
        }, delay);
    });
}

/**
 * Clear chat history
 */
async function clearChat() {
    try {
        if (!confirm('确定要清空聊天记录吗？')) {
            return;
        }
        
        // Get user UUID
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            throw new Error('No user UUID found');
        }
        
        // Delete chat session via API
        const response = await apiRequest(`/api/chat/sessions/${currentSessionId}`, {
            method: 'DELETE',
            headers: {
                'X-User-UUID': userUUID
            }
        });
        
        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }
        
        // Clear chat display
        chatMessages.innerHTML = '';
        
        // Show empty state
        emptyChatState.style.display = 'flex';
        
        logInfo('Chat history cleared');
    } catch (error) {
        logError('Error clearing chat:', error);
        showError('清空聊天记录失败，请稍后再试');
    }
}

/**
 * Toggle voice input recording
 */
function toggleVoiceInput() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

/**
 * Initialize speech recognition
 */
function initSpeechRecognition() {
    try {
        // Check for browser support
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            logWarn('Speech recognition not supported');
            voiceInputBtn.style.display = 'none';
            return;
        }
        
        // Create recognition object
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        
        // Configure
        recognition.lang = 'zh-CN';
        recognition.continuous = true;
        recognition.interimResults = true;
        
        // Handle results
        recognition.onresult = function(event) {
            let finalTranscript = '';
            let interimTranscript = '';
            
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }
            
            // Update chat input with recognized text
            if (finalTranscript) {
                chatInput.value = finalTranscript;
            } else if (interimTranscript) {
                chatInput.value = interimTranscript;
            }
        };
        
        // Handle errors
        recognition.onerror = function(event) {
            logError('Speech recognition error:', event.error);
            stopRecording();
            
            if (event.error === 'not-allowed') {
                showError('麦克风访问被拒绝，请允许浏览器使用麦克风');
            } else {
                showError('语音识别出错，请稍后再试');
            }
        };
        
        // Handle end of recording
        recognition.onend = function() {
            stopRecording();
        };
        
        logInfo('Speech recognition initialized');
    } catch (error) {
        logError('Error initializing speech recognition:', error);
        voiceInputBtn.style.display = 'none';
    }
}

/**
 * Start voice recording
 */
function startRecording() {
    try {
        if (!recognition) {
            showError('语音识别不可用');
            return;
        }
        
        recognition.start();
        isRecording = true;
        
        // Update UI
        voiceInputBtn.classList.add('recording');
        recordingStatus.style.display = 'flex';
        
        // Start timer
        recordingTime = 0;
        updateRecordingTime();
        recordingTimer = setInterval(updateRecordingTime, 1000);
        
        logInfo('Voice recording started');
    } catch (error) {
        logError('Error starting recording:', error);
        stopRecording();
        showError('无法开始语音录制，请稍后再试');
    }
}

/**
 * Stop voice recording
 */
function stopRecording() {
    try {
        if (recognition) {
            recognition.stop();
        }
        
        isRecording = false;
        
        // Update UI
        voiceInputBtn.classList.remove('recording');
        recordingStatus.style.display = 'none';
        
        // Stop timer
        if (recordingTimer) {
            clearInterval(recordingTimer);
            recordingTimer = null;
        }
        
        logInfo('Voice recording stopped');
    } catch (error) {
        logError('Error stopping recording:', error);
    }
}

/**
 * Update recording time display
 */
function updateRecordingTime() {
    recordingTime++;
    
    const minutes = Math.floor(recordingTime / 60);
    const seconds = recordingTime % 60;
    
    recordingTimeElement.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    // Auto-stop after 60 seconds
    if (recordingTime >= 60) {
        stopRecording();
        showError('录音时间过长，已自动停止');
    }
}

/**
 * Show loading indicator
 */
function showLoadingIndicator() {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) {
        indicator.style.display = 'flex';
    }
}

/**
 * Hide loading indicator
 */
function hideLoadingIndicator() {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
}

/**
 * Show error message
 */
function showError(message) {
    // Create error element if it doesn't exist
    let errorElement = document.getElementById('errorMessage');
    
    if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.id = 'errorMessage';
        errorElement.className = 'error-message';
        document.body.appendChild(errorElement);
    }
    
    // Set message and show
    errorElement.textContent = message;
    errorElement.style.display = 'flex';
    
    // Hide after 5 seconds
    setTimeout(() => {
        errorElement.style.display = 'none';
    }, 5000);
    
    logWarn(`Displayed error: ${message}`);
}

/**
 * Logging functions with configurable level
 */
function logDebug(...args) {
    if (CURRENT_LOG_LEVEL <= LOG_LEVEL.DEBUG) {
        const timestamp = new Date().toISOString();
        const sessionInfo = currentSessionId ? `[Session: ${currentSessionId.substring(0, 8)}]` : '[No Session]';
        console.debug(`[Chat][${timestamp}]${sessionInfo}`, ...args);
    }
}

function logInfo(...args) {
    if (CURRENT_LOG_LEVEL <= LOG_LEVEL.INFO) {
        const timestamp = new Date().toISOString();
        const sessionInfo = currentSessionId ? `[Session: ${currentSessionId.substring(0, 8)}]` : '[No Session]';
        console.info(`[Chat][${timestamp}]${sessionInfo}`, ...args);
    }
}

function logWarn(...args) {
    if (CURRENT_LOG_LEVEL <= LOG_LEVEL.WARN) {
        const timestamp = new Date().toISOString();
        const sessionInfo = currentSessionId ? `[Session: ${currentSessionId.substring(0, 8)}]` : '[No Session]';
        console.warn(`[Chat][${timestamp}]${sessionInfo}`, ...args);
    }
}

function logError(...args) {
    if (CURRENT_LOG_LEVEL <= LOG_LEVEL.ERROR) {
        const timestamp = new Date().toISOString();
        const sessionInfo = currentSessionId ? `[Session: ${currentSessionId.substring(0, 8)}]` : '[No Session]';
        console.error(`[Chat][${timestamp}]${sessionInfo}`, ...args);
    }
}

/**
 * Send user message to the server using AJAX
 */
async function sendUserMessage(message) {
    try {
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            logError('No user UUID found in localStorage');
            throw new Error('No user UUID found');
        }
        
        // Prepare request data
        const requestData = {
            message: message,
            user_uuid: userUUID,
            chat_id: currentSessionId
        };
        
        logInfo(`Sending message to session ${currentSessionId}, length: ${message.length} chars, first 30 chars: "${message.substring(0, 30)}..."`);
        
        // Show loading indicator
        showLoadingIndicator();
        
        // Ensure we're scrolled to the bottom when loading
        scrollToBottom();
        
        // Send message to the server with cache busting
        const startTime = new Date().getTime();
        const response = await apiRequest(`/api/chat/sessions/${currentSessionId}/messages`, {
            method: 'POST',
            headers: {
                'X-User-UUID': userUUID,
                'X-Client-ID': clientId
            },
            body: JSON.stringify(requestData)
        });
        const endTime = new Date().getTime();
        const responseTime = endTime - startTime;
        
        logInfo(`Server response received in ${responseTime}ms, status: ${response.status}, ${response.statusText}`);
        
        if (response.status === 403) {
            // Check if server suggested a new session ID
            const data = await response.json();
            logWarn(`Received 403 response with data:`, data);
            
            if (data.new_session_id) {
                logInfo(`Server suggested new session ID: ${data.new_session_id}`);
                currentSessionId = data.new_session_id;
                
                // Try sending the message again with the new session ID
                logInfo(`Retrying message with new session ID: ${currentSessionId}`);
                return await sendUserMessage(message);
            }
            
            throw new Error('Unauthorized access to chat session');
        }
        
        if (!response.ok) {
            logError(`Error response from server: ${response.status}, ${response.statusText}`);
            throw new Error(`Server responded with ${response.status}`);
        }
        
        const data = await response.json();
        logInfo(`Message sent successfully, response size: ${JSON.stringify(data).length} bytes`);
        logDebug(`Full API response:`, data);
        
        if (data.status !== 'success') {
            logError(`API returned error status: ${data.status}`, data.message || 'No error message');
            throw new Error(data.message || 'Unknown error');
        }
        
        // Increase messages received
        messagesReceived++;
        
        // Add AI response to chat (user message was already added)
        const aiResponse = data.data.ai_response;
        // Extract the message from the response, handling different response formats
        const responseText = aiResponse.message || aiResponse.content || '';
        
        logInfo(`Processing AI response, length: ${responseText.length} chars, first 30 chars: "${responseText.substring(0, 30)}..."`);
        
        // Check if this is a mock or error message
        const isMock = responseText.startsWith('Echo:') || responseText.includes('this is just a mock response');
        const isError = responseText.startsWith('Error:');
        
        if (isMock) logInfo('Mock response detected');
        if (isError) logWarn('Error response detected');
        
        // Add message to chat with appropriate flags
        addMessageToChat(
            responseText, 
            false, 
            new Date(aiResponse.timestamp || aiResponse.created_at), 
            isError, 
            isMock
        );
        
        // Ensure we're scrolled to the bottom after response
        scrollToBottom();
        
        // Hide loading indicator
        hideLoadingIndicator();
        
        // Mark message as processed
        isPendingResponse = false;
        
        // Process next message if queue has items
        if (messageQueue.length > 0) {
            logInfo(`Message queue has ${messageQueue.length} items, processing next message`);
            processMessageQueue();
        }
        
        // Return AI response
        return responseText;
    } catch (error) {
        // Hide loading indicator
        hideLoadingIndicator();
        
        // Mark message as processed (despite error)
        isPendingResponse = false;
        
        logError(`Error sending message to server:`, error);
        
        // Show error message in chat
        const errorMessage = `Error: ${error.message}`;
        addMessageToChat(errorMessage, false, new Date(), true, false);
        
        showError('无法发送消息，请稍后再试');
        throw error;
    }
}

// Function to add a loading class to messages container
function markChatAsLoaded() {
    if (chatMessages) {
        chatMessages.classList.add('loaded');
    }
} 