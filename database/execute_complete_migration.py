#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
================================================================================
完整数据库迁移执行脚本
================================================================================

执行顺序:
  1. 添加系统管理字段 + 扩展appointment表
  2. Phase 1: UUID迁移 - 核心表
  3. Phase 2: UUID迁移 - 业务表
  4. Phase 3: UUID迁移 - 辅助表

注意事项:
  ⚠️  执行前请确保已备份数据库！
  ⚠️  建议在测试环境先执行
  ⚠️  执行过程约需 30-40 分钟

作者: System Migration
日期: 2025-11-20
================================================================================
"""

import os
import sys
import mysql.connector
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.db_config import DB_CONFIG


class DatabaseMigrationExecutor:
    """数据库迁移执行器"""

    def __init__(self):
        self.connection = None
        self.cursor = None
        self.migration_dir = Path(__file__).parent / 'migrations'
        self.migration_order = [
            'add_system_fields_and_extend_appointment.sql',
            'phase1_uuid_migration_core_tables.sql',
            'phase2_uuid_migration_business_tables.sql',
            'phase3_uuid_migration_auxiliary_tables.sql'
        ]
        self.log_file = project_root / 'logs' / f'migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

    def log(self, message, level='INFO'):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f'[{timestamp}] [{level}] {message}'
        print(log_message)

        # 确保日志目录存在
        self.log_file.parent.mkdir(exist_ok=True)

        # 写入日志文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

    def connect(self):
        """连接数据库"""
        try:
            self.log('正在连接数据库...')
            self.connection = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.connection.cursor()
            self.log(f'✓ 成功连接到数据库: {DB_CONFIG["database"]}')
            return True
        except Exception as e:
            self.log(f'✗ 数据库连接失败: {str(e)}', 'ERROR')
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        self.log('数据库连接已关闭')

    def backup_database(self):
        """备份数据库（使用mysqldump）"""
        try:
            self.log('=' * 80)
            self.log('开始备份数据库...')

            backup_dir = project_root / 'database' / 'backups'
            backup_dir.mkdir(exist_ok=True)

            backup_file = backup_dir / f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sql'

            # 构建mysqldump命令
            dump_cmd = f'mysqldump -h {DB_CONFIG["host"]} -u {DB_CONFIG["user"]} -p{DB_CONFIG["password"]} {DB_CONFIG["database"]} > "{backup_file}"'

            # 执行备份
            import subprocess
            result = subprocess.run(dump_cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                self.log(f'✓ 数据库备份成功: {backup_file}')
                return True
            else:
                self.log(f'⚠️  mysqldump 失败，跳过自动备份')
                self.log(f'   请手动备份数据库后继续')
                return self.confirm_manual_backup()

        except Exception as e:
            self.log(f'⚠️  备份过程出错: {str(e)}', 'WARNING')
            self.log('   建议手动备份数据库')
            return self.confirm_manual_backup()

    def confirm_manual_backup(self):
        """确认是否已手动备份"""
        print('\n' + '=' * 80)
        print('⚠️  请确认您已经手动备份了数据库！')
        print('=' * 80)
        response = input('是否已完成备份？(yes/no): ').strip().lower()
        return response in ['yes', 'y']

    def execute_sql_file(self, sql_file_path):
        """执行SQL文件"""
        try:
            self.log('=' * 80)
            self.log(f'执行脚本: {sql_file_path.name}')
            self.log('=' * 80)

            # 读取SQL文件
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 分割SQL语句（处理DELIMITER）
            statements = self._split_sql_statements(sql_content)

            total = len(statements)
            success_count = 0
            error_count = 0

            for idx, statement in enumerate(statements, 1):
                statement = statement.strip()
                if not statement or statement.startswith('/*') or statement.startswith('--'):
                    continue

                try:
                    # 执行SQL语句
                    for result in self.cursor.execute(statement, multi=True):
                        if result.with_rows:
                            rows = result.fetchall()
                            if rows:
                                # 打印SELECT结果
                                for row in rows:
                                    self.log(f'  {row}')

                    self.connection.commit()
                    success_count += 1

                    if idx % 10 == 0:
                        self.log(f'  进度: {idx}/{total} 语句已执行')

                except mysql.connector.Error as e:
                    # 某些错误可以忽略（如列已存在）
                    error_msg = str(e)
                    if 'Duplicate column name' in error_msg or 'Duplicate key name' in error_msg:
                        self.log(f'  ⊙ 跳过: {error_msg}', 'WARNING')
                        success_count += 1
                    else:
                        self.log(f'  ✗ 错误: {error_msg}', 'ERROR')
                        self.log(f'  SQL: {statement[:200]}...')
                        error_count += 1

                        # 是否继续？
                        if error_count > 5:
                            self.log('错误过多，中止迁移', 'ERROR')
                            return False

            self.log(f'✓ 脚本执行完成: 成功 {success_count}, 错误 {error_count}')
            return error_count == 0

        except Exception as e:
            self.log(f'✗ 脚本执行失败: {str(e)}', 'ERROR')
            import traceback
            self.log(traceback.format_exc(), 'ERROR')
            return False

    def _split_sql_statements(self, sql_content):
        """分割SQL语句（处理DELIMITER）"""
        statements = []
        current_delimiter = ';'
        buffer = []

        for line in sql_content.split('\n'):
            line = line.strip()

            # 处理DELIMITER命令
            if line.upper().startswith('DELIMITER'):
                if buffer:
                    statements.append(''.join(buffer))
                    buffer = []
                # 提取新的分隔符
                parts = line.split()
                if len(parts) > 1:
                    current_delimiter = parts[1]
                continue

            # 跳过注释
            if line.startswith('--') or line.startswith('#'):
                continue

            # 累积语句
            buffer.append(line + '\n')

            # 检查是否到达语句结尾
            if line.endswith(current_delimiter):
                statement = ''.join(buffer).rstrip(current_delimiter).strip()
                if statement:
                    statements.append(statement)
                buffer = []

        # 处理最后的缓冲
        if buffer:
            statement = ''.join(buffer).strip()
            if statement:
                statements.append(statement)

        return statements

    def verify_migration(self):
        """验证迁移结果"""
        self.log('=' * 80)
        self.log('验证迁移结果...')
        self.log('=' * 80)

        try:
            # 检查系统字段是否添加
            sql = """
                SELECT TABLE_NAME, COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                AND COLUMN_NAME IN ('Create_By', 'Update_By', 'Version', 'Deleted')
                ORDER BY TABLE_NAME, COLUMN_NAME
            """
            self.cursor.execute(sql, (DB_CONFIG['database'],))
            results = self.cursor.fetchall()

            self.log(f'✓ 找到 {len(results)} 个系统管理字段')

            # 检查UUID字段
            sql = """
                SELECT TABLE_NAME, COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                AND COLUMN_NAME LIKE '%_UUID'
                ORDER BY TABLE_NAME, COLUMN_NAME
            """
            self.cursor.execute(sql, (DB_CONFIG['database'],))
            results = self.cursor.fetchall()

            self.log(f'✓ 找到 {len(results)} 个UUID字段')

            # 检查appointment表的新字段
            sql = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = 'appointment'
                AND COLUMN_NAME IN ('Is_Generic_Event', 'Event_Type', 'Notes')
            """
            self.cursor.execute(sql, (DB_CONFIG['database'],))
            results = self.cursor.fetchall()

            if len(results) == 3:
                self.log('✓ appointment表通用日程字段已添加')
            else:
                self.log(f'⚠️  appointment表字段不完整: {results}', 'WARNING')

            self.log('✓ 迁移验证完成')
            return True

        except Exception as e:
            self.log(f'✗ 验证失败: {str(e)}', 'ERROR')
            return False

    def run(self):
        """执行完整迁移流程"""
        print('=' * 80)
        print('眼科管理系统 - 数据库完整迁移')
        print('=' * 80)
        print()
        print('迁移内容:')
        print('  1. 添加系统管理字段 (Create_By, Update_By, Version, Deleted)')
        print('  2. 扩展appointment表为通用日程表')
        print('  3. 完整UUID迁移 (phase 1-3)')
        print()
        print('⚠️  重要提示:')
        print('   - 此操作将修改数据库结构')
        print('   - 请确保已备份数据库')
        print('   - 预计执行时间: 30-40分钟')
        print('=' * 80)
        print()

        response = input('确认开始迁移？(yes/no): ').strip().lower()
        if response not in ['yes', 'y']:
            print('迁移已取消')
            return

        start_time = datetime.now()
        self.log(f'迁移开始时间: {start_time}')

        try:
            # 1. 备份数据库
            if not self.backup_database():
                self.log('未完成备份，迁移中止', 'ERROR')
                return

            # 2. 连接数据库
            if not self.connect():
                return

            # 3. 执行迁移脚本
            for script_name in self.migration_order:
                script_path = self.migration_dir / script_name

                if not script_path.exists():
                    self.log(f'⚠️  脚本不存在: {script_name}', 'WARNING')
                    continue

                if not self.execute_sql_file(script_path):
                    self.log(f'✗ 脚本执行失败: {script_name}', 'ERROR')
                    response = input('继续执行下一个脚本？(yes/no): ').strip().lower()
                    if response not in ['yes', 'y']:
                        self.log('迁移已中止', 'WARNING')
                        break

            # 4. 验证迁移
            self.verify_migration()

            # 5. 完成
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self.log('=' * 80)
            self.log('✅ 迁移执行完成！')
            self.log(f'总耗时: {duration:.2f} 秒 ({duration/60:.2f} 分钟)')
            self.log(f'日志文件: {self.log_file}')
            self.log('=' * 80)

        except KeyboardInterrupt:
            self.log('\n✗ 迁移被用户中断', 'WARNING')

        except Exception as e:
            self.log(f'✗ 迁移过程出错: {str(e)}', 'ERROR')
            import traceback
            self.log(traceback.format_exc(), 'ERROR')

        finally:
            self.disconnect()


if __name__ == '__main__':
    executor = DatabaseMigrationExecutor()
    executor.run()
