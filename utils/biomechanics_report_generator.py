"""
生物力学报告生成器
支持两种模板类型:
- aidocx1.docx: 基础眼科生物测量模板
- aidocx2.docx: 详细生物力学分析模板
"""
import re
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from docx import Document

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BiomechanicsReportGenerator:
    """生物力学报告生成器"""

    def __init__(self, template_dir: str = "example/TemplateScan/template"):
        """
        初始化生物力学报告生成器

        Args:
            template_dir: 模板文件目录
        """
        self.template_dir = template_dir
        self.template1_path = os.path.join(template_dir, "aidocx1.docx")
        self.template2_path = os.path.join(template_dir, "aidocx2.docx")
        self.output_dir = "example/TemplateScan/reports"

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_basic_report(self, data: Dict[str, Any], output_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        生成基础眼科生物测量报告 (使用 aidocx1.docx 模板)

        Args:
            data: 包含所有占位符数据的字典
            output_filename: 输出文件名（可选，默认自动生成）

        Returns:
            包含success, output_path, message的字典
        """
        try:
            # 检查模板是否存在
            if not os.path.exists(self.template1_path):
                return {
                    'success': False,
                    'message': f'模板文件不存在: {self.template1_path}'
                }

            # 加载模板
            doc = Document(self.template1_path)

            # 定义基础模板的占位符（从main1.py提取）
            required_placeholders = [
                '[Name]', '[Gender]', '[ScanTime]', '[ID]', '[BirthDay]', '[Operator]',
                '[AXL-R]', '[AXL-L]', '[CCT-R]', '[CCT-L]', '[ACD-R]', '[ACD-L]',
                '[LT-R]', '[LT-L]', '[AXL-ACD-LT-R]', '[AXL-ACD-LT-L]',
                '[K1-D-R]', '[K1-mm-R]', '[K1-DEG-R]', '[K1-D-L]', '[K1-mm-L]', '[K1-DEG-L]',
                '[K2-D-R]', '[K2-mm-R]', '[K2-DEG-R]', '[K2-D-L]', '[K2-mm-L]', '[K2-DEG-L]',
                '[DK-R]', '[DK-DEG-R]', '[DK-L]', '[DK-DEG-L]',
                '[WTW-R]', '[WTW-L]', '[PD-R]', '[PD-L]'
            ]

            # 验证必需的数据是否存在
            missing_fields = [field for field in required_placeholders if field not in data]
            if missing_fields:
                print(f"⚠ 警告：缺少以下字段数据，将使用空值: {missing_fields}")

            # 替换所有占位符
            print("开始替换占位符...\n")
            replacement_count = 0
            for placeholder, replacement in data.items():
                if self._replace_placeholder(doc, placeholder, str(replacement)):
                    replacement_count += 1

            # 生成输出文件名
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                patient_name = data.get('[Name]', 'Unknown')
                output_filename = f"biomechanics_basic_{patient_name}_{timestamp}.docx"

            output_path = os.path.join(self.output_dir, output_filename)

            # 保存文档
            doc.save(output_path)
            logger.info(f"生成docx文件: {output_path}")

            # 转换为PDF
            pdf_path = self._convert_to_pdf(output_path)

            # 验证结果
            verification = self._verify_replacements(output_path)

            result = {
                'success': True,
                'docx_path': output_path,
                'pdf_path': pdf_path,
                'output_path': pdf_path if pdf_path else output_path,  # 优先返回PDF路径
                'replacement_count': replacement_count,
                'remaining_placeholders': verification['remaining'],
                'message': f'[OK] 基础报告生成成功！已替换 {replacement_count} 个占位符'
            }

            if pdf_path:
                result['message'] += f"\n[OK] PDF文件生成成功: {pdf_path}"
            else:
                result['message'] += f"\n[WARN] PDF转换失败，仅生成docx文件"

            if verification['remaining']:
                result['message'] += f"\n[WARN] 仍有 {len(verification['remaining'])} 个未替换的占位符"

            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'生成报告失败: {str(e)}'
            }

    def generate_detailed_report(self, data: Dict[str, Any], output_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        生成详细生物力学分析报告 (使用 aidocx2.docx 模板)

        Args:
            data: 包含所有占位符数据的字典
            output_filename: 输出文件名（可选，默认自动生成）

        Returns:
            包含success, output_path, message的字典
        """
        try:
            # 检查模板是否存在
            if not os.path.exists(self.template2_path):
                return {
                    'success': False,
                    'message': f'模板文件不存在: {self.template2_path}'
                }

            # 加载模板
            doc = Document(self.template2_path)

            # 验证数据（详细模板需要更多字段）
            print("开始替换占位符...\n")
            replacement_count = 0

            # 替换所有占位符
            for placeholder, replacement in data.items():
                if self._replace_placeholder(doc, placeholder, str(replacement)):
                    replacement_count += 1

            # 生成输出文件名
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                patient_name = data.get('[Name]', 'Unknown')
                output_filename = f"biomechanics_detailed_{patient_name}_{timestamp}.docx"

            output_path = os.path.join(self.output_dir, output_filename)

            # 保存文档
            doc.save(output_path)
            logger.info(f"生成docx文件: {output_path}")

            # 转换为PDF
            pdf_path = self._convert_to_pdf(output_path)

            # 验证结果
            verification = self._verify_replacements(output_path)

            result = {
                'success': True,
                'docx_path': output_path,
                'pdf_path': pdf_path,
                'output_path': pdf_path if pdf_path else output_path,  # 优先返回PDF路径
                'replacement_count': replacement_count,
                'remaining_placeholders': verification['remaining'],
                'message': f'[OK] 详细报告生成成功！已替换 {replacement_count} 个占位符'
            }

            if pdf_path:
                result['message'] += f"\n[OK] PDF文件生成成功: {pdf_path}"
            else:
                result['message'] += f"\n[WARN] PDF转换失败，仅生成docx文件"

            if verification['remaining']:
                result['message'] += f"\n[WARN] 仍有 {len(verification['remaining'])} 个未替换的占位符"

            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'生成报告失败: {str(e)}'
            }

    def _replace_placeholder_in_paragraph(self, para, placeholder: str, replacement: str) -> bool:
        """
        改进版：处理占位符被分散在多个runs中的情况
        通过合并所有runs的文本，查找并替换，然后重建runs

        Args:
            para: 段落对象
            placeholder: 占位符
            replacement: 替换文本

        Returns:
            是否成功替换
        """
        # 获取完整的段落文本
        full_text = para.text

        # 检查是否包含占位符
        if placeholder not in full_text:
            return False

        # 执行替换
        new_text = full_text.replace(placeholder, replacement)

        # 如果文本有变化
        if new_text != full_text:
            # 保存第一个run的格式
            if para.runs:
                first_run_font = para.runs[0].font

                # 清除所有现有的runs
                for run in para.runs:
                    run.text = ''

                # 在第一个run中设置新文本
                para.runs[0].text = new_text
                # print(f"✓ 替换成功: {placeholder} → {replacement}")  # 避免Windows编码问题
                return True

        return False

    def _replace_placeholder_in_table(self, table, placeholder: str, replacement: str) -> bool:
        """
        替换表格中所有单元格的占位符

        Args:
            table: 表格对象
            placeholder: 占位符
            replacement: 替换文本

        Returns:
            是否成功替换
        """
        replaced = False
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if self._replace_placeholder_in_paragraph(para, placeholder, replacement):
                        replaced = True
        return replaced

    def _replace_placeholder(self, doc, placeholder: str, replacement: str) -> bool:
        """
        替换文档中段落和表格中的所有占位符

        Args:
            doc: 文档对象
            placeholder: 占位符
            replacement: 替换文本

        Returns:
            是否成功替换
        """
        replaced = False

        # 替换段落中的占位符
        for para in doc.paragraphs:
            if self._replace_placeholder_in_paragraph(para, placeholder, replacement):
                replaced = True

        # 替换表格中的占位符
        for table in doc.tables:
            if self._replace_placeholder_in_table(table, placeholder, replacement):
                replaced = True

        return replaced

    def _verify_replacements(self, doc_path: str) -> Dict[str, Any]:
        """
        验证文档中是否还有未替换的占位符

        Args:
            doc_path: 文档路径

        Returns:
            包含remaining列表的字典
        """
        try:
            doc_verify = Document(doc_path)
            remaining_placeholders = []

            # 检查段落
            for para in doc_verify.paragraphs:
                if '[' in para.text and ']' in para.text:
                    # 提取所有占位符
                    matches = re.findall(r'\[[\w-]+\]', para.text)
                    remaining_placeholders.extend(matches)

            # 检查表格
            for table in doc_verify.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for para in cell.paragraphs:
                            if '[' in para.text and ']' in para.text:
                                matches = re.findall(r'\[[\w-]+\]', para.text)
                                remaining_placeholders.extend(matches)

            # 去重
            remaining_placeholders = list(set(remaining_placeholders))

            return {
                'remaining': remaining_placeholders
            }

        except Exception as e:
            print(f"验证失败: {e}")
            return {'remaining': []}

    def _convert_to_pdf(self, docx_path: str) -> Optional[str]:
        """
        将docx文件转换为PDF

        Args:
            docx_path: docx文件路径

        Returns:
            PDF文件路径，失败返回 None
        """
        pdf_path = docx_path.replace('.docx', '.pdf')

        try:
            # 尝试使用 docx2pdf（Windows环境）
            try:
                from docx2pdf import convert
                convert(docx_path, pdf_path)
                logger.info(f"使用docx2pdf转换成功: {pdf_path}")
                return pdf_path
            except Exception as e:
                logger.warning(f"docx2pdf转换失败: {e}")
        except ImportError:
            logger.warning("未安装docx2pdf库")

        try:
            # 尝试使用 pypandoc（跨平台备选方案）
            try:
                import pypandoc
                pypandoc.convert_file(docx_path, 'pdf', outputfile=pdf_path)
                logger.info(f"使用pypandoc转换成功: {pdf_path}")
                return pdf_path
            except Exception as e:
                logger.warning(f"pypandoc转换失败: {e}")
        except ImportError:
            logger.warning("未安装pypandoc库")

        # 如果都失败，返回None
        logger.error(f"PDF转换失败，请手动转换docx文件: {docx_path}")
        return None

    @staticmethod
    def get_basic_template_fields() -> list:
        """获取基础模板需要的字段列表"""
        return [
            '[Name]', '[Gender]', '[ScanTime]', '[ID]', '[BirthDay]', '[Operator]',
            '[AXL-R]', '[AXL-L]', '[CCT-R]', '[CCT-L]', '[ACD-R]', '[ACD-L]',
            '[LT-R]', '[LT-L]', '[AXL-ACD-LT-R]', '[AXL-ACD-LT-L]',
            '[K1-D-R]', '[K1-mm-R]', '[K1-DEG-R]', '[K1-D-L]', '[K1-mm-L]', '[K1-DEG-L]',
            '[K2-D-R]', '[K2-mm-R]', '[K2-DEG-R]', '[K2-D-L]', '[K2-mm-L]', '[K2-DEG-L]',
            '[DK-R]', '[DK-DEG-R]', '[DK-L]', '[DK-DEG-L]',
            '[WTW-R]', '[WTW-L]', '[PD-R]', '[PD-L]'
        ]

    @staticmethod
    def get_detailed_template_fields() -> list:
        """获取详细模板需要的字段列表"""
        fields = [
            '[Name]', '[Gender]', '[ScanDate]', '[Age]', '[ID]', '[BirthDay]', '[Doctor]',
            '[AXL-OD]', '[AXL-OS]',
            '[K1-D-OD]', '[K1-mm-OD]', '[K1-DEG-OD]',
            '[K1-D-OS]', '[K1-mm-OS]', '[K1-DEG-OS]',
            '[K2-D-OD]', '[K2-mm-OD]', '[K2-DEG-OD]',
            '[K2-D-OS]', '[K2-mm-OS]', '[K2-DEG-OS]',
            '[ACD-OD]', '[ACD-OS]', '[CCT-OD]', '[CCT-OS]',
            '[WTW-OD]', '[WTW-OS]', '[TR-OD]', '[TR-OS]',
            '[PrintTime]'
        ]

        # 添加 Ac-T1 到 Ac-T8
        for i in range(1, 9):
            fields.append(f'[Ac-T{i}]')

        # 添加 P-T1 到 P-T8
        for i in range(1, 9):
            fields.append(f'[P-T{i}]')

        # 添加 I1-T1 到 I5-T8 和 R1-T1 到 R5-T8
        for row in range(1, 6):
            for col in range(1, 9):
                fields.append(f'[I{row}-T{col}]')
                fields.append(f'[R{row}-T{col}]')

        return fields


# 测试函数
def test_basic_report():
    """测试基础报告生成"""
    generator = BiomechanicsReportGenerator()

    test_data = {
        '[Name]': '张三',
        '[Gender]': '男',
        '[ScanTime]': '2025-11-18',
        '[ID]': '123456',
        '[BirthDay]': '1990-01-01',
        '[Operator]': '李医生',
        '[AXL-R]': '24.89',
        '[AXL-L]': '24.73',
        '[CCT-R]': '540.1',
        '[CCT-L]': '542.2',
        '[ACD-R]': '3.66',
        '[ACD-L]': '3.51',
        '[LT-R]': '4.28',
        '[LT-L]': '4.30',
        '[AXL-ACD-LT-R]': '16.95',
        '[AXL-ACD-LT-L]': '16.94',
        '[K1-D-R]': '47.47',
        '[K1-mm-R]': '7.11',
        '[K1-DEG-R]': '178',
        '[K1-D-L]': '47.27',
        '[K1-mm-L]': '7.14',
        '[K1-DEG-L]': '14',
        '[K2-D-R]': '48.31',
        '[K2-mm-R]': '6.99',
        '[K2-DEG-R]': '88',
        '[K2-D-L]': '48.09',
        '[K2-mm-L]': '7.02',
        '[K2-DEG-L]': '104',
        '[DK-R]': '-0.84',
        '[DK-DEG-R]': '178',
        '[DK-L]': '-0.81',
        '[DK-DEG-L]': '90',
        '[WTW-R]': '11.80',
        '[WTW-L]': '12.00',
        '[PD-R]': '3.86',
        '[PD-L]': '3.80'
    }

    result = generator.generate_basic_report(test_data)
    print(f"\n测试结果: {result}")


if __name__ == "__main__":
    test_basic_report()
