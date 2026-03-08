// 全局变量
let sessionId = null;
let conversationId = null; // 数据库会话ID（用于继续对话）
let currentStage = 'greeting';
let currentAgent = null; // 当前使用的agent
let isProcessing = false;
let selectedUserId = null; // 选中的用户ID
let selectedUserPhone = null; // 选中的用户手机号
let currentRole = 'patient'; // 当前身份：patient 或 doctor
let useStreaming = true; // 是否使用流式模式
let pendingAttachments = []; // 待发送的附件列表（已上传完毕的附件数据）

// 测试用医生ID（实际应从登录系统获取）
const TEST_DOCTOR_ID = "00000000-0000-0000-0000-000000000001";

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
        const newUserId = e.target.value || null;
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

    // 初始化麦克风 PTT 按钮
    initMicButton();

    // 流式模式切换
    const streamingToggle = document.getElementById('streamingToggle');
    const streamingStatus = document.getElementById('streamingStatus');

    if (streamingToggle && streamingStatus) {
        streamingToggle.addEventListener('change', (e) => {
            useStreaming = e.target.checked;
            streamingStatus.textContent = useStreaming ? '开启' : '关闭';
            console.log('[Chat] 流式模式:', useStreaming ? '开启' : '关闭');
        });
    }
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

    // 验证是否已选择患者
    if (!selectedUserId) {
        addSystemMessage('⚠️ 请先选择患者');
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
        // 转换patient_id为字符串以确保正确的类型
        const patientIdStr = String(selectedUserId);

        // 发送请求到后端
        const requestBody = {
            message: message,
            session_id: sessionId,
            patient_id: patientIdStr,
            role: currentRole,
            conversation_id: conversationId
        };

        // 医生模式下添加 doctor_id
        if (currentRole === 'doctor') {
            requestBody.doctor_id = TEST_DOCTOR_ID;
        }

        // 携带附件（如有）
        if (pendingAttachments.length > 0) {
            requestBody.attachments = pendingAttachments.map(att => ({
                file_type: att.file_type,
                filename: att.filename,
                minio_url: att.minio_url || null,
                base64: att.base64 || null,
                mime_type: att.mime_type || null,
                page_images: att.page_images || null,
            }));
            // 发送后清空
            pendingAttachments = [];
            clearAttachmentPreview();
        }

        // 根据开关选择接口
        if (useStreaming) {
            await sendMessageStreaming(requestBody);
        } else {
            await sendMessageNonStreaming(requestBody);
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

// 非流式发送（原有逻辑）
async function sendMessageNonStreaming(requestBody) {
    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

    if (data.conversation_id) {
        conversationId = data.conversation_id;
        console.log('[Chat] 会话ID:', conversationId);
    }

    // 更新阶段和Agent
    currentStage = data.stage;
    updateStageDisplay(data.stage);

    if (data.agent_type) {
        currentAgent = data.agent_type;
        updateAgentDisplay(data.agent_type);
    }

    // 添加AI响应
    addMessage(data.response, 'assistant');

    if (data.is_completed) {
        setTimeout(() => {
            addSystemMessage('✅ 问诊已完成！您可以点击"导出病例"按钮查看完整的患者信息。');
        }, 500);
    }
}

// 流式发送（打字机效果）
async function sendMessageStreaming(requestBody) {
    const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
        throw new Error('网络请求失败');
    }

    // 创建流式消息占位符
    const streamingTextDiv = createStreamingMessage();

    // 处理 SSE 流
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullResponse = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;

            try {
                const data = JSON.parse(line.slice(6));
                const event = data.event;

                if (event === 'start') {
                    if (data.session_id && !sessionId) {
                        sessionId = data.session_id;
                        sessionIdDisplay.textContent = sessionId.substring(0, 8) + '...';
                    }
                    if (data.conversation_id) {
                        conversationId = data.conversation_id;
                        console.log('[Chat] 流式会话ID:', conversationId);
                    }
                }
                else if (event === 'token') {
                    fullResponse += data.content;
                    appendTokenToMessage(streamingTextDiv, data.content);
                }
                else if (event === 'tool_call') {
                    showToolIndicator(data.tool, data.status);
                }
                else if (event === 'agent_switch') {
                    currentAgent = data.to;
                    updateAgentDisplay(data.to);
                }
                else if (event === 'done') {
                    finalizeStreamingMessage(streamingTextDiv);

                    if (data.stage) {
                        currentStage = data.stage;
                        updateStageDisplay(data.stage);
                    }
                    if (data.agent_type) {
                        currentAgent = data.agent_type;
                        updateAgentDisplay(data.agent_type);
                    }
                }
                else if (event === 'error') {
                    finalizeStreamingMessage(streamingTextDiv);
                    streamingTextDiv.textContent = data.message || '发生错误';
                }
            } catch (e) {
                console.warn('解析SSE数据失败:', e);
            }
        }
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

// 创建流式消息占位符（返回textDiv元素用于后续追加内容）
function createStreamingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message streaming';
    messageDiv.id = 'streaming-message';

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.textContent = '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.id = 'streaming-text';

    const cursorSpan = document.createElement('span');
    cursorSpan.className = 'typing-cursor';
    cursorSpan.textContent = '▌';
    textDiv.appendChild(cursorSpan);

    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();

    contentDiv.appendChild(textDiv);
    contentDiv.appendChild(timeDiv);

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return textDiv;
}

// 追加 token 到流式消息
function appendTokenToMessage(textDiv, token) {
    // 移除光标
    const cursor = textDiv.querySelector('.typing-cursor');
    if (cursor) cursor.remove();

    // 追加文本
    textDiv.appendChild(document.createTextNode(token));

    // 重新添加光标
    const newCursor = document.createElement('span');
    newCursor.className = 'typing-cursor';
    newCursor.textContent = '▌';
    textDiv.appendChild(newCursor);

    scrollToBottom();
}

// 完成流式消息（移除光标）
function finalizeStreamingMessage(textDiv) {
    const cursor = textDiv.querySelector('.typing-cursor');
    if (cursor) cursor.remove();

    const messageDiv = document.getElementById('streaming-message');
    if (messageDiv) {
        messageDiv.classList.remove('streaming');
        messageDiv.removeAttribute('id');
    }

    textDiv.removeAttribute('id');
}

// 显示工具调用指示器
function showToolIndicator(toolName, status) {
    let indicator = document.getElementById('tool-indicator');

    if (status === 'start') {
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'tool-indicator';
            indicator.className = 'tool-indicator';
            chatMessages.appendChild(indicator);
        }
        indicator.innerHTML = `<span class="tool-spinner"></span> 正在调用: ${toolName}`;
        indicator.style.display = 'flex';
        scrollToBottom();
    } else if (status === 'end') {
        if (indicator) {
            indicator.style.display = 'none';
        }
    }
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
        // 方案B：开始新会话（不调用reset API，直接创建新会话）
        // 不调用 reset API，避免404错误
        // 旧会话会自动过期（120分钟TTL）

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

        // 重置状态并生成新的session ID
        sessionId = null;
        conversationId = null;  // 重置数据库会话ID
        currentStage = 'greeting';
        generateSessionId();  // 生成新的UUID
        updateStageDisplay('greeting');

        console.log('[Reset] 已创建新会话:', sessionId);

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
    if (!selectedUserId) {
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
        // 根据角色决定查询的 host_id
        // 患者：用患者自己的ID查询
        // 医生：用医生自己的ID查询（医生的历史对话）
        let hostId, userType;
        if (currentRole === 'doctor') {
            hostId = TEST_DOCTOR_ID;
            userType = 'doctor';
        } else {
            hostId = selectedUserId;
            userType = 'patient';
        }

        const endpoint = `/api/conversations?host_id=${hostId}&user_type=${userType}&limit=20&offset=0`;

        const response = await fetch(endpoint);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '查询失败');
        }

        displayChatHistory(data.conversations || []);
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
function displayChatHistory(conversations) {
    if (conversations.length === 0) {
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
    conversations.forEach(conv => {
        const chatId = conv.id;
        const title = conv.title || `对话 #${chatId.substring(0, 8)}`;
        const messageCount = conv.total_messages || 0;
        const time = formatHistoryTime(conv.create_time);
        const isCurrent = conversationId && chatId === conversationId;

        html += `
            <div class="history-item ${isCurrent ? 'current' : ''}" onclick="loadHistoryChat('${chatId}')">
                <div class="history-item-header">
                    <span class="history-title">${escapeHtml(title)}</span>
                </div>
                <div class="history-meta">
                    💬 ${messageCount} 条消息
                </div>
                <div class="history-preview">
                    ${conv.summary || '暂无摘要'}
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
        // 使用新的会话详情API
        const response = await fetch(`/api/conversations/${chatId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '加载失败');
        }

        // 清空当前对话
        chatMessages.innerHTML = '';

        // 加载历史消息
        const messages = data.messages || [];
        messages.forEach(msg => {
            const messageType = msg.message_type === 'user' ? 'user' : 'assistant';
            addMessageToUI(msg.message_content, messageType);
        });

        // 更新UI状态 - 设置conversationId以支持继续对话
        const conversation = data.conversation;
        if (conversation) {
            // 设置会话ID，允许继续对话
            conversationId = chatId;
            console.log('[History] 加载会话，设置conversationId:', conversationId);

            const title = conversation.title || `对话 #${chatId.substring(0, 8)}`;
            addSystemMessage(`📜 已加载历史对话: ${title} (${messages.length} 条消息)。您可以继续该对话。`);
        }

        // 关闭侧边栏
        historySidebar.classList.remove('active');

        // 滚动到底部
        scrollToBottom();

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

// ════════════════════════════════════════════════════════════════════════════
// PTT（Push-to-Talk）语音识别模块
// ════════════════════════════════════════════════════════════════════════════

// PTT 状态变量
let micAudioContext = null;
let micScriptProcessor = null;
let micStream = null;
let micRecordedSamples = [];   // Float32 PCM 采样数组
let micIsRecording = false;
let micIsProcessing = false;

/**
 * 初始化麦克风按钮事件绑定。
 * 支持鼠标（desktop）和触摸（mobile）两种交互方式。
 */
function initMicButton() {
    const micBtn = document.getElementById('micBtn');
    if (!micBtn) return;

    // ── 桌面端：mouse events ──────────────────────────────────────────────
    micBtn.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startRecording();
    });

    micBtn.addEventListener('mouseup', (e) => {
        e.preventDefault();
        stopRecordingAndSend();
    });

    // 防止鼠标移出时卡录音状态
    micBtn.addEventListener('mouseleave', () => {
        if (micIsRecording) {
            stopRecordingAndSend();
        }
    });

    // ── 移动端：touch events ──────────────────────────────────────────────
    micBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecording();
    }, { passive: false });

    micBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecordingAndSend();
    }, { passive: false });

    micBtn.addEventListener('touchcancel', () => {
        if (micIsRecording) {
            stopRecordingAndSend();
        }
    });
}

/**
 * 设置麦克风按钮 UI 状态。
 * @param {'idle'|'recording'|'processing'} state
 */
function setMicState(state) {
    const micBtn = document.getElementById('micBtn');
    const micIcon = document.getElementById('micIcon');
    if (!micBtn || !micIcon) return;

    micBtn.classList.remove('recording', 'processing');

    switch (state) {
        case 'recording':
            micBtn.classList.add('recording');
            micIcon.textContent = '🔴';
            micBtn.disabled = false;
            break;
        case 'processing':
            micBtn.classList.add('processing');
            micIcon.textContent = '⏳';
            micBtn.disabled = true;
            break;
        case 'idle':
        default:
            micIcon.textContent = '🎤';
            micBtn.disabled = false;
            break;
    }
}

/**
 * 开始录音：请求麦克风权限，创建 16kHz AudioContext，开始采集 PCM 样本。
 */
async function startRecording() {
    // 防重入：正在录音或识别中时忽略
    if (micIsRecording || micIsProcessing || isProcessing) return;

    try {
        // 请求麦克风权限
        micStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        // 创建 16kHz AudioContext（确保与 DashScope ASR 要求匹配）
        micAudioContext = new AudioContext({ sampleRate: 16000 });
        const source = micAudioContext.createMediaStreamSource(micStream);

        // ScriptProcessorNode：每 4096 帧触发一次，获取原始 Float32 PCM
        micScriptProcessor = micAudioContext.createScriptProcessor(4096, 1, 1);
        micRecordedSamples = [];

        micScriptProcessor.onaudioprocess = (e) => {
            if (!micIsRecording) return;
            const channelData = e.inputBuffer.getChannelData(0);
            // Float32Array 转为普通数组追加（避免引用被覆盖）
            for (let i = 0; i < channelData.length; i++) {
                micRecordedSamples.push(channelData[i]);
            }
        };

        source.connect(micScriptProcessor);
        // 必须连接到 destination 才能触发 onaudioprocess
        micScriptProcessor.connect(micAudioContext.destination);

        micIsRecording = true;
        setMicState('recording');
        console.log('[ASR] 开始录音（16kHz）');

    } catch (err) {
        console.error('[ASR] 麦克风权限获取失败:', err);
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            addSystemMessage('⚠️ 请在浏览器中允许麦克风权限后再使用语音功能');
        } else if (err.name === 'NotFoundError') {
            addSystemMessage('⚠️ 未检测到麦克风设备，请连接麦克风后重试');
        } else {
            addSystemMessage('⚠️ 麦克风启动失败：' + err.message);
        }
        setMicState('idle');
        _cleanupMic();
    }
}

/**
 * 停止录音，将采集的 PCM 样本打包为 WAV Blob，提交识别。
 */
async function stopRecordingAndSend() {
    if (!micIsRecording) return;

    micIsRecording = false;

    // 停止 AudioContext 和媒体流
    if (micScriptProcessor) {
        micScriptProcessor.disconnect();
        micScriptProcessor = null;
    }
    if (micStream) {
        micStream.getTracks().forEach(t => t.stop());
        micStream = null;
    }
    if (micAudioContext) {
        try { await micAudioContext.close(); } catch (_) {}
        micAudioContext = null;
    }

    const samples = micRecordedSamples;
    micRecordedSamples = [];

    console.log(`[ASR] 停止录音，采集 ${samples.length} 个样本（约 ${(samples.length / 16000).toFixed(1)}s）`);

    // 样本太少（< 0.3s）直接忽略
    if (samples.length < 4800) {
        addSystemMessage('⚠️ 录音时间太短，请按住按钮说话');
        setMicState('idle');
        return;
    }

    // 打包 WAV Blob
    const wavBlob = _createWAVBlob(new Float32Array(samples), 16000);

    // 提交识别
    micIsProcessing = true;
    setMicState('processing');
    await _sendAudioForTranscription(wavBlob);
    micIsProcessing = false;
    setMicState('idle');
}

/**
 * 将 WAV Blob POST 到后端 /api/asr/transcribe，成功后自动发送消息。
 * @param {Blob} wavBlob
 */
async function _sendAudioForTranscription(wavBlob) {
    try {
        const formData = new FormData();
        formData.append('audio', wavBlob, 'recording.wav');

        const res = await fetch('/api/asr/transcribe', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (res.ok && data.text) {
            const recognizedText = data.text.trim();
            console.log('[ASR] 识别结果:', recognizedText);

            if (recognizedText) {
                // 填入输入框并自动发送
                userInput.value = recognizedText;
                await sendMessage();
            }
        } else {
            // 服务端返回错误
            const errCode = data.error_code || '';
            const errMsg = data.message || '识别失败';
            console.warn('[ASR] 识别失败:', errCode, errMsg);

            if (errCode === 'NO_SPEECH_DETECTED') {
                addSystemMessage('⚠️ 未检测到语音，请按住按钮说话后再松开');
            } else if (errCode === 'AUDIO_TOO_SHORT') {
                addSystemMessage('⚠️ 录音时间太短，请按住按钮后再说话');
            } else {
                addSystemMessage(`⚠️ 语音识别失败：${errMsg}`);
            }
        }
    } catch (err) {
        console.error('[ASR] 请求失败:', err);
        addSystemMessage('❌ 语音识别服务暂时不可用，请改用文字输入');
    }
}

/**
 * 将 Float32 PCM 数组打包为标准 WAV Blob（无需任何外部库）。
 * WAV 格式 = 44字节 RIFF/fmt/data 头 + int16 小端序 PCM 数据。
 *
 * @param {Float32Array} float32Samples - Float32 PCM 样本（-1.0 ~ 1.0）
 * @param {number} sampleRate - 采样率（Hz）
 * @returns {Blob} audio/wav
 */
function _createWAVBlob(float32Samples, sampleRate) {
    const numSamples = float32Samples.length;
    const numChannels = 1;
    const bitsPerSample = 16;
    const byteRate = sampleRate * numChannels * (bitsPerSample / 8);
    const blockAlign = numChannels * (bitsPerSample / 8);
    const dataSize = numSamples * blockAlign;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    function writeStr(offset, str) {
        for (let i = 0; i < str.length; i++) {
            view.setUint8(offset + i, str.charCodeAt(i));
        }
    }

    // RIFF chunk descriptor
    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);       // ChunkSize
    writeStr(8, 'WAVE');

    // fmt sub-chunk
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);                 // Subchunk1Size (PCM = 16)
    view.setUint16(20, 1, true);                  // AudioFormat (PCM = 1)
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);

    // data sub-chunk
    writeStr(36, 'data');
    view.setUint32(40, dataSize, true);

    // 写入 PCM 数据（Float32 → Int16）
    const pcmView = new Int16Array(buffer, 44);
    for (let i = 0; i < numSamples; i++) {
        const s = Math.max(-1, Math.min(1, float32Samples[i]));
        pcmView[i] = s < 0 ? s * 32768 : s * 32767;
    }

    return new Blob([buffer], { type: 'audio/wav' });
}

/**
 * 清理麦克风资源（异常情况使用）。
 */
function _cleanupMic() {
    micIsRecording = false;
    if (micScriptProcessor) { micScriptProcessor.disconnect(); micScriptProcessor = null; }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    if (micAudioContext) { micAudioContext.close().catch(() => {}); micAudioContext = null; }
    micRecordedSamples = [];
}

// =====================================================================
// 附件上传功能
// =====================================================================

/**
 * 上传单个文件到 /api/upload，结果放入 pendingAttachments[]
 * @param {File} file
 */
async function uploadAttachment(file) {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
        addSystemMessage(`⚠️ 不支持的文件类型：${file.type}，请上传图片（JPG/PNG/WebP）或 PDF`);
        return;
    }

    const maxSize = file.type === 'application/pdf' ? 30 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxSize) {
        const limitMB = file.type === 'application/pdf' ? 30 : 10;
        addSystemMessage(`⚠️ 文件过大（${(file.size / 1024 / 1024).toFixed(1)}MB），上限 ${limitMB}MB`);
        return;
    }

    // 显示上传中占位
    const previewId = `att-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    renderAttachmentPreviewItem(previewId, file.name, '上传中...', null);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: '上传失败' }));
            updateAttachmentPreviewItem(previewId, file.name, `❌ ${err.detail || '上传失败'}`, null);
            return;
        }

        const data = await res.json();
        pendingAttachments.push(data);

        // 图片显示缩略图，PDF 显示图标
        if (data.file_type === 'image' && data.base64) {
            const src = `data:${data.mime_type};base64,${data.base64.slice(0, 200)}`;
            // 只预览，不用完整 base64 影响 DOM
            updateAttachmentPreviewItem(previewId, data.filename, null, `data:${data.mime_type};base64,${data.base64}`);
        } else {
            updateAttachmentPreviewItem(previewId, data.filename, `📄 ${data.page_count || '?'} 页`, null);
        }

        console.log(`[Attachment] 上传成功: ${data.filename}, type=${data.file_type}`);

    } catch (e) {
        console.error('[Attachment] 上传异常:', e);
        updateAttachmentPreviewItem(previewId, file.name, '❌ 网络错误', null);
    }
}

/**
 * 渲染附件预览项
 */
function renderAttachmentPreviewItem(id, filename, text, imgSrc) {
    const preview = document.getElementById('attachmentPreview');
    if (!preview) return;

    const item = document.createElement('div');
    item.id = id;
    item.style.cssText = 'display:inline-flex;align-items:center;gap:4px;background:#fff;border:1px solid #ddd;border-radius:6px;padding:4px 8px;font-size:12px;max-width:160px;';

    if (imgSrc) {
        const img = document.createElement('img');
        img.src = imgSrc;
        img.style.cssText = 'width:32px;height:32px;object-fit:cover;border-radius:4px;flex-shrink:0;';
        item.appendChild(img);
    } else {
        const span = document.createElement('span');
        span.textContent = text || '...';
        item.appendChild(span);
    }

    const name = document.createElement('span');
    name.style.cssText = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;';
    name.title = filename;
    name.textContent = filename.length > 12 ? filename.slice(0, 10) + '…' : filename;
    item.appendChild(name);

    const del = document.createElement('span');
    del.textContent = '×';
    del.style.cssText = 'cursor:pointer;color:#999;flex-shrink:0;';
    del.onclick = () => {
        item.remove();
        // 从 pendingAttachments 移除对应项
        pendingAttachments = pendingAttachments.filter(a => a.filename !== filename);
        if (document.getElementById('attachmentPreview').children.length === 0) {
            document.getElementById('attachmentPreview').style.display = 'none';
        }
    };
    item.appendChild(del);

    preview.appendChild(item);
    preview.style.display = 'flex';
}

/**
 * 更新预览项内容（上传完成后替换"上传中..."状态）
 */
function updateAttachmentPreviewItem(id, filename, text, imgSrc) {
    const item = document.getElementById(id);
    if (!item) return;
    // 清空重建
    item.innerHTML = '';

    if (imgSrc) {
        const img = document.createElement('img');
        img.src = imgSrc;
        img.style.cssText = 'width:32px;height:32px;object-fit:cover;border-radius:4px;flex-shrink:0;';
        item.appendChild(img);
    } else if (text) {
        const span = document.createElement('span');
        span.textContent = text;
        item.appendChild(span);
    }

    const name = document.createElement('span');
    name.style.cssText = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;';
    name.title = filename;
    name.textContent = filename.length > 12 ? filename.slice(0, 10) + '…' : filename;
    item.appendChild(name);

    const del = document.createElement('span');
    del.textContent = '×';
    del.style.cssText = 'cursor:pointer;color:#999;flex-shrink:0;';
    del.onclick = () => {
        item.remove();
        pendingAttachments = pendingAttachments.filter(a => a.filename !== filename);
        if (document.getElementById('attachmentPreview').children.length === 0) {
            document.getElementById('attachmentPreview').style.display = 'none';
        }
    };
    item.appendChild(del);
}

/**
 * 清空附件预览区
 */
function clearAttachmentPreview() {
    const preview = document.getElementById('attachmentPreview');
    if (preview) {
        preview.innerHTML = '';
        preview.style.display = 'none';
    }
}

// 绑定文件选择事件
document.addEventListener('DOMContentLoaded', () => {
    const attachmentInput = document.getElementById('attachmentInput');
    if (attachmentInput) {
        attachmentInput.addEventListener('change', async (e) => {
            const files = Array.from(e.target.files || []);
            for (const file of files) {
                await uploadAttachment(file);
            }
            // 清空 input 以允许重复选同一文件
            attachmentInput.value = '';
        });
    }
});
