# 数据库迁移快速开始

## 🚀 最快执行路径（5分钟）

如果您只想快速补全文档中缺失的字段（系统管理字段 + appointment扩展），执行以下步骤：

### 第1步：备份数据库（必须！）

```bash
mysqldump -h localhost -u root -p medical_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 第2步：执行迁移SQL

```bash
cd d:\Agent\pythonProject1\database
mysql -h localhost -u root -p medical_db < migrations/add_system_fields_and_extend_appointment.sql
```

### 第3步：验证结果

```bash
python verify_migration.py
```

**完成！** 现在您的数据库已经有：
- ✅ 所有表的系统管理字段（Create_By, Update_By, Version, Deleted）
- ✅ appointment表的通用日程功能（Is_Generic_Event, Event_Type, Notes）
- ✅ 所有必要的索引

---

## 📋 完整迁移路径（30分钟）

如果您还需要UUID主键支持，使用自动化脚本：

### 使用Python自动化脚本（推荐）

```bash
cd d:\Agent\pythonProject1\database
python execute_complete_migration.py
```

脚本会自动完成：
1. ✅ 数据库备份
2. ✅ 添加系统管理字段
3. ✅ 扩展appointment表
4. ✅ Phase 1-3 UUID迁移
5. ✅ 验证迁移结果

---

## 📖 详细说明

参见 [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) 获取：
- 完整迁移步骤
- 代码适配指南
- 回滚方案
- 常见问题解答

---

## ❓ 常见问题

### Q: 我需要执行UUID迁移吗？

**A**: 取决于需求：
- **不需要**：单机部署，不对外提供API → 只执行第1步即可
- **需要**：微服务/分库分表/对外API → 执行完整迁移

### Q: 迁移会影响现有数据吗？

**A**: 不会。所有迁移都是**添加字段**，不会修改或删除现有数据。

### Q: 迁移需要多长时间？

**A**:
- 只添加系统字段：5-10分钟
- 完整UUID迁移：30-40分钟

### Q: 如何回滚？

**A**:
```bash
# 方法1：恢复备份
mysql -h localhost -u root -p medical_db < backup_YYYYMMDD_HHMMSS.sql

# 方法2：执行回滚脚本
mysql -h localhost -u root -p medical_db < migrations/rollback_system_fields_and_appointment.sql
```

---

## 🆘 遇到问题？

1. 查看日志：`logs/migration_*.log`
2. 运行验证：`python verify_migration.py`
3. 参考详细文档：[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

---

**版本**: 1.0
**更新日期**: 2025-11-20
