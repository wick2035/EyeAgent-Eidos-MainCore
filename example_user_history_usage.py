"""
用户历史信息加载功能使用示例
演示如何在对话中使用用户历史信息
"""

from agents.agent_1 import HealthAgent

def example_new_user():
    """示例1：新用户（无历史记录）"""
    print("=" * 60)
    print("示例1：新用户对话")
    print("=" * 60)
    
    # 创建智能体，不提供 user_id（新用户）
    agent = HealthAgent()
    
    # 开始对话
    response1 = agent.chat("你好，我最近眼睛有点不舒服")
    print(f"助手: {response1}\n")
    
    response2 = agent.chat("眼睛有点模糊，看东西不清楚")
    print(f"助手: {response2}\n")


def example_existing_user():
    """示例2：老用户（有历史记录）"""
    print("=" * 60)
    print("示例2：老用户对话（假设用户ID为1）")
    print("=" * 60)
    
    # 创建智能体，提供 user_id（老用户）
    # 注意：这里假设数据库中存在 Patient_ID = 1 的用户
    user_id = 1
    agent = HealthAgent(user_id=user_id)
    
    # 开始对话 - 系统会自动加载用户历史信息
    response1 = agent.chat("你好，我眼睛又不舒服了")
    print(f"助手: {response1}\n")
    
    # AI会参考用户的历史就诊记录
    response2 = agent.chat("跟上次的症状差不多")
    print(f"助手: {response2}\n")
    
    # 老用户无需重复提供基本信息
    response3 = agent.chat("我想预约医生")
    print(f"助手: {response3}\n")


def example_manual_load_history():
    """示例3：手动加载用户历史"""
    print("=" * 60)
    print("示例3：手动加载用户历史")
    print("=" * 60)
    
    # 先创建智能体
    agent = HealthAgent()
    
    # 后续通过某种方式获得用户ID后，手动加载历史
    user_id = 2  # 假设识别出用户ID
    agent._load_user_history(user_id)
    
    # 之后的对话会使用加载的历史信息
    response = agent.chat("我想咨询一下眼睛问题")
    print(f"助手: {response}\n")


def example_check_user_history():
    """示例4：查看用户历史信息"""
    print("=" * 60)
    print("示例4：查看用户历史信息")
    print("=" * 60)
    
    from database.user_history_service import UserHistoryService
    
    service = UserHistoryService()
    
    # 查询用户完整信息
    user_id = 1
    complete_info = service.get_user_complete_info(user_id)
    
    print(f"用户ID: {complete_info['user_id']}")
    print(f"是否有历史记录: {complete_info['has_history']}")
    print(f"历史病例数: {len(complete_info['medical_records'])}")
    print(f"历史预约数: {len(complete_info['appointments'])}")
    print()
    
    # 获取格式化的历史信息文本
    history_text = service.format_user_history_text(user_id)
    print("格式化的历史信息：")
    print(history_text)
    
    service.close()


def example_integration_with_web():
    """示例5：与Web应用集成（伪代码）"""
    print("=" * 60)
    print("示例5：与Web应用集成")
    print("=" * 60)
    
    print("""
    # 在 Flask/FastAPI 等Web框架中的使用示例：
    
    from flask import Flask, request, session
    from agents.agent_1 import HealthAgent
    
    app = Flask(__name__)
    
    # 全局存储每个会话的agent实例
    agents = {}
    
    @app.route('/chat', methods=['POST'])
    def chat():
        session_id = session.get('session_id')
        user_id = session.get('user_id')  # 从session中获取用户ID
        user_message = request.json.get('message')
        
        # 如果是新会话，创建agent
        if session_id not in agents:
            # 传入用户ID，自动加载历史信息
            agents[session_id] = HealthAgent(user_id=user_id)
        
        # 处理对话
        agent = agents[session_id]
        response = agent.chat(user_message)
        
        return {'response': response}
    
    # 用户登录时设置 user_id
    @app.route('/login', methods=['POST'])
    def login():
        phone_number = request.json.get('phone_number')
        # 根据手机号查询用户ID
        # user_id = query_user_id_by_phone(phone_number)
        session['user_id'] = user_id
        return {'success': True}
    """)


if __name__ == "__main__":
    print("""
    用户历史信息加载功能说明
    ========================
    
    功能概述：
    1. 在对话开始前，系统会自动从数据库读取用户的历史信息
    2. 历史信息包括：基本信息、历史病例记录、历史预约记录
    3. AI助手会参考历史信息提供更个性化的咨询服务
    4. 老用户的基本信息和病史会自动预填充，无需重复询问
    
    使用方法：
    1. 创建 HealthAgent 实例时传入 user_id 参数
    2. 如果不传入 user_id，则按新用户处理
    3. 首次调用 chat() 方法时，会自动加载用户历史
    
    数据库要求：
    - 需要有 patient 表（存储患者基本信息和病例）
    - 需要有 appointment 表（存储预约记录）
    - 需要有 doctor 表（存储医生信息）
    - 以 Patient_ID 作为用户唯一标识
    
    """)
    
    # 运行示例（注意：需要数据库中有相应的数据）
    # example_new_user()
    # example_existing_user()
    # example_manual_load_history()
    # example_check_user_history()
    example_integration_with_web()

