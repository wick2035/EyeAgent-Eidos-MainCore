"""
生物力学检查数据服务
管理眼科生物力学检查数据的存储和检索

Migration: 已适配UUID主键格式
Updated: 2025-11-21 (UUID Migration)
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from database.db_connection import DatabaseConnection
from database.base_service import BaseServiceWithUUID


class BiomechanicsService(BaseServiceWithUUID):
    """生物力学检查数据服务 - UUID版本"""

    def __init__(self):
        super().__init__()
        self.db = DatabaseConnection()

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'db'):
            self.db.close()

    def get_latest_scan_by_patient(self, patient_uuid: str) -> Optional[Dict[str, Any]]:
        """
        获取患者最新的生物力学检查数据

        Args:
            patient_uuid: 患者UUID

        Returns:
            检查数据字典，如果没有返回None
        """
        query = """
        SELECT * FROM biomechanics_scan
        WHERE Patient_UUID = %s
        ORDER BY Scan_Date DESC
        LIMIT 1
        """

        try:
            result = self.db.fetch_one(query, (patient_uuid,))
            if result:
                return self._format_scan_data(result)
            return None
        except Exception as e:
            print(f"[BiomechanicsServiceUUID] 查询失败: {e}")
            return None

    def get_latest_scan_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        通过手机号获取患者最新的生物力学检查数据

        Args:
            phone_number: 手机号

        Returns:
            检查数据字典，如果没有返回None
        """
        query = """
        SELECT bs.* FROM biomechanics_scan bs
        INNER JOIN patient p ON bs.Patient_UUID = p.Patient_UUID
        WHERE p.Phone_Number = %s
        ORDER BY bs.Scan_Date DESC
        LIMIT 1
        """

        try:
            result = self.db.fetch_one(query, (phone_number,))
            if result:
                return self._format_scan_data(result)
            return None
        except Exception as e:
            print(f"[BiomechanicsServiceUUID] 查询失败: {e}")
            return None

    def get_scan_by_uuid(self, scan_uuid: str) -> Optional[Dict[str, Any]]:
        """
        通过扫描UUID获取生物力学检查数据

        Args:
            scan_uuid: 扫描UUID

        Returns:
            检查数据字典，如果没有返回None
        """
        query = """
        SELECT * FROM biomechanics_scan
        WHERE Scan_UUID = %s
        """

        try:
            result = self.db.fetch_one(query, (scan_uuid,))
            if result:
                return self._format_scan_data(result)
            return None
        except Exception as e:
            print(f"[BiomechanicsServiceUUID] 查询失败: {e}")
            return None

    def get_all_scans_by_patient(self, patient_uuid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取患者的所有生物力学检查记录

        Args:
            patient_uuid: 患者UUID
            limit: 最多返回的记录数

        Returns:
            检查数据列表
        """
        query = """
        SELECT * FROM biomechanics_scan
        WHERE Patient_UUID = %s
        ORDER BY Scan_Date DESC
        LIMIT %s
        """

        try:
            results = self.db.fetch_all(query, (patient_uuid, limit))
            return [self._format_scan_data(row) for row in results]
        except Exception as e:
            print(f"[BiomechanicsServiceUUID] 查询失败: {e}")
            return []

    def create_scan_record(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新的生物力学检查记录

        Args:
            scan_data: 包含检查数据的字典

        Returns:
            包含success, scan_uuid, message的字典
        """
        required_fields = ['Patient_UUID', 'Scan_Date', 'Operator']

        # 验证必需字段
        for field in required_fields:
            if field not in scan_data:
                return {
                    'success': False,
                    'message': f'缺少必需字段: {field}'
                }

        try:
            # 生成Scan_UUID
            scan_uuid = self.generate_uuid()
            scan_data['Scan_UUID'] = scan_uuid

            # 构建插入语句
            columns = ', '.join(scan_data.keys())
            placeholders = ', '.join(['%s'] * len(scan_data))
            values = tuple(scan_data.values())

            query = f"""
            INSERT INTO biomechanics_scan ({columns})
            VALUES ({placeholders})
            """

            self.db.execute(query, values)

            return {
                'success': True,
                'scan_uuid': scan_uuid,
                'message': '检查记录创建成功'
            }

        except Exception as e:
            print(f"[BiomechanicsServiceUUID] 创建记录失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'创建记录失败: {str(e)}'
            }

    def update_scan_record(self, scan_uuid: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新生物力学检查记录

        Args:
            scan_uuid: 扫描UUID
            update_data: 要更新的数据

        Returns:
            包含success, message的字典
        """
        if not update_data:
            return {
                'success': False,
                'message': '没有要更新的数据'
            }

        try:
            # 构建更新语句
            set_clause = ', '.join([f"{key} = %s" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(scan_uuid)

            query = f"""
            UPDATE biomechanics_scan
            SET {set_clause}, Updated_At = NOW()
            WHERE Scan_UUID = %s
            """

            self.db.execute(query, tuple(values))

            return {
                'success': True,
                'message': '检查记录更新成功'
            }

        except Exception as e:
            print(f"[BiomechanicsServiceUUID] 更新记录失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'更新记录失败: {str(e)}'
            }

    def _format_scan_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化数据库查询结果为标准格式

        Args:
            row: 数据库行数据

        Returns:
            格式化后的数据字典
        """
        # 直接返回行数据，保持所有字段
        return dict(row)

    def format_scan_for_report(self, scan_data: Dict[str, Any], report_type: str = 'basic') -> Dict[str, Any]:
        """
        将数据库扫描数据格式化为报告模板占位符格式

        Args:
            scan_data: 数据库中的扫描数据
            report_type: 报告类型 ('basic' 或 'detailed')

        Returns:
            包含占位符键值对的字典
        """
        if report_type == 'basic':
            return self._format_basic_template_data(scan_data)
        elif report_type == 'detailed':
            return self._format_detailed_template_data(scan_data)
        else:
            raise ValueError(f"未知的报告类型: {report_type}")

    def _format_basic_template_data(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化为基础模板数据（aidocx1.docx）

        Args:
            scan_data: 数据库扫描数据

        Returns:
            基础模板占位符数据
        """
        return {
            '[Name]': scan_data.get('Patient_Name', ''),
            '[Gender]': scan_data.get('Gender', ''),
            '[ScanTime]': str(scan_data.get('Scan_Date', '')),
            '[ID]': str(scan_data.get('Patient_UUID', '')),
            '[BirthDay]': str(scan_data.get('Birth_Date', '')),
            '[Operator]': scan_data.get('Operator', ''),
            '[AXL-R]': str(scan_data.get('AXL_R', '')),
            '[AXL-L]': str(scan_data.get('AXL_L', '')),
            '[CCT-R]': str(scan_data.get('CCT_R', '')),
            '[CCT-L]': str(scan_data.get('CCT_L', '')),
            '[ACD-R]': str(scan_data.get('ACD_R', '')),
            '[ACD-L]': str(scan_data.get('ACD_L', '')),
            '[LT-R]': str(scan_data.get('LT_R', '')),
            '[LT-L]': str(scan_data.get('LT_L', '')),
            '[AXL-ACD-LT-R]': str(scan_data.get('VT_R', '')),
            '[AXL-ACD-LT-L]': str(scan_data.get('VT_L', '')),
            '[K1-D-R]': str(scan_data.get('K1_D_R', '')),
            '[K1-mm-R]': str(scan_data.get('K1_mm_R', '')),
            '[K1-DEG-R]': str(scan_data.get('K1_Axis_R', '')),
            '[K1-D-L]': str(scan_data.get('K1_D_L', '')),
            '[K1-mm-L]': str(scan_data.get('K1_mm_L', '')),
            '[K1-DEG-L]': str(scan_data.get('K1_Axis_L', '')),
            '[K2-D-R]': str(scan_data.get('K2_D_R', '')),
            '[K2-mm-R]': str(scan_data.get('K2_mm_R', '')),
            '[K2-DEG-R]': str(scan_data.get('K2_Axis_R', '')),
            '[K2-D-L]': str(scan_data.get('K2_D_L', '')),
            '[K2-mm-L]': str(scan_data.get('K2_mm_L', '')),
            '[K2-DEG-L]': str(scan_data.get('K2_Axis_L', '')),
            '[DK-R]': str(scan_data.get('Astigmatism_R', '')),
            '[DK-DEG-R]': str(scan_data.get('K1_Axis_R', '')),
            '[DK-L]': str(scan_data.get('Astigmatism_L', '')),
            '[DK-DEG-L]': str(scan_data.get('K1_Axis_L', '')),
            '[WTW-R]': str(scan_data.get('WTW_R', '')),
            '[WTW-L]': str(scan_data.get('WTW_L', '')),
            '[PD-R]': str(scan_data.get('Pupil_Diameter_R', '')),
            '[PD-L]': str(scan_data.get('Pupil_Diameter_L', ''))
        }

    def _format_detailed_template_data(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化为详细模板数据（aidocx2.docx）

        Args:
            scan_data: 数据库扫描数据

        Returns:
            详细模板占位符数据
        """
        # 基础数据映射
        template_data = {
            '[Name]': scan_data.get('Patient_Name', ''),
            '[Gender]': scan_data.get('Gender', ''),
            '[ScanDate]': str(scan_data.get('Scan_Date', '')),
            '[Age]': str(scan_data.get('Age', '')),
            '[ID]': str(scan_data.get('Patient_UUID', '')),
            '[BirthDay]': str(scan_data.get('Birth_Date', '')),
            '[Doctor]': scan_data.get('Operator', ''),
            '[AXL-OD]': str(scan_data.get('AXL_R', '')),
            '[AXL-OS]': str(scan_data.get('AXL_L', '')),
            '[K1-D-OD]': str(scan_data.get('K1_D_R', '')),
            '[K1-mm-OD]': str(scan_data.get('K1_mm_R', '')),
            '[K1-DEG-OD]': str(scan_data.get('K1_Axis_R', '')),
            '[K1-D-OS]': str(scan_data.get('K1_D_L', '')),
            '[K1-mm-OS]': str(scan_data.get('K1_mm_L', '')),
            '[K1-DEG-OS]': str(scan_data.get('K1_Axis_L', '')),
            '[K2-D-OD]': str(scan_data.get('K2_D_R', '')),
            '[K2-mm-OD]': str(scan_data.get('K2_mm_R', '')),
            '[K2-DEG-OD]': str(scan_data.get('K2_Axis_R', '')),
            '[K2-D-OS]': str(scan_data.get('K2_D_L', '')),
            '[K2-mm-OS]': str(scan_data.get('K2_mm_L', '')),
            '[K2-DEG-OS]': str(scan_data.get('K2_Axis_L', '')),
            '[ACD-OD]': str(scan_data.get('ACD_R', '')),
            '[ACD-OS]': str(scan_data.get('ACD_L', '')),
            '[CCT-OD]': str(scan_data.get('CCT_R', '')),
            '[CCT-OS]': str(scan_data.get('CCT_L', '')),
            '[WTW-OD]': str(scan_data.get('WTW_R', '')),
            '[WTW-OS]': str(scan_data.get('WTW_L', '')),
            '[TR-OD]': str(scan_data.get('TR_R', '-0.5')),
            '[TR-OS]': str(scan_data.get('TR_L', '-0.5')),
            '[PrintTime]': datetime.now().strftime('%Y-%m-%d')
        }

        # 添加多区域角膜厚度数据 (Ac-T1 到 Ac-T8)
        for i in range(1, 9):
            key = f'Ac_T{i}'
            template_data[f'[Ac-T{i}]'] = str(scan_data.get(key, ''))

        # 添加角膜屈光力数据 (P-T1 到 P-T8)
        for i in range(1, 9):
            key = f'P_T{i}'
            template_data[f'[P-T{i}]'] = str(scan_data.get(key, ''))

        # 添加生物力学参数 (I1-T1 到 I5-T8 和 R1-T1 到 R5-T8)
        for row in range(1, 6):
            for col in range(1, 9):
                i_key = f'I{row}_T{col}'
                r_key = f'R{row}_T{col}'
                template_data[f'[I{row}-T{col}]'] = str(scan_data.get(i_key, ''))
                template_data[f'[R{row}-T{col}]'] = str(scan_data.get(r_key, ''))

        return template_data


# 测试函数
def test_service():
    """测试服务"""
    service = BiomechanicsServiceUUID()

    # 测试数据
    test_data = {
        'Patient_UUID': '550e8400-e29b-41d4-a716-446655440000',
        'Scan_Date': '2025-11-18',
        'Operator': '李医生',
        'Patient_Name': '张三',
        'Gender': '男',
        'Birth_Date': '1990-01-01',
        'AXL_R': 24.89,
        'AXL_L': 24.73,
        'CCT_R': 540.1,
        'CCT_L': 542.2,
        'ACD_R': 3.66,
        'ACD_L': 3.51,
        'LT_R': 4.28,
        'LT_L': 4.30,
        'K1_D_R': 47.47,
        'K1_mm_R': 7.11,
        'K1_Axis_R': 178,
        'K1_D_L': 47.27,
        'K1_mm_L': 7.14,
        'K1_Axis_L': 14,
        'K2_D_R': 48.31,
        'K2_mm_R': 6.99,
        'K2_Axis_R': 88,
        'K2_D_L': 48.09,
        'K2_mm_L': 7.02,
        'K2_Axis_L': 104,
        'WTW_R': 11.80,
        'WTW_L': 12.00,
        'Pupil_Diameter_R': 3.86,
        'Pupil_Diameter_L': 3.80
    }

    # 测试格式化
    formatted = service._format_basic_template_data(test_data)
    print("格式化后的数据:")
    for k, v in formatted.items():
        print(f"{k}: {v}")

    service.close()


if __name__ == "__main__":
    test_service()
