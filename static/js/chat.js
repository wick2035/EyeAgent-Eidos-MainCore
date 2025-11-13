// 全局变量
let sessionId = null;
let currentStage = 'greeting';
let isProcessing = false;

// DOM元素
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const exportBtn = document.getElementById('exportBtn');
const resetBtn = document.getElementById('resetBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const sessionIdDisplay = document.getElementById('sessionId');
const currentStageDisplay = document.getElementById('currentStage');
const jsonModal = document.getElementById('jsonModal');
const jsonContent = document.getElementById('jsonContent');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 设置欢迎消息时间
    document.getElementById('welcomeTime').textContent = getCurrentTime();
    
    // 绑定事件
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    exportBtn.addEventListener('click', exportPatientData);
    resetBtn.addEventListener('click', resetSession);
    
    // 自动调整textarea高度
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = userInput.scrollHeight + 'px';
    });
    
    // 生成会话ID显示
    generateSessionId();
});

// 生成或获取会话ID
function generateSessionId() {
    if (!sessionId) {
        sessionId = generateUUID();
        sessionIdDisplay.textContent = sessionId.substring(0, 8) + '...';
    }
}

// 生成UUID
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// 获取当前时间
function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

// 发送消息
async function sendMessage() {
    const message = userInput.value.trim();
    
    if (!message || isProcessing) {
        return;
    }
    
    // 添加用户消息到界面
    addMessage(message, 'user');
    
    // 清空输入框
    userInput.value = '';
    userInput.style.height = 'auto';
    
    // 设置处理状态
    isProcessing = true;
    sendBtn.disabled = true;
    showLoading();
    
    try {
        // 发送请求到后端
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        if (!response.ok) {
            throw new Error('网络请求失败');
        }
        
        const data = await response.json();
        
        // 更新会话ID
        if (data.session_id && !sessionId) {
            sessionId = data.session_id;
            sessionIdDisplay.textContent = sessionId.substring(0, 8) + '...';
        }
        
        // 更新当前阶段
        currentStage = data.stage;
        updateStageDisplay(data.stage);
        
        // 添加AI响应到界面
        addMessage(data.response, 'assistant');
        
        // 如果对话完成，显示提示
        if (data.is_completed) {
            setTimeout(() => {
                addSystemMessage('✅ 问诊已完成！您可以点击"导出病例"按钮查看完整的患者信息。');
            }, 500);
        }
        
    } catch (error) {
        console.error('Error:', error);
        addSystemMessage('❌ 抱歉，发送消息时出现错误，请重试。');
    } finally {
        isProcessing = false;
        sendBtn.disabled = false;
        hideLoading();
        userInput.focus();
    }
}

// 添加消息到聊天界面
function addMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.textContent = type === 'user' ? '👤' : '🤖';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = text;
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();
    
    contentDiv.appendChild(textDiv);
    contentDiv.appendChild(timeDiv);
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    
    chatMessages.appendChild(messageDiv);
    
    // 滚动到底部
    scrollToBottom();
}

// 添加系统消息
function addSystemMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.textContent = '💡';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.style.background = '#e8f5e9';
    textDiv.style.borderColor = '#4caf50';
    textDiv.textContent = text;
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();
    
    contentDiv.appendChild(textDiv);
    contentDiv.appendChild(timeDiv);
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
}

// 滚动到底部
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 显示加载动画
function showLoading() {
    loadingIndicator.style.display = 'flex';
}

// 隐藏加载动画
function hideLoading() {
    loadingIndicator.style.display = 'none';
}

// 更新阶段显示
function updateStageDisplay(stage) {
    const stageNames = {
        'greeting': '初次问候',
        'health_consultation': '健康咨询',
        'symptom_assessment': '症状评估',
        'appointment_inquiry': '询问预约',
        'patient_info_collection': '收集患者信息',
        'ophthalmology_triage': '眼科分诊',
        'medical_history': '病史采集',
        'appointment_booking': '预约确认',
        'completed': '✅ 已完成'
    };
    
    currentStageDisplay.textContent = stageNames[stage] || stage;
}

// 导出患者数据
async function exportPatientData() {
    if (!sessionId) {
        alert('暂无会话数据可导出');
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`/api/export/${sessionId}`);
        
        if (!response.ok) {
            throw new Error('导出失败');
        }
        
        const data = await response.json();
        
        // 显示JSON模态框
        jsonContent.textContent = JSON.stringify(data, null, 2);
        jsonModal.style.display = 'flex';
        
    } catch (error) {
        console.error('Error:', error);
        alert('导出数据时出错，请重试');
    } finally {
        hideLoading();
    }
}

// 关闭JSON模态框
function closeJsonModal() {
    jsonModal.style.display = 'none';
}

// 下载JSON文件
function downloadJson() {
    const jsonText = jsonContent.textContent;
    const blob = new Blob([jsonText], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `patient_record_${new Date().getTime()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 重置会话
async function resetSession() {
    if (!confirm('确定要重新开始吗？当前对话记录将被清除。')) {
        return;
    }
    
    showLoading();
    
    try {
        if (sessionId) {
            await fetch(`/api/reset/${sessionId}`, { method: 'POST' });
        }
        
        // 清空界面
        chatMessages.innerHTML = `
            <div class="message assistant-message">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <div class="message-text">
                        您好！我是智能医疗咨询助手。我可以为您提供眼科健康咨询、症状评估和医生预约服务。请告诉我您有什么不舒服的地方？
                    </div>
                    <div class="message-time">${getCurrentTime()}</div>
                </div>
            </div>
        `;
        
        // 重置状态
        sessionId = null;
        currentStage = 'greeting';
        generateSessionId();
        updateStageDisplay('greeting');
        
    } catch (error) {
        console.error('Error:', error);
        alert('重置会话时出错，请刷新页面重试');
    } finally {
        hideLoading();
    }
}

// 点击模态框外部关闭
jsonModal.addEventListener('click', (e) => {
    if (e.target === jsonModal) {
        closeJsonModal();
    }
});

