/**
 * Memory Agent Web Client
 */

// State
let ws = null;
let isConnected = false;
let isSending = false;
let attachedFile = null;

// DOM Elements
const chatContainer = document.getElementById('chatContainer');
const welcomeMessage = document.getElementById('welcomeMessage');
const inputTextarea = document.getElementById('inputTextarea');
const sendBtn = document.getElementById('sendBtn');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileName = document.getElementById('fileName');
const fileRemove = document.getElementById('fileRemove');
const skillsBtn = document.getElementById('skillsBtn');
const skillsDropdown = document.getElementById('skillsDropdown');
const skillsList = document.getElementById('skillsList');

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    // Connect WebSocket
    connectWebSocket();

    // Load existing messages
    await loadMessages();

    // Load skills
    await loadSkills();

    // Setup event listeners
    setupEventListeners();
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/chat`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        isConnected = true;
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        isConnected = false;
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
        handleWebSocketMessage(JSON.parse(event.data));
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'user':
            addMessage('user', data.content);
            break;
        case 'assistant':
            addMessage('assistant', data.content);
            hideTypingIndicator();
            break;
        case 'tool':
            addMessage('tool', data.content);
            break;
        case 'status':
            showTypingIndicator();
            break;
        case 'error':
            addMessage('error', data.content);
            hideTypingIndicator();
            break;
    }
}

async function loadMessages() {
    try {
        const res = await fetch('/api/messages');
        const data = await res.json();

        if (data.messages && data.messages.length > 0) {
            welcomeMessage.style.display = 'none';
            data.messages.forEach(msg => {
                if (msg.role !== 'system') {
                    addMessage(msg.role, msg.content, msg.timestamp, false);
                }
            });
        }
    } catch (error) {
        console.error('Failed to load messages:', error);
    }
}

async function loadSkills() {
    try {
        const res = await fetch('/api/skills');
        const data = await res.json();

        skillsList.innerHTML = '';
        data.skills.forEach(skill => {
            const item = document.createElement('div');
            item.className = 'skill-item';
            item.innerHTML = `
                <span class="skill-name">${skill}</span>
            `;
            item.onclick = () => selectSkill(skill);
            skillsList.appendChild(item);
        });
    } catch (error) {
        console.error('Failed to load skills:', error);
    }
}

function selectSkill(skill) {
    inputTextarea.value = `/${skill} `;
    inputTextarea.focus();
    toggleSkillsDropdown();
}

function setupEventListeners() {
    // Textarea auto-resize
    inputTextarea.addEventListener('input', () => {
        autoResizeTextarea();
        updateSendButton();
    });

    // Send on Enter (Shift+Enter for newline)
    inputTextarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send button
    sendBtn.addEventListener('click', sendMessage);

    // File attach
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);
    fileRemove.addEventListener('click', removeAttachedFile);

    // Skills dropdown
    skillsBtn.addEventListener('click', toggleSkillsDropdown);

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!skillsDropdown.contains(e.target) && e.target !== skillsBtn) {
            skillsDropdown.classList.remove('active');
        }
    });
}

function autoResizeTextarea() {
    inputTextarea.style.height = 'auto';
    inputTextarea.style.height = Math.min(inputTextarea.scrollHeight, 200) + 'px';
}

function updateSendButton() {
    const hasText = inputTextarea.value.trim().length > 0;
    const hasFile = attachedFile !== null;
    sendBtn.disabled = !hasText && !hasFile;
}

function toggleSkillsDropdown() {
    skillsDropdown.classList.toggle('active');
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        attachedFile = file;
        fileName.textContent = file.name;
        filePreview.style.display = 'flex';
        updateSendButton();
    }
}

function removeAttachedFile() {
    attachedFile = null;
    filePreview.style.display = 'none';
    fileInput.value = '';
    updateSendButton();
}

async function sendMessage() {
    if (isSending) return;

    const text = inputTextarea.value.trim();
    if (!text && !attachedFile) return;

    // Intercept clear command - clear frontend DOM + backend memory
    if (text === 'clear' || text === '/clear') {
        inputTextarea.value = '';
        autoResizeTextarea();
        await clearMessages();
        return;
    }

    isSending = true;
    sendBtn.disabled = true;

    // Hide welcome message
    welcomeMessage.style.display = 'none';

    // Clear input
    inputTextarea.value = '';
    autoResizeTextarea();

    // Send via WebSocket
    if (isConnected) {
        ws.send(JSON.stringify({
            message: text,
            file: attachedFile ? attachedFile.name : null
        }));
    }

    // Remove attached file after sending
    if (attachedFile) {
        removeAttachedFile();
    }

    isSending = false;
}

async function clearMessages() {
    // Remove all message elements from the DOM
    const messages = chatContainer.querySelectorAll('.message');
    messages.forEach(m => m.remove());

    // Show welcome message again
    welcomeMessage.style.display = '';

    // Call backend to clear server-side memory
    try {
        await fetch('/api/clear', { method: 'POST' });
    } catch (error) {
        console.error('Failed to clear memory:', error);
    }
}

function addMessage(role, content, timestamp = null, scroll = true) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = `avatar ${role}`;
    avatar.textContent = role === 'user' ? 'U' : role === 'assistant' ? 'A' : 'T';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    if (role === 'error') {
        bubble.classList.add('error-bubble');
    }

    // Format content
    bubble.innerHTML = formatContent(content);

    messageEl.appendChild(avatar);
    messageEl.appendChild(bubble);

    chatContainer.appendChild(messageEl);

    if (scroll) {
        scrollToBottom();
    }

    return messageEl;
}

function formatContent(content) {
    // Escape HTML
    let formatted = content
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Format code blocks
    formatted = formatted.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Format inline code
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Format bold
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Format newlines
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

function showTypingIndicator() {
    // Remove existing typing indicator
    hideTypingIndicator();

    const typingEl = document.createElement('div');
    typingEl.className = 'message assistant';
    typingEl.id = 'typingIndicator';

    const avatar = document.createElement('div');
    avatar.className = 'avatar assistant';
    avatar.textContent = 'A';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;

    typingEl.appendChild(avatar);
    typingEl.appendChild(bubble);
    chatContainer.appendChild(typingEl);

    scrollToBottom();
}

function hideTypingIndicator() {
    const existing = document.getElementById('typingIndicator');
    if (existing) {
        existing.remove();
    }
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
