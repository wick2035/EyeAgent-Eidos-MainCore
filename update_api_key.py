"""
更新API密钥配置脚本
"""
import os

print("=" * 60)
print("           API密钥配置更新工具")
print("=" * 60)
print()
print("请访问 https://cloud.siliconflow.cn/ 获取您的API密钥")
print()
print("当前.env文件内容：")
print("-" * 60)

# 读取当前配置
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        content = f.read()
    print(content)
else:
    print(".env文件不存在")

print("-" * 60)
print()

# 获取新的API密钥
new_api_key = input("请输入您的新API密钥（按Enter跳过）: ").strip()

if new_api_key:
    # 读取当前内容
    lines = []
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    # 更新或添加API密钥
    found = False
    for i, line in enumerate(lines):
        if line.startswith("SILICONFLOW_API_KEY="):
            lines[i] = f"SILICONFLOW_API_KEY={new_api_key}\n"
            found = True
            break
    
    if not found:
        lines.append(f"SILICONFLOW_API_KEY={new_api_key}\n")
    
    # 确保有BASE_URL和MODEL_NAME
    has_base_url = any(line.startswith("SILICONFLOW_BASE_URL=") for line in lines)
    has_model = any(line.startswith("MODEL_NAME=") for line in lines)
    
    if not has_base_url:
        lines.append("SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1\n")
    if not has_model:
        lines.append("MODEL_NAME=Qwen/Qwen2.5-7B-Instruct\n")
    
    # 写入文件
    with open(".env", "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    print()
    print("[OK] API密钥已更新！")
    print()
    print("现在您可以运行以下命令启动服务：")
    print("  python main.py")
else:
    print()
    print("未更新API密钥")

print()
print("=" * 60)

