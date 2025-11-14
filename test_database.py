"""
数据库模块测试脚本
用于验证数据库模块是否正常工作
"""

import sys
from datetime import datetime


def test_import():
    """测试模块导入"""
    print("\n" + "="*60)
    print("测试 1: 模块导入")
    print("="*60)
    
    try:
        from database import AppointmentService, DatabaseConnection, DB_CONFIG
        print("✓ 成功导入 AppointmentService")
        print("✓ 成功导入 DatabaseConnection")
        print("✓ 成功导入 DB_CONFIG")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        print("\n请确保已安装 pymysql: pip install pymysql")
        return False


def test_database_connection():
    """测试数据库连接"""
    print("\n" + "="*60)
    print("测试 2: 数据库连接")
    print("="*60)
    
    try:
        from database import DatabaseConnection, DB_CONFIG
        
        print(f"尝试连接到: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        
        db = DatabaseConnection()
        conn = db.connect()
        
        print("✓ 数据库连接成功")
        
        # 测试查询
        result = db.execute_query("SELECT DATABASE() as current_db")
        if result:
            print(f"✓ 当前数据库: {result[0]['current_db']}")
        
        db.close()
        print("✓ 数据库连接已关闭")
        return True
        
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        print("\n可能的原因:")
        print("  1. MySQL 服务未启动")
        print("  2. 用户名或密码错误")
        print("  3. 数据库 medical_db 不存在")
        print("\n解决方案:")
        print("  运行: mysql -u root -p20041118 < database/init_database.sql")
        return False


def test_tables_exist():
    """测试数据表是否存在"""
    print("\n" + "="*60)
    print("测试 3: 数据表检查")
    print("="*60)
    
    try:
        from database import DatabaseConnection
        
        db = DatabaseConnection()
        
        # 检查表是否存在
        tables = db.execute_query("SHOW TABLES")
        table_names = [list(t.values())[0] for t in tables]
        
        required_tables = ['doctor', 'patient', 'appointment']
        
        for table in required_tables:
            if table in table_names:
                print(f"✓ 表 '{table}' 存在")
            else:
                print(f"✗ 表 '{table}' 不存在")
                db.close()
                return False
        
        # 检查医生数据
        doctors = db.execute_query("SELECT COUNT(*) as count FROM doctor")
        doctor_count = doctors[0]['count']
        
        if doctor_count > 0:
            print(f"✓ doctor 表有 {doctor_count} 条数据")
        else:
            print("⚠ doctor 表没有数据，建议运行初始化脚本")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ 表检查失败: {e}")
        return False


def test_appointment_service():
    """测试预约服务"""
    print("\n" + "="*60)
    print("测试 4: 预约服务功能")
    print("="*60)
    
    try:
        from database import AppointmentService
        
        service = AppointmentService()
        print("✓ AppointmentService 实例创建成功")
        
        # 测试数据
        test_data = {
            "patient_info": {
                "name": f"测试患者_{datetime.now().strftime('%H%M%S')}",
                "age": "30",
                "gender": "男",
                "contact": f"138{datetime.now().strftime('%H%M%S')}00",
            },
            "chief_complaint": "测试症状",
            "present_illness": "这是测试数据",
            "medical_history": "无",
            "allergy_history": "无",
            "appointment": {
                "department": "眼科",
                "preferred_time": "明天上午",
                "urgency": "普通"
            }
        }
        
        print("✓ 测试数据准备完成")
        print("\n开始处理预约...")
        
        result = service.process_appointment(test_data)
        
        if result['success']:
            print("\n✓ 预约处理成功！")
            print(f"  患者ID: {result['patient_id']}")
            print(f"  预约ID: {result['appointment_id']}")
            print(f"  医生: {result['doctor_info']['name']} ({result['doctor_info']['title']})")
            print(f"  时间: {result['appointment_time']}")
            
            # 清理测试数据
            service.db.execute_update(
                "DELETE FROM appointment WHERE Appointment_ID = %s",
                (result['appointment_id'],)
            )
            service.db.execute_update(
                "DELETE FROM patient WHERE Patient_ID = %s",
                (result['patient_id'],)
            )
            print("\n✓ 测试数据已清理")
            
        else:
            print(f"\n✗ 预约失败: {result['message']}")
            
            if '未找到符合条件的可用医生' in result['message']:
                print("\n提示: 请确保 doctor 表中有可用医生数据")
                print("可以运行: mysql -u root -p20041118 < database/init_database.sql")
        
        service.close()
        return result['success']
        
    except Exception as e:
        print(f"✗ 预约服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_time_parsing():
    """测试时间解析功能"""
    print("\n" + "="*60)
    print("测试 5: 时间表达式解析")
    print("="*60)
    
    try:
        from database import AppointmentService
        
        service = AppointmentService()
        
        test_cases = [
            "明天上午",
            "后天下午",
            "11月15日",
            "今天下午"
        ]
        
        for expr in test_cases:
            result = service._parse_time_expression(expr)
            if result:
                print(f"✓ '{expr}' → {result.strftime('%Y-%m-%d %H:%M')}")
            else:
                print(f"⚠ '{expr}' 解析失败")
        
        service.close()
        return True
        
    except Exception as e:
        print(f"✗ 时间解析测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("数据库模块测试")
    print("="*60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("模块导入", test_import),
        ("数据库连接", test_database_connection),
        ("数据表检查", test_tables_exist),
        ("预约服务", test_appointment_service),
        ("时间解析", test_time_parsing),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except KeyboardInterrupt:
            print("\n\n测试被用户中断")
            sys.exit(0)
        except Exception as e:
            print(f"\n✗ 测试 '{name}' 出现异常: {e}")
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status} - {name}")
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过！数据库模块工作正常。")
        print("\n下一步:")
        print("  1. 查看 database/QUICKSTART.md 快速入门")
        print("  2. 运行 python database/example_usage.py 查看示例")
        print("  3. 集成到您的应用中")
    else:
        print("\n⚠ 部分测试失败，请根据错误信息进行修复。")
        print("\n常见解决方案:")
        print("  1. 安装依赖: pip install pymysql")
        print("  2. 初始化数据库: mysql -u root -p20041118 < database/init_database.sql")
        print("  3. 检查 MySQL 服务是否启动")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

