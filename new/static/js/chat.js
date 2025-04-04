/**
 * Chat System for Time Capsule
 * Handles real-time messaging via WebSocket and voice input for elderly users.
 */

// WebSocket connection
let socket = null;
let currentSessionId = "single-chat-session";  // Fixed session ID
let isRecording = false;
let recordingTimer = null;
let recordingTime = 0;
let recognition = null;

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

// Initialize chat functionality when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Chat system initializing...');
    
    // Initialize components
    await initChat();
    setupEventListeners();
    initSpeechRecognition();
});

/**
 * Initialize the chat system
 */
async function initChat() {
    try {
        // Get user session data
        const sessionData = await UserSession.getSessionData();
        if (!sessionData || !sessionData.uuid) {
            console.error('No user session found, redirecting to profile page');
            window.location.href = '/profile';
            return;
        }
        
        // Connect to websocket with the fixed session ID
        connectWebSocket(currentSessionId);
        
        // Load previous messages from this session
        await loadChatMessages(currentSessionId);
        
        console.log('Chat system initialized');
    } catch (error) {
        console.error('Error initializing chat:', error);
        showError('无法初始化聊天系统，请稍后再试');
    }
}

/**
 * Set up event listeners for chat interactions
 */
function setupEventListeners() {
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
    
    // Clear chat
    clearChatBtn.addEventListener('click', clearChat);
}

/**
 * Load chat messages for the current session
 */
async function loadChatMessages(sessionId) {
    try {
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            throw new Error('No user UUID found');
        }
        
        const response = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-User-UUID': userUUID
            }
        });
        
        if (!response.ok) {
            // Session might not exist yet, which is fine
            if (response.status === 404) {
                console.log('Chat session not found. A new one will be created when sending the first message.');
                emptyChatState.style.display = 'flex';
                return;
            }
            throw new Error(`Server responded with ${response.status}`);
        }
        
        const data = await response.json();
        if (data.status !== 'success') {
            throw new Error(data.message || 'Unknown error');
        }
        
        // Add messages to the chat
        const messages = data.data;
        if (messages.length === 0) {
            emptyChatState.style.display = 'flex';
            return;
        }
        
        emptyChatState.style.display = 'none';
        messages.forEach(message => {
            addMessageToChat(message.content, message.is_user, new Date(message.created_at));
        });
        
        // Scroll to bottom
        scrollToBottom();
    } catch (error) {
        console.error('Error loading chat messages:', error);
        showError('无法加载聊天记录，请稍后再试');
    }
}

/**
 * Connect to the WebSocket for real-time chat
 */
function connectWebSocket(sessionId) {
    try {
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            throw new Error('No user UUID found');
        }
        
        // Create WebSocket connection
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${sessionId}?user_uuid=${userUUID}`;
        
        socket = new WebSocket(wsUrl);
        
        // Connection opened
        socket.addEventListener('open', (event) => {
            console.log('WebSocket connection established');
        });
        
        // Listen for messages
        socket.addEventListener('message', (event) => {
            handleWebSocketMessage(event.data);
        });
        
        // Connection closed
        socket.addEventListener('close', (event) => {
            console.log('WebSocket connection closed');
        });
        
        // Connection error
        socket.addEventListener('error', (event) => {
            console.error('WebSocket error:', event);
            showError('聊天连接出错，请刷新页面重试');
        });
    } catch (error) {
        console.error('Error connecting to WebSocket:', error);
        showError('无法连接到聊天服务器，请稍后再试');
    }
}

/**
 * Close the WebSocket connection
 */
function closeWebSocketConnection() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
        socket = null;
    }
}

/**
 * Handle incoming WebSocket messages
 */
function handleWebSocketMessage(messageData) {
    try {
        const data = JSON.parse(messageData);
        
        switch (data.status) {
            case 'connected':
                console.log('WebSocket connection confirmed:', data.message);
                break;
                
            case 'message_received':
                console.log('Message received by server:', data.message_id);
                break;
                
            case 'ai_response':
                // Add AI response to chat
                addMessageToChat(data.message, false);
                scrollToBottom();
                break;
                
            case 'error':
                console.error('WebSocket error:', data.message);
                showError(data.message);
                break;
                
            default:
                console.warn('Unknown WebSocket message type:', data.status);
        }
    } catch (error) {
        console.error('Error handling WebSocket message:', error);
    }
}

/**
 * Send a message via WebSocket
 */
function sendMessage() {
    try {
        const message = chatInput.value.trim();
        
        // Don't send empty messages
        if (!message) return;
        
        // If not connected, reconnect
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            connectWebSocket(currentSessionId);
            showError('重新连接中，请稍后再试...');
            return;
        }
        
        // Add user message to the chat
        addMessageToChat(message, true);
        
        // Send message to server
        socket.send(JSON.stringify({
            message: message
        }));
        
        // Clear input
        chatInput.value = '';
        
        // Scroll to bottom
        scrollToBottom();
        
        // Hide empty state if visible
        emptyChatState.style.display = 'none';
    } catch (error) {
        console.error('Error sending message:', error);
        showError('无法发送消息，请稍后再试');
    }
}

/**
 * Add a message to the chat display
 */
function addMessageToChat(content, isUser, timestamp = new Date()) {
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `message ${isUser ? 'message-user' : 'message-ai'}`;
    
    // Format the message text (support for simple formatting)
    const formattedContent = content.replace(/\n/g, '<br>');
    
    // Format time
    const timeFormatted = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // Set content
    messageElement.innerHTML = `
        ${formattedContent}
        <div class="message-time">${timeFormatted}</div>
    `;
    
    // Check if empty state is displayed
    if (emptyChatState.style.display !== 'none') {
        emptyChatState.style.display = 'none';
    }
    
    // Add to chat
    chatMessages.appendChild(messageElement);
    
    // Scroll to bottom
    scrollToBottom();
}

/**
 * Scroll chat to the bottom
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Clear all messages from the chat
 */
function clearChat() {
    if (confirm('确定要清空对话历史吗？此操作不可撤销。')) {
        // Remove all message elements
        const messageElements = chatMessages.querySelectorAll('.message');
        messageElements.forEach(element => element.remove());
        
        // Show empty state
        emptyChatState.style.display = 'flex';
        
        // Try to delete the chat session on the server (this will erase history)
        deleteChatSession(currentSessionId);
    }
}

/**
 * Delete a chat session
 */
async function deleteChatSession(sessionId) {
    try {
        const userUUID = localStorage.getItem('userUUID');
        if (!userUUID) {
            throw new Error('No user UUID found');
        }
        
        const response = await fetch(`/api/chat/sessions/${sessionId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-User-UUID': userUUID
            }
        });
        
        // Even if the delete fails (e.g., session doesn't exist yet), we still cleared the UI
        console.log('Chat history cleared');
        
        // Reconnect websocket to create a fresh session
        closeWebSocketConnection();
        connectWebSocket(currentSessionId);
    } catch (error) {
        console.error('Error deleting chat session:', error);
        // No need to show an error since the UI is already cleared
    }
}

/**
 * Toggle voice input
 */
function toggleVoiceInput() {
    if (!recognition) {
        showError('您的浏览器不支持语音输入功能，请使用键盘输入');
        return;
    }
    
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

/**
 * Start voice recording
 */
function startRecording() {
    try {
        recognition.start();
        isRecording = true;
        
        // Update UI
        voiceInputBtn.classList.add('recording');
        voiceInputBtn.innerHTML = '<i class="fas fa-stop"></i>';
        recordingStatus.style.display = 'block';
        
        // Start timer
        recordingTime = 0;
        recordingTimeElement.textContent = recordingTime;
        recordingTimer = setInterval(() => {
            recordingTime++;
            recordingTimeElement.textContent = recordingTime;
            
            // Auto-stop after 30 seconds to prevent memory issues
            if (recordingTime >= 30) {
                stopRecording();
            }
        }, 1000);
    } catch (error) {
        console.error('Error starting voice recording:', error);
        showError('无法启动语音输入，请稍后再试');
        stopRecording();
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
    } catch (error) {
        console.error('Error stopping recognition:', error);
    }
    
    isRecording = false;
    
    // Update UI
    voiceInputBtn.classList.remove('recording');
    voiceInputBtn.innerHTML = '<i class="fas fa-microphone"></i>';
    recordingStatus.style.display = 'none';
    
    // Stop timer
    if (recordingTimer) {
        clearInterval(recordingTimer);
        recordingTimer = null;
    }
}

/**
 * Initialize speech recognition
 */
function initSpeechRecognition() {
    // Check if browser supports speech recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn('Speech recognition not supported in this browser');
        voiceInputBtn.title = '您的浏览器不支持语音输入';
        voiceInputBtn.disabled = true;
        return;
    }
    
    // Create recognition instance
    recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;
    
    // Handle results
    recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }
        
        // Update input field
        if (finalTranscript) {
            chatInput.value = finalTranscript;
        } else if (interimTranscript) {
            chatInput.value = interimTranscript;
        }
    };
    
    // Handle errors
    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        stopRecording();
        
        if (event.error === 'not-allowed') {
            showError('请允许麦克风访问权限以使用语音输入功能');
        } else {
            showError('语音识别出错，请稍后再试');
        }
    };
    
    // Handle end of recognition
    recognition.onend = () => {
        stopRecording();
    };
}

/**
 * Show error message
 */
function showError(message) {
    // You can implement a toast or alert system here
    alert(message);
} 