// 全局变量
let sessionId = null;
let currentStage = 'greeting';
let currentAgent = null; // 当前使用的agent
let isProcessing = false;
let selectedUserId = null; // 选中的用户ID
let selectedUserPhone = null; // 选中的用户手机号
let currentRole = 'patient'; // 当前身份：patient 或 doctor

// DOM元素
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const exportBtn = document.getElementById('exportBtn');
const resetBtn = document.getElementById('resetBtn');
const historyBtn = document.getElementById('historyBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const sessionIdDisplay = document.getElementById('sessionId');
const currentStageDisplay = document.getElementById('currentStage');
const currentAgentDisplay = document.getElementById('currentAgent');
const currentRoleDisplay = document.getElementById('currentRole');
const jsonModal = document.getElementById('jsonModal');
const jsonContent = document.getElementById('jsonContent');
const userSelect = document.getElementById('userSelect');
const roleSelect = document.getElementById('roleSelect');
const userSelectLabel = document.getElementById('userSelectLabel');
const historySidebar = document.getElementById('historySidebar');
const historyList = document.getElementById('historyList');

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
    historyBtn.addEventListener('click', toggleHistorySidebar);
    
    // 身份选择事件 - 切换身份时自动重置会话并更新UI
    roleSelect.addEventListener('change', async (e) => {
        const newRole = e.target.value;
        if (newRole !== currentRole) {
            currentRole = newRole;
            updateRoleUI();
            
            // 自动重置会话
            if (sessionId || chatMessages.children.length > 1) {
                await resetSessionWithoutConfirm();
                const roleText = currentRole === 'doctor' ? '医生' : '患者';
                addSystemMessage(`🎭 已切换到${roleText}身份，系统已重置会话`);
            }
        }
    });
    
    // 用户选择事件 - 切换用户时自动重置会话
    userSelect.addEventListener('change', async (e) => {
        const selectedOption = e.target.selectedOptions[0];
        const newUserId = e.target.value ? parseInt(e.target.value) : null;
        const newUserPhone = selectedOption ? selectedOption.getAttribute('data-phone') : null;
        
        // 如果用户选择发生变化，重置会话
        if (newUserId !== selectedUserId || newUserPhone !== selectedUserPhone) {
            selectedUserId = newUserId;
            selectedUserPhone = newUserPhone;
            console.log('选择的用户ID:', selectedUserId, '手机号:', selectedUserPhone);
            
            // 自动重置会话以加载新用户的历史信息
            if (sessionId || chatMessages.children.length > 1) {
                await resetSessionWithoutConfirm();
                
                // 如果选择了老用户，显示提示信息
                if (selectedUserId) {
                    const userName = selectedOption.textContent.split('(')[0].trim();
                    addSystemMessage(`💡 已切换到用户：${userName}，系统将自动加载该用户的历史信息`);
                }
            }
        }
    });
    
    // 自动调整textarea高度
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = userInput.scrollHeight + 'px';
    });
    
    // 生成会话ID显示
    generateSessionId();
    
    // 加载用户列表
    loadUserList();
    
    // 初始化身份UI
    updateRoleUI();
});

// 更新身份UI
function updateRoleUI() {
    const roleText = currentRole === 'doctor' ? '医生' : '患者';
    currentRoleDisplay.textContent = roleText;
    
    if (currentRole === 'patient') {
        // 患者身份：只能选择自己，隐藏用户选择器或设为只读
        userSelectLabel.textContent = '👤 我的身份：';
        userSelect.style.display = 'inline-block';
        addSystemMessage('💡 患者模式：您只能查看和操作自己的信息。系统会自动调用相应功能，但不能生成新报告。');
    } else {
        // 医生身份：可以选择任何患者
        userSelectLabel.textContent = '👤 选择患者：';
        userSelect.style.display = 'inline-block';
        addSystemMessage('💡 医生模式：您可以选择任何患者，系统会根据您的对话自动选择合适的功能（咨询/报告）。');
    }
}

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

// 加载用户列表
async function loadUserList() {
    try {
        const response = await fetch('/api/users');
        if (!response.ok) {
            console.error('加载用户列表失败');
            return;
        }
        
        const data = await response.json();
        if (data.success && data.users && data.users.length > 0) {
            // 清空现有选项（除了默认的"新用户"选项）
            userSelect.innerHTML = '<option value="">新用户（无历史记录）</option>';
            
            // 添加用户选项
            data.users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.Patient_ID;
                option.setAttribute('data-phone', user.Phone_Number || '');
                const gender = user.Gender || '未知';
                const age = user.Age || '未知';
                option.textContent = `${user.Name} (ID:${user.Patient_ID}, ${gender}, ${age}岁, ${user.Phone_Number || '无电话'})`;
                userSelect.appendChild(option);
            });
            
            console.log(`已加载 ${data.users.length} 个用户`);
        }
    } catch (error) {
        console.error('加载用户列表时出错:', error);
    }
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
        const requestBody = {
            message: message,
            session_id: sessionId,
            role: currentRole  // 添加身份参数
        };
        
        // 如果选择了用户，添加 user_id 和 phone_number
        if (selectedUserId) {
            requestBody.user_id = selectedUserId;
        }
        if (selectedUserPhone) {
            requestBody.phone_number = selectedUserPhone;
        }
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
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
        
        // 更新当前Agent
        if (data.agent_type) {
            currentAgent = data.agent_type;
            updateAgentDisplay(data.agent_type);
        }
        
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
        'select_action': '选择操作',
        'generate_report': '生成报告',
        'analyze_history': '分析历史',
        'answer_question': '回答问题',
        'compare_records': '对比记录',
        'completed': '✅ 已完成'
    };
    
    currentStageDisplay.textContent = stageNames[stage] || stage;
}

// 更新Agent显示
function updateAgentDisplay(agentType) {
    const agentNames = {
        'health': '健康咨询Agent',
        'report': '报告分析Agent'
    };
    
    currentAgentDisplay.textContent = agentNames[agentType] || agentType;
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

// 重置会话（不需要确认，供内部调用）
async function resetSessionWithoutConfirm() {
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

// 重置会话（需要用户确认）
async function resetSession() {
    if (!confirm('确定要重新开始吗？当前对话记录将被清除。')) {
        return;
    }
    
    await resetSessionWithoutConfirm();
}

// 点击模态框外部关闭
jsonModal.addEventListener('click', (e) => {
    if (e.target === jsonModal) {
        closeJsonModal();
    }
});

// ========== 历史记录功能 ==========

// 切换历史记录侧边栏
function toggleHistorySidebar() {
    const isActive = historySidebar.classList.toggle('active');

    // 如果打开侧边栏且有选中用户,自动加载历史
    if (isActive && (selectedUserId || selectedUserPhone)) {
        loadChatHistory();
    }
}

// 加载对话历史列表
async function loadChatHistory() {
    if (!selectedUserId && !selectedUserPhone) {
        historyList.innerHTML = `
            <div class="empty-history">
                <div class="empty-icon">👤</div>
                <p>请先选择用户</p>
                <small>从顶部选择一个用户后即可查看历史对话</small>
            </div>
        `;
        return;
    }

    historyList.innerHTML = `
        <div class="loading-history">
            <div class="loading-spinner"></div>
            <p>加载历史记录...</p>
        </div>
    `;

    try {
        // 判断使用哪个API
        let endpoint;
        if (selectedUserPhone) {
            endpoint = `/api/chat/history/phone/${selectedUserPhone}`;
        } else {
            endpoint = `/api/chat/history/${currentRole}/${selectedUserId}`;
        }

        const response = await fetch(endpoint);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '查询失败');
        }

        displayChatHistory(data.chats || []);
    } catch (error) {
        historyList.innerHTML = `
            <div class="empty-history">
                <div class="empty-icon">❌</div>
                <p>加载失败</p>
                <small>${error.message}</small>
            </div>
        `;
    }
}

// 显示对话历史列表
function displayChatHistory(chats) {
    if (chats.length === 0) {
        historyList.innerHTML = `
            <div class="empty-history">
                <div class="empty-icon">💭</div>
                <p>暂无历史对话</p>
                <small>开始新对话后会自动保存</small>
            </div>
        `;
        return;
    }

    let html = '';
    chats.forEach(chat => {
        const statusClass = `status-${chat.Status || 'active'}`;
        const title = chat.Title || `对话 #${chat.Chat_ID}`;
        const agent = chat.AI_Agent || '-';
        const type = chat.Conversation_Type || 'general';
        const messageCount = chat.Total_Messages || 0;
        const time = formatHistoryTime(chat.Created_At);
        const isCurrent = sessionId && chat.Chat_ID === parseInt(sessionId);

        html += `
            <div class="history-item ${isCurrent ? 'current' : ''}" onclick="loadHistoryChat(${chat.Chat_ID})">
                <div class="history-item-header">
                    <span class="history-title">${escapeHtml(title)}</span>
                    <span class="history-status ${statusClass}">${chat.Status || 'active'}</span>
                </div>
                <div class="history-meta">
                    🤖 ${agent} | 💬 ${messageCount} 条
                </div>
                <div class="history-preview">
                    ${chat.Summary || '暂无摘要'}
                </div>
                <div class="history-time">
                    🕐 ${time}
                </div>
            </div>
        `;
    });

    historyList.innerHTML = html;
}

// 加载历史对话
async function loadHistoryChat(chatId) {
    showLoading();

    try {
        const response = await fetch(`/api/chat/messages/${chatId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '加载失败');
        }

        // 清空当前对话
        chatMessages.innerHTML = '';

        // 加载历史消息
        const messages = data.messages || [];
        messages.forEach(msg => {
            const messageType = msg.Message_Type === 'user' ? 'user' : 'assistant';
            addMessageToUI(msg.Message_Content, messageType);
        });

        // 更新UI状态
        const chat = data.chat;
        if (chat) {
            // 可以选择是否更新sessionId为历史对话的ID
            // sessionId = chatId.toString();
            // sessionIdDisplay.textContent = sessionId.substring(0, 8) + '...';

            if (chat.AI_Agent) {
                updateAgentDisplay(chat.AI_Agent);
            }

            addSystemMessage(`📜 已加载历史对话: ${chat.Title || '对话 #' + chatId} (${messages.length} 条消息)`);
        }

        // 关闭侧边栏
        historySidebar.classList.remove('active');

        // 更新历史列表中的高亮
        loadChatHistory();

    } catch (error) {
        console.error('Error:', error);
        addSystemMessage(`❌ 加载历史对话失败: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// 添加消息到UI(不滚动到底部)
function addMessageToUI(text, type) {
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
}

// 格式化历史时间
function formatHistoryTime(dateStr) {
    if (!dateStr) return '-';

    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    // 小于1分钟
    if (diff < 60000) {
        return '刚刚';
    }

    // 小于1小时
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes}分钟前`;
    }

    // 小于1天
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours}小时前`;
    }

    // 小于7天
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days}天前`;
    }

    // 超过7天显示具体日期
    return date.toLocaleDateString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

