// Global variables
let clearButton = document.getElementById('clearButton');
let questionsArea = document.getElementById('questionsArea');
let answersArea = document.getElementById('answersArea');
let apiKeyInput = document.getElementById('apiKeyInput');
let saveApiKeyButton = document.getElementById('saveApiKey');
let deleteApiKeyButton = document.getElementById('deleteApiKey');
let startInterviewButton = document.getElementById('startInterviewButton');
let stopInterviewButton = document.getElementById('stopInterviewButton');
let completeAnswerButton = document.getElementById('completeAnswerButton');
let cameraPreview = document.getElementById('cameraPreview');
let countdownOverlay = document.getElementById('countdownOverlay');
let overlayCount = document.getElementById('overlayCount');
let modal = document.getElementById('modal');
let modalMessage = document.getElementById('modal-message');
let toastContainer = document.getElementById('toastContainer');
let ttsToggle = document.getElementById('ttsToggle');
let questionCounter = document.getElementById('questionCounter');
let countdown = document.getElementById('countdown');
let aiAvatar = document.getElementById('aiAvatar');
let connectionStatus = document.getElementById('connectionStatus');
let statusText = document.getElementById('statusText');

let proctoringNotes = [];
let activeAudios = [];
let ttsEnabled = true;
let countdownTimerId = null;
let countdownEndTs = null;
let countdownTotal = 90;

// Deduplication state
let lastQuestionText = '';
let lastQuestionIndex = '';
let lastAnswerText = '';
let lastAudioBase64 = '';

// Initialize page
window.addEventListener('load', async () => {
    updateConnectionStatus(false);
    initializeCamera();
    try {
        const hasKey = await eel.has_api_key()();
        updateApiKeyUI(!!hasKey);
    } catch (e) {
        updateApiKeyUI(false);
    }
});

// Camera initialization
async function initializeCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'user' }, 
            audio: false 
        });
        cameraPreview.srcObject = stream;
        updateConnectionStatus(true);
    } catch (error) {
        console.error('Camera access denied:', error);
        showToast('Camera access required for interview', 'error');
    }
}

// Connection status
function updateConnectionStatus(connected) {
    if (connected) {
        connectionStatus.classList.remove('inactive');
        statusText.textContent = 'Connected';
    } else {
        connectionStatus.classList.add('inactive');
        statusText.textContent = 'Disconnected';
    }
}

// API Key Management
function updateApiKeyUI(hasApiKey) {
    apiKeyInput.style.display = hasApiKey ? 'none' : 'block';
    saveApiKeyButton.style.display = hasApiKey ? 'none' : 'inline-flex';
    deleteApiKeyButton.style.display = hasApiKey ? 'inline-flex' : 'none';
    startInterviewButton.disabled = !hasApiKey;
    
    if (hasApiKey) {
        showToast('API key configured successfully', 'success');
    }
}

// Event Listeners
saveApiKeyButton.addEventListener('click', async () => {
    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
        showToast('Please enter an API key', 'error');
        return;
    }
    if (!apiKey.startsWith('gsk_')) {
        showToast('Invalid API key format. Must start with gsk_', 'error');
        return;
    }
    try {
        const ok = await eel.save_api_key(apiKey)();
        if (ok) {
            updateApiKeyUI(true);
            apiKeyInput.value = '';
        } else {
            showToast('Failed to save API key', 'error');
        }
    } catch (e) {
        showToast('Failed to save API key', 'error');
    }
});

deleteApiKeyButton.addEventListener('click', async () => {
    try {
        const ok = await eel.delete_api_key()();
        if (ok) {
            updateApiKeyUI(false);
            showToast('API key removed', 'info');
        }
    } catch (e) {
        showToast('Failed to delete API key', 'error');
    }
});

startInterviewButton.addEventListener('click', async () => {
    showCountdownOverlay();
    setTimeout(async () => {
        hideCountdownOverlay();
        try {
            // Rely on backend to push UI updates via update_ui; avoid handling payload here to prevent duplicates
            await eel.start_interview()();
            startInterviewButton.disabled = true;
            stopInterviewButton.disabled = false;
            completeAnswerButton.disabled = false;
            showToast('Interview started', 'success');
        } catch (e) {
            showToast('Failed to start interview', 'error');
        }
    }, 3000);
});

stopInterviewButton.addEventListener('click', async () => {
    try {
        // Avoid immediate payload handling; backend will notify via update_ui if needed
        await eel.stop_interview()();
    } catch (e) {}
    stopInterview();
});

completeAnswerButton.addEventListener('click', async () => {
    hideCountdown();
    try {
        // Avoid immediate payload handling; backend will notify via update_ui if needed
        await eel.complete_answer()();
    } catch (e) {
        showToast('Failed to submit answer', 'error');
    }
});

clearButton.addEventListener('click', () => {
    clearAllContent();
});

ttsToggle.addEventListener('click', async () => {
    try {
        const enabled = await eel.toggle_tts()();
        ttsEnabled = !!enabled;
        ttsToggle.innerHTML = ttsEnabled ? 
            '<i class="fas fa-volume-up"></i> TTS On' : 
            '<i class="fas fa-volume-mute"></i> TTS Off';
        showToast(`TTS ${ttsEnabled ? 'enabled' : 'disabled'}`, 'info');
    } catch (e) {}
});

// Modal controls
document.querySelector('.modal-close').addEventListener('click', () => {
    modal.style.display = 'none';
});

window.addEventListener('click', (event) => {
    if (event.target === modal) {
        modal.style.display = 'none';
    }
});

// Utility functions
function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? 'check-circle' : 
                type === 'error' ? 'exclamation-triangle' : 
                'info-circle';
    
    toast.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" style="margin-left: auto; background: none; border: none; font-size: 1.2rem; cursor: pointer;">&times;</button>
    `;
    
    toastContainer.appendChild(toast);
    
    if (duration > 0) {
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, duration);
    }
}

function showModal(message) {
    modalMessage.textContent = message;
    modal.style.display = 'block';
}

function showCountdownOverlay() {
    countdownOverlay.style.display = 'flex';
    let count = 3;
    overlayCount.textContent = count;
    
    const interval = setInterval(() => {
        count--;
        if (count > 0) {
            overlayCount.textContent = count;
        } else {
            overlayCount.textContent = 'GO!';
            setTimeout(() => {
                clearInterval(interval);
            }, 500);
        }
    }, 1000);
}

function hideCountdownOverlay() {
    countdownOverlay.style.display = 'none';
}

function startCountdown(seconds = 90) {
    countdown.style.display = 'flex';
    countdownTotal = seconds;
    countdownEndTs = Date.now() + seconds * 1000;
    
    const updateCountdown = () => {
        const remaining = Math.max(0, countdownEndTs - Date.now());
        const remainingSeconds = Math.ceil(remaining / 1000);
        
        if (remainingSeconds <= 0) {
            countdown.querySelector('span').textContent = 'Time up!';
            countdown.classList.add('warning');
            clearInterval(countdownTimerId);
            return;
        }
        
        const minutes = Math.floor(remainingSeconds / 60);
        const seconds = remainingSeconds % 60;
        const timeString = minutes > 0 ? 
            `${minutes}:${seconds.toString().padStart(2, '0')} remaining` : 
            `${seconds}s remaining`;
        
        countdown.querySelector('span').textContent = timeString;
        
        if (remainingSeconds <= 10) {
            countdown.classList.add('warning');
        } else {
            countdown.classList.remove('warning');
        }
    };
    
    updateCountdown();
    countdownTimerId = setInterval(updateCountdown, 1000);
}

function hideCountdown() {
    countdown.style.display = 'none';
    countdown.classList.remove('warning');
    if (countdownTimerId) {
        clearInterval(countdownTimerId);
        countdownTimerId = null;
    }
}

function clearAllContent() {
    questionsArea.innerHTML = `
        <div style="text-align: center; color: var(--text-secondary); margin-top: 2rem;">
            <i class="fas fa-comments" style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.3;"></i>
            <p>Questions will appear here when you start the interview</p>
        </div>
    `;
    answersArea.innerHTML = `
        <div style="text-align: center; color: var(--text-secondary); margin-top: 2rem;">
            <i class="fas fa-robot" style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.3;"></i>
            <p>AI responses and feedback will appear here</p>
        </div>
    `;
    questionCounter.textContent = '0/0';
    // Reset dedupe state
    lastQuestionText = '';
    lastQuestionIndex = '';
    lastAnswerText = '';
    lastAudioBase64 = '';
    showToast('Content cleared', 'info');
}

function stopInterview() {
    startInterviewButton.disabled = false;
    stopInterviewButton.disabled = true;
    completeAnswerButton.disabled = true;
    hideCountdown();
    
    // Stop camera
    if (cameraPreview.srcObject) {
        cameraPreview.srcObject.getTracks().forEach(track => track.stop());
        cameraPreview.srcObject = null;
        setTimeout(initializeCamera, 1000); // Restart camera
    }
    
    // Stop any playing audio
    activeAudios.forEach(a => { try { a.pause(); a.currentTime = 0; } catch(_){} });
    activeAudios = [];

    showToast('Interview stopped', 'info');
}

// Backend -> Frontend bridge
eel.expose(update_ui);
function update_ui(questionText, payload) {
    try {
        if (questionText && questionText.trim()) {
            // Extract counter like [1/5]
            const match = questionText.match(/^\[(\d+)\/(\d+)\]\s*(.*)$/);
            if (match) {
                const idx = parseInt(match[1], 10);
                const total = parseInt(match[2], 10);
                const qText = match[3];
                const idxKey = `${idx}/${total}`;
                // Deduplicate same question index + text
                if (idxKey !== lastQuestionIndex || qText !== lastQuestionText) {
                    questionCounter.textContent = `${idx}/${total}`;
                    addQuestion(idx, qText);
                    startCountdown(90);
                    lastQuestionIndex = idxKey;
                    lastQuestionText = qText;
                }
            } else {
                if (questionText !== lastQuestionText) {
                    addQuestion('', questionText);
                    lastQuestionText = questionText;
                }
            }
        }
        if (payload && String(payload).trim()) {
            handleBackendPayload(payload);
        }
    } catch (e) {}
}

function handleBackendPayload(payload) {
    try {
        let data = payload;
        if (typeof payload === 'string') {
            try { data = JSON.parse(payload); } catch (_) { data = { text: String(payload), audio: null }; }
        }
        const text = data && data.text ? data.text : '';
        const audio = data && data.audio ? data.audio : null;
        if (text && text !== lastAnswerText) {
            addAnswer(text);
            lastAnswerText = text;
        }
        if (ttsEnabled && audio && audio !== lastAudioBase64) {
            playTtsAudio(audio);
            lastAudioBase64 = audio;
        }
    } catch (e) {}
}

function playTtsAudio(base64Audio) {
    try {
        const src = `data:audio/mp3;base64,${base64Audio}`;
        const audio = new Audio(src);
        audio.addEventListener('play', () => { try { eel.audio_playback_started()(); } catch (_) {} });
        audio.addEventListener('ended', () => { try { eel.audio_playback_ended()(); } catch (_) {} });
        audio.addEventListener('error', () => { try { eel.audio_playback_ended()(); } catch (_) {} });
        // Stop any currently playing audio
        activeAudios.forEach(a => { try { a.pause(); a.currentTime = 0; } catch(_){} });
        activeAudios = [audio];
        audio.play().catch(() => {
            showToast('Autoplay blocked. Click to play audio.', 'warn');
        });
    } catch (e) {}
}

function addQuestion(number, text) {
    if (questionsArea.querySelector('.fa-comments')) {
        questionsArea.innerHTML = '';
    }
    
    const questionDiv = document.createElement('div');
    questionDiv.className = 'question-item';
    questionDiv.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 1rem;">
            <span class="question-number">${number}</span>
            <div>
                <p style="margin: 0; font-weight: 500;">${text}</p>
            </div>
        </div>
    `;
    questionsArea.appendChild(questionDiv);
    questionsArea.scrollTop = questionsArea.scrollHeight;
}

function addAnswer(text) {
    if (answersArea.querySelector('.fa-robot')) {
        answersArea.innerHTML = '';
    }
    
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-item';
    answerDiv.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 1rem;">
            <div class="ai-avatar" style="flex-shrink: 0;">AI</div>
            <div style="flex: 1;">
                <p style="margin: 0; line-height: 1.6;">${text}</p>
                <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                    <button class="btn btn-secondary" style="padding: 0.5rem 1rem; font-size: 0.75rem;" onclick="replayLastAudio(this)">
                        <i class="fas fa-play"></i> Play Audio
                    </button>
                    <button class="btn btn-secondary" style="padding: 0.5rem 1rem; font-size: 0.75rem;" onclick="this.parentElement.parentElement.parentElement.parentElement.remove()">
                        <i class="fas fa-times"></i> Dismiss
                    </button>
                </div>
            </div>
        </div>
    `;
    answersArea.appendChild(answerDiv);
    answersArea.scrollTop = answersArea.scrollHeight;
}

function replayLastAudio(btn) {
    if (!ttsEnabled) { showToast('TTS is disabled', 'info'); return; }
    const last = activeAudios[activeAudios.length - 1];
    if (last) { try { last.currentTime = 0; last.play(); } catch(_){} }
}
