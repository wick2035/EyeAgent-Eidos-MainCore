# 已归档文件说明

本文件夹包含不再使用的旧版本文件,仅作归档保留。

## 文件分类

### 旧版本服务文件
- `appointment_service.py` - V1版本预约服务(已被V3替代)
- `appointment_service_v2.py` - V2版本预约服务(已被V3替代)
- `user_history_service.py` - V1版本用户历史服务(已被V2替代)

### 旧版本SQL初始化文件
- `init_database.sql` - V1版本数据库初始化脚本
- `init_database_v2.sql` - V2版本数据库初始化脚本
- `init_database_v3.sql` - V3版本数据库初始化脚本
- `biomechanics_table.sql` - 生物力学表单独脚本(已归并到主脚本)
- `chat_history_table.sql` - 聊天历史表单独脚本(已归并到主脚本)
- `reminder_schema.sql` - 提醒功能表单独脚本(已归并到主脚本)
- `upgrade_to_v3.sql` - V2升级到V3的迁移脚本

### 旧版本执行脚本
- `execute_init_v2.py` - V2版本初始化执行脚本
- `execute_biomechanics_init.py` - 生物力学表初始化脚本
- `execute_chat_init.py` - 聊天历史表初始化脚本
- `execute_reminder_schema.py` - 提醒功能表初始化脚本
- `run_upgrade_to_v3.py` - V3升级执行脚本
- `migrate_to_slot_system.py` - 时间段系统迁移脚本

### 示例和文档文件
- `example_usage.py` - 使用示例代码
- `prescription_queries_example.sql` - 处方查询示例
- `BIOMECHANICS_README.md` - 生物力学功能文档
- `CHAT_HISTORY_README.md` - 聊天历史功能文档
- `prescription_table_readme.md` - 处方表文档
- `QUICKSTART.md` - 快速入门文档

### 迁移历史
- `migrations/` - 数据库迁移历史记录

## 当前使用的文件

请参考父目录中的文件:
- **数据库初始化**: `database_init_complete.sql` (归并了所有表结构)
- **执行脚本**: `execute_database_init.py` (统一的初始化脚本)
- **预约服务**: `appointment_service_v3.py` (最新版本,支持智能时间段管理)
- **用户历史**: `user_history_service_v2.py` (支持电话号多记录查询)

## 注意事项

1. 这些文件已不再使用,保留仅用于参考和回滚
2. 如需恢复旧版本,请先备份当前数据库
3. 建议定期清理此文件夹(如半年后可删除)
4. 新功能开发请使用父目录中的最新版本文件

## 归档日期

2025-11-20
