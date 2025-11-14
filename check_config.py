"""
配置检查脚本 - 验证环境配置是否正确
"""
import os
import sys
from pathlib import Path


def check_file_exists(filepath, description):
    """检查文件是否存在"""
    if Path(filepath).exists():
        print(f"[OK] {description}: {filepath}")
        return True
    else:
        print(f"[X] {description}不存在: {filepath}")
        return False


def check_env_file():
    """检查.env文件"""
    print("\n【环境配置检查】")
    if not Path(".env").exists():
        print("[X] .env 文件不存在")
        print("\n请创建 .env 文件并添加以下配置：")
        print("-" * 50)
        print("SILICONFLOW_API_KEY=your_api_key_here")
        print("SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1")
        print("MODEL_NAME=Qwen/Qwen2.5-7B-Instruct")
        print("-" * 50)
        return False
    
    print("[OK] .env 文件存在")
    
    # 尝试加载环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if api_key and api_key != "your_api_key_here":
        print(f"[OK] API密钥已配置 (长度: {len(api_key)})")
        return True
    else:
        print("[X] API密钥未配置或使用的是示例值")
        return False


def check_dependencies():
    """检查依赖包"""
    print("\n【依赖包检查】")
    required_packages = [
        "fastapi",
        "uvicorn",
        "langchain",
        "langchain_openai",
        "pydantic",
        "python-dotenv",
    ]
    
    all_installed = True
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"[OK] {package}")
        except ImportError:
            print(f"[X] {package} 未安装")
            all_installed = False
    
    if not all_installed:
        print("\n请运行以下命令安装依赖：")
        print("pip install -r requirements.txt")
    
    return all_installed


def check_project_structure():
    """检查项目结构"""
    print("\n【项目结构检查】")
    
    required_files = [
        ("requirements.txt", "依赖配置文件"),
        ("main.py", "主程序文件"),
        ("README.md", "说明文档"),
        ("agents/__init__.py", "智能体模块"),
        ("agents/agent_1.py", "1号智能体"),
        ("agents/agent_manager.py", "智能体管理器"),
        ("utils/__init__.py", "工具模块"),
        ("utils/llm_config.py", "LLM配置"),
        ("utils/data_handler.py", "数据处理"),
        ("templates/index.html", "前端页面"),
        ("static/css/style.css", "CSS样式"),
        ("static/js/chat.js", "JavaScript脚本"),
    ]
    
    all_exist = True
    for filepath, description in required_files:
        if not check_file_exists(filepath, description):
            all_exist = False
    
    return all_exist


def check_python_version():
    """检查Python版本"""
    print("\n【Python版本检查】")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print(f"当前Python版本: {version_str}")
    
    if version.major >= 3 and version.minor >= 8:
        print("[OK] Python版本符合要求 (>= 3.8)")
        return True
    else:
        print("[X] Python版本过低，建议使用 Python 3.8 或更高版本")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print(" " * 18 + "系统配置检查工具")
    print("=" * 60)
    
    checks = [
        ("Python版本", check_python_version),
        ("项目结构", check_project_structure),
        ("依赖包", check_dependencies),
        ("环境配置", check_env_file),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[X] {name}检查失败: {str(e)}")
            results.append((name, False))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("检查结果总结")
    print("=" * 60)
    
    for name, result in results:
        status = "[OK] 通过" if result else "[X] 未通过"
        print(f"{status} - {name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 项检查通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有检查通过！可以运行以下命令启动服务：")
        print("   python main.py")
    else:
        print("\n[WARNING] 请根据上述提示完成配置后再启动服务。")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

