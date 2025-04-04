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
        
        logInfo(`Initializing chat for user ${sessionData.uuid.substring(0, 8)}...`);
        
        // Store user UUID in localStorage to ensure it's available for API calls
        localStorage.setItem('userUUID', sessionData.uuid);
        
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
    
    // Use the UUID directly without any prefix to match database expectations
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
 * Load chat messages for the current session
 */
async function loadChatMessages(sessionId) {
    try {
        logInfo(`Loading chat messages for session ${sessionId}`);
        
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            throw new Error('No user UUID found');
        }
        
        // Always include the user UUID in headers
        const headers = {
            'Content-Type': 'application/json',
            'X-User-UUID': userUUID
        };
        
        logInfo(`Fetching messages with UUID: ${userUUID.substring(0, 8)}...`);
        
        const response = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
            method: 'GET',
            headers: headers
        });
        
        // Handle different response statuses
        if (response.status === 403) {
            // Session exists but belongs to another user
            logInfo('Session belongs to another user. Will create a new session on first message.');
            
            // Check if server suggested a new session ID
            const data = await response.json();
            if (data.new_session_id) {
                logInfo(`Server suggested new session ID: ${data.new_session_id}`);
                currentSessionId = data.new_session_id;
                
                // Try loading messages with the new session ID
                return await loadChatMessages(currentSessionId);
            }
            
            // Hide empty state and show welcome message instead
            emptyChatState.style.display = 'none';
            
            // Add a welcome message from the AI to explain what happened
            const welcomeMessage = `欢迎来到新的聊天会话！之前的会话属于另一个设备或用户，我们已为您创建一个新的聊天会话。请开始输入您的消息，与20岁的自己对话吧！`;
            addMessageToChat(welcomeMessage, false);
            
            return true; // We added welcome message
        } else if (response.status === 404) {
            // This shouldn't happen anymore with our server changes, but just in case
            logInfo('Chat session not found. A new one will be created when sending the first message.');
            emptyChatState.style.display = 'flex';
            return false; // No messages loaded
        } else if (!response.ok) {
            // Any other error status
            throw new Error(`Server responded with ${response.status}`);
        }
        
        const data = await response.json();
        if (data.status !== 'success') {
            throw new Error(data.message || 'Unknown error');
        }
        
        // Add messages to the chat
        const messages = data.data;
        logInfo(`Loaded ${messages.length} messages from history`);
        
        if (messages.length === 0) {
            emptyChatState.style.display = 'flex';
            return false; // No messages loaded
        }
        
        emptyChatState.style.display = 'none';
        messages.forEach(message => {
            addMessageToChat(message.content, message.is_user, new Date(message.created_at));
        });
        
        // Scroll to bottom
        scrollToBottom();
        logInfo('Chat history loaded successfully');
        return true; // Messages were loaded
    } catch (error) {
        logError('Error loading chat messages:', error);
        showError('无法加载聊天记录，请稍后再试');
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
 */
function addMessageToChat(message, isUserMessage, timestamp = new Date()) {
    // Create message element
    const messageContainer = document.createElement('div');
    messageContainer.className = isUserMessage ? 'message user-message' : 'message ai-message';
    
    // Format timestamp
    const formattedTime = formatTime(timestamp);
    
    // Add content with timestamp
    messageContainer.innerHTML = `
        <div class="message-content">${formatMessage(message)}</div>
        <div class="message-time">${formattedTime}</div>
    `;
    
    // Add to chat
    chatMessages.appendChild(messageContainer);
    
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
 * Scroll chat to bottom
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
        const response = await fetch(`/api/chat/sessions/${currentSessionId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
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
        console.debug('[Chat]', ...args);
    }
}

function logInfo(...args) {
    if (CURRENT_LOG_LEVEL <= LOG_LEVEL.INFO) {
        console.info('[Chat]', ...args);
    }
}

function logWarn(...args) {
    if (CURRENT_LOG_LEVEL <= LOG_LEVEL.WARN) {
        console.warn('[Chat]', ...args);
    }
}

function logError(...args) {
    if (CURRENT_LOG_LEVEL <= LOG_LEVEL.ERROR) {
        console.error('[Chat]', ...args);
    }
}

/**
 * Send user message to the server using AJAX
 */
async function sendUserMessage(message) {
    try {
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            throw new Error('No user UUID found');
        }
        
        // Prepare request data
        const requestData = {
            message: message
        };
        
        // Show loading indicator
        showLoadingIndicator();
        
        // Send message to the server
        const response = await fetch(`/api/chat/sessions/${currentSessionId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-UUID': userUUID,
                'X-Client-ID': clientId
            },
            body: JSON.stringify(requestData)
        });
        
        if (response.status === 403) {
            // Check if server suggested a new session ID
            const data = await response.json();
            if (data.new_session_id) {
                logInfo(`Server suggested new session ID: ${data.new_session_id}`);
                currentSessionId = data.new_session_id;
                
                // Try sending the message again with the new session ID
                return await sendUserMessage(message);
            }
            
            throw new Error('Unauthorized access to chat session');
        }
        
        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }
        
        const data = await response.json();
        if (data.status !== 'success') {
            throw new Error(data.message || 'Unknown error');
        }
        
        // Increase messages received
        messagesReceived++;
        
        // Add AI response to chat (user message was already added)
        const aiResponse = data.data.ai_response;
        addMessageToChat(aiResponse.content, false);
        
        // Hide loading indicator
        hideLoadingIndicator();
        
        // Mark message as processed
        isPendingResponse = false;
        
        // Process next message if queue has items
        if (messageQueue.length > 0) {
            processMessageQueue();
        }
        
        // Return AI response
        return aiResponse.content;
    } catch (error) {
        // Hide loading indicator
        hideLoadingIndicator();
        
        // Mark message as processed (despite error)
        isPendingResponse = false;
        
        logError('Error sending message to server:', error);
        showError('无法发送消息，请稍后再试');
        throw error;
    }
} 