"""
UUID迁移执行脚本
用于自动执行三个阶段的UUID迁移SQL脚本

使用方法:
    python database/execute_uuid_migration.py --phase all
    python database/execute_uuid_migration.py --phase 1
    python database/execute_uuid_migration.py --phase 2
    python database/execute_uuid_migration.py --phase 3
    python database/execute_uuid_migration.py --rollback

Created: 2025-11-20
"""

import argparse
import sys
import os
from pathlib import Path
import pymysql
from typing import Optional

# 设置UTF-8编码输出(Windows兼容)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.db_config import DB_CONFIG


class UUIDMigrationExecutor:
    """UUID迁移执行器"""

    def __init__(self):
        """初始化数据库连接"""
        self.connection: Optional[pymysql.connections.Connection] = None
        self.migrations_dir = Path(__file__).parent / "migrations"

    def connect(self):
        """连接到数据库"""
        try:
            self.connection = pymysql.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset='utf8mb4'
            )
            print(f"✓ 成功连接到数据库: {DB_CONFIG['database']}")
            return True
        except Exception as e:
            print(f"✗ 数据库连接失败: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            print("✓ 数据库连接已关闭")

    def execute_sql_file(self, sql_file_path: Path) -> bool:
        """
        执行SQL文件

        Args:
            sql_file_path: SQL文件路径

        Returns:
            bool: 是否执行成功
        """
        if not sql_file_path.exists():
            print(f"✗ SQL文件不存在: {sql_file_path}")
            return False

        print(f"\n{'='*70}")
        print(f"执行SQL脚本: {sql_file_path.name}")
        print(f"{'='*70}\n")

        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 分割SQL语句 (以分号+换行为分隔符)
            # 注意: DELIMITER // ... DELIMITER ; 需要特殊处理
            statements = self._split_sql_statements(sql_content)

            cursor = self.connection.cursor()
            executed_count = 0
            failed_count = 0

            for i, statement in enumerate(statements, 1):
                statement = statement.strip()
                if not statement or statement.startswith('--') or statement.startswith('/*'):
                    continue

                try:
                    cursor.execute(statement)
                    executed_count += 1

                    # 打印进度
                    if executed_count % 10 == 0:
                        print(f"  已执行 {executed_count} 条语句...")

                except Exception as e:
                    # 某些语句失败是可接受的 (如 DROP TRIGGER IF EXISTS)
                    if "doesn't exist" not in str(e).lower():
                        print(f"  警告 [语句 {i}]: {e}")
                        failed_count += 1

            self.connection.commit()
            cursor.close()

            print(f"\n✓ SQL脚本执行完成")
            print(f"  成功: {executed_count} 条")
            if failed_count > 0:
                print(f"  警告: {failed_count} 条")

            return True

        except Exception as e:
            print(f"\n✗ SQL脚本执行失败: {e}")
            if self.connection:
                self.connection.rollback()
            return False

    def _split_sql_statements(self, sql_content: str) -> list:
        """
        分割SQL语句,处理 DELIMITER 指令

        Args:
            sql_content: SQL文件内容

        Returns:
            list: SQL语句列表
        """
        lines = sql_content.split('\n')
        statements = []
        current_statement = []
        delimiter = ';'
        in_delimiter_block = False

        for line in lines:
            stripped = line.strip()

            # 处理 DELIMITER 指令
            if stripped.upper().startswith('DELIMITER'):
                if '//' in stripped:
                    delimiter = '//'
                    in_delimiter_block = True
                else:
                    delimiter = ';'
                    in_delimiter_block = False
                continue

            # 跳过注释行
            if stripped.startswith('--') or not stripped:
                continue

            current_statement.append(line)

            # 检查是否到达语句结尾
            if stripped.endswith(delimiter):
                stmt = '\n'.join(current_statement)
                # 移除delimiter
                if delimiter == '//':
                    stmt = stmt.rstrip('//')
                else:
                    stmt = stmt.rstrip(';')

                statements.append(stmt.strip())
                current_statement = []

        # 添加最后一条语句
        if current_statement:
            stmt = '\n'.join(current_statement).strip()
            if stmt:
                statements.append(stmt)

        return statements

    def execute_phase(self, phase: int) -> bool:
        """
        执行指定阶段的迁移

        Args:
            phase: 阶段编号 (1, 2, 或 3)

        Returns:
            bool: 是否执行成功
        """
        phase_files = {
            1: "phase1_uuid_migration_core_tables.sql",
            2: "phase2_uuid_migration_business_tables.sql",
            3: "phase3_uuid_migration_auxiliary_tables.sql"
        }

        if phase not in phase_files:
            print(f"✗ 无效的阶段编号: {phase}")
            return False

        sql_file = self.migrations_dir / phase_files[phase]
        return self.execute_sql_file(sql_file)

    def execute_all_phases(self) -> bool:
        """执行所有阶段的迁移"""
        print("\n" + "="*70)
        print("开始执行UUID迁移 - 全部阶段")
        print("="*70)

        for phase in [1, 2, 3]:
            print(f"\n>>> 执行第 {phase} 阶段...")
            if not self.execute_phase(phase):
                print(f"\n✗ 第 {phase} 阶段执行失败,迁移中止")
                return False

            print(f"✓ 第 {phase} 阶段执行成功")

        print("\n" + "="*70)
        print("✓ UUID迁移全部完成!")
        print("="*70)
        return True

    def rollback_migration(self) -> bool:
        """执行迁移回滚"""
        print("\n" + "="*70)
        print("警告: 即将回滚UUID迁移")
        print("="*70)

        confirm = input("\n确认要回滚所有UUID更改吗? (输入 YES 确认): ")
        if confirm.strip() != "YES":
            print("✗ 回滚已取消")
            return False

        sql_file = self.migrations_dir / "rollback_uuid_migration.sql"
        return self.execute_sql_file(sql_file)

    def verify_migration(self) -> bool:
        """验证迁移状态"""
        print("\n" + "="*70)
        print("验证UUID迁移状态")
        print("="*70 + "\n")

        try:
            cursor = self.connection.cursor(pymysql.cursors.DictCursor)

            # 检查迁移日志表是否存在
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = '_uuid_migration_log'
            """, (DB_CONFIG['database'],))

            result = cursor.fetchone()
            if result['cnt'] == 0:
                print("✗ 迁移日志表不存在,可能尚未执行迁移")
                cursor.close()
                return False

            # 查询迁移状态
            cursor.execute("""
                SELECT phase, COUNT(*) as tables_migrated, SUM(records_migrated) as total_records
                FROM _uuid_migration_log
                WHERE status = 'completed'
                GROUP BY phase
                ORDER BY phase
            """)

            results = cursor.fetchall()
            cursor.close()

            if not results:
                print("✗ 未找到已完成的迁移记录")
                return False

            print("迁移状态:")
            print("-" * 70)
            for row in results:
                phase_name = row['phase'].replace('_', ' ').title()
                print(f"  {phase_name}:")
                print(f"    已迁移表数: {row['tables_migrated']}")
                print(f"    总记录数: {row['total_records']}")
            print("-" * 70)

            # 检查是否所有阶段都完成
            completed_phases = [r['phase'] for r in results]
            all_phases = ['phase1_core', 'phase2_business', 'phase3_auxiliary']

            if set(completed_phases) == set(all_phases):
                print("\n✓ 所有阶段迁移已完成")
                return True
            else:
                missing = set(all_phases) - set(completed_phases)
                print(f"\n⚠  未完成的阶段: {', '.join(missing)}")
                return False

        except Exception as e:
            print(f"\n✗ 验证失败: {e}")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='UUID迁移执行工具')
    parser.add_argument(
        '--phase',
        choices=['1', '2', '3', 'all'],
        help='执行指定阶段的迁移 (1=核心表, 2=业务表, 3=辅助表, all=全部)'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='回滚UUID迁移'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='验证迁移状态'
    )

    args = parser.parse_args()

    # 创建执行器
    executor = UUIDMigrationExecutor()

    # 连接数据库
    if not executor.connect():
        sys.exit(1)

    try:
        success = False

        if args.rollback:
            success = executor.rollback_migration()
        elif args.verify:
            success = executor.verify_migration()
        elif args.phase:
            if args.phase == 'all':
                success = executor.execute_all_phases()
            else:
                success = executor.execute_phase(int(args.phase))
        else:
            parser.print_help()
            sys.exit(0)

        if success:
            print("\n✓ 操作成功完成")
            sys.exit(0)
        else:
            print("\n✗ 操作失败")
            sys.exit(1)

    finally:
        executor.close()


if __name__ == "__main__":
    main()
