"""
病例报告生成工具 - 填充docx模板并转换为PDF + UUID支持
创建日期：2025-11-17
更新日期：2025-11-20 (UUID支持)
"""

import os
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    raise ImportError("请安装 python-docx: pip install python-docx")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportGenerator:
    """病例报告生成器"""
    
    def __init__(self, template_path: str = None, output_dir: str = None):
        """
        初始化报告生成器
        
        Args:
            template_path: docx模板文件路径
            output_dir: 输出目录
        """
        # 默认模板路径
        if template_path is None:
            project_root = Path(__file__).parent.parent
            template_path = project_root / "example" / "bingli.docx"
        
        # 默认输出目录
        if output_dir is None:
            project_root = Path(__file__).parent.parent
            output_dir = project_root / "example" / "reports"
        
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"报告生成器初始化完成: 模板={self.template_path}, 输出={self.output_dir}")
    
    def generate_report_from_data(self, data: Dict[str, Any], output_filename: str = None) -> Optional[str]:
        """
        根据数据字典生成报告
        
        Args:
            data: 符合报告JSON Schema的数据字典
            output_filename: 输出文件名（不含扩展名）
            
        Returns:
            生成的PDF文件路径，失败返回 None
        """
        try:
            # 生成输出文件名
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                patient_name = data.get('patient_info', {}).get('name', 'unknown')
                output_filename = f"report_{patient_name}_{timestamp}"
            
            # 填充模板
            doc = self._fill_template(data)
            
            if doc is None:
                logger.error("填充模板失败")
                return None
            
            # 保存为docx
            docx_path = self.output_dir / f"{output_filename}.docx"
            doc.save(str(docx_path))
            logger.info(f"生成docx文件: {docx_path}")
            
            # 转换为PDF
            pdf_path = self._convert_to_pdf(str(docx_path))
            
            if pdf_path:
                logger.info(f"成功生成病例报告: {pdf_path}")
                return pdf_path
            else:
                logger.warning(f"PDF转换失败，返回docx文件路径: {docx_path}")
                return str(docx_path)
                
        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_report_from_db(self, medical_record_id: Union[str, int]) -> Optional[str]:
        """
        根据病例ID从数据库生成报告 (支持UUID)

        Args:
            medical_record_id: 病例ID（支持Medical_Record_ID或Medical_Record_UUID）

        Returns:
            生成的PDF文件路径，失败返回 None
        """
        try:
            from database.report_service import ReportService
            from database.base_service import normalize_id

            # 规范化medical_record_id
            try:
                medical_record_id_normalized = normalize_id(medical_record_id)
            except ValueError as e:
                logger.error(f"无效的病例ID格式: {medical_record_id}, 错误: {e}")
                return None

            # 获取报告数据
            service = ReportService()
            data = service.get_report_data_for_template(medical_record_id_normalized)

            if not data:
                logger.error(f"未找到病例ID: {medical_record_id_normalized}")
                service.close()
                return None

            # 确保有报告编号
            if not data['patient_info'].get('report_id'):
                report_id = service.assign_report_id(medical_record_id_normalized)
                if report_id:
                    data['patient_info']['report_id'] = report_id

            # 生成报告（使用规范化的ID作为文件名）
            output_filename = f"report_{medical_record_id_normalized}_{data['patient_info'].get('report_id', 'unknown')}"
            pdf_path = self.generate_report_from_data(data, output_filename)

            # 标记报告已打印
            if pdf_path:
                service.mark_report_printed(medical_record_id_normalized)

            service.close()
            return pdf_path

        except Exception as e:
            logger.error(f"从数据库生成报告失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _fill_template(self, data: Dict[str, Any]) -> Optional[Document]:
        """
        填充docx模板
        
        Args:
            data: 报告数据
            
        Returns:
            填充后的Document对象
        """
        try:
            # 检查模板是否存在
            if not self.template_path.exists():
                logger.warning(f"模板文件不存在: {self.template_path}，将创建新文档")
                doc = self._create_new_document(data)
                return doc
            
            # 读取模板
            doc = Document(str(self.template_path))
            
            # 创建占位符映射
            placeholders = self._create_placeholder_mapping(data)
            
            # 替换段落中的占位符
            for paragraph in doc.paragraphs:
                self._replace_placeholders_in_paragraph(paragraph, placeholders)
            
            # 替换表格中的占位符
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            self._replace_placeholders_in_paragraph(paragraph, placeholders)
            
            return doc
            
        except Exception as e:
            logger.error(f"填充模板失败: {e}")
            # 如果模板有问题，创建新文档
            return self._create_new_document(data)
    
    def _create_placeholder_mapping(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        创建占位符到实际值的映射
        
        Args:
            data: 报告数据
            
        Returns:
            占位符映射字典
        """
        patient_info = data.get('patient_info', {})
        medical_history = data.get('medical_history', {})
        examinations = data.get('examinations', {})
        diagnosis = data.get('diagnosis', {})
        treatment = data.get('treatment', {})
        meta = data.get('meta', {})
        
        return {
            # 患者信息
            '{{name}}': str(patient_info.get('name', '')),
            '{{gender}}': str(patient_info.get('gender', '')),
            '{{age}}': str(patient_info.get('age', '')),
            '{{patient_id}}': str(patient_info.get('patient_id', '')),
            '{{report_id}}': str(patient_info.get('report_id', '')),
            '{{visit_time}}': str(patient_info.get('visit_time', '')),
            '{{department}}': str(patient_info.get('department', '')),
            
            # 病史信息
            '{{chief_complaint}}': str(medical_history.get('chief_complaint', '')),
            '{{present_illness_history}}': str(medical_history.get('present_illness_history', '')),
            '{{past_history}}': str(medical_history.get('past_history', '无')),
            '{{allergy_history}}': str(medical_history.get('allergy_history', '无')),
            '{{family_history}}': str(medical_history.get('family_history', '无')),
            
            # 检查信息
            '{{special_exams}}': str(examinations.get('special_exams', '')),
            '{{auxiliary_exams}}': str(examinations.get('auxiliary_exams', '')),
            
            # 诊断信息
            '{{ai_diagnosis}}': str(diagnosis.get('ai_diagnosis', '')),
            '{{initial_diagnosis}}': str(diagnosis.get('initial_diagnosis', '')),
            
            # 治疗信息
            '{{treatment_plan}}': str(treatment.get('treatment_plan', '')),
            
            # 元信息
            '{{doctor_signature}}': str(meta.get('doctor_signature', '')),
            '{{print_time}}': str(meta.get('print_time', datetime.now().strftime('%Y-%m-%d %H:%M')))
        }
    
    def _replace_placeholders_in_paragraph(self, paragraph, placeholders: Dict[str, str]):
        """
        在段落中替换占位符（处理跨run的情况）
        
        Args:
            paragraph: 段落对象
            placeholders: 占位符映射
        """
        # 获取完整的段落文本
        full_text = paragraph.text
        
        # 检查是否需要替换
        need_replace = False
        for placeholder in placeholders.keys():
            if placeholder in full_text:
                need_replace = True
                break
        
        if not need_replace:
            return
        
        # 执行替换
        for placeholder, value in placeholders.items():
            full_text = full_text.replace(placeholder, str(value))
        
        # 清空段落的所有runs，保留第一个run来写入新文本
        # 保存第一个run的格式
        if paragraph.runs:
            first_run = paragraph.runs[0]
            # 清空所有runs
            for run in paragraph.runs:
                run.text = ''
            # 在第一个run中写入替换后的完整文本
            first_run.text = full_text
        else:
            # 如果没有runs，创建一个新的
            paragraph.add_run(full_text)
    
    def _create_new_document(self, data: Dict[str, Any]) -> Document:
        """
        创建新的病例报告文档（当模板不存在时）
        
        Args:
            data: 报告数据
            
        Returns:
            新创建的Document对象
        """
        doc = Document()
        
        # 添加标题
        title = doc.add_heading('眼科病例报告', level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 患者基本信息
        patient_info = data.get('patient_info', {})
        doc.add_heading('患者基本信息', level=1)
        
        info_table = doc.add_table(rows=4, cols=4)
        info_table.style = 'Light Grid Accent 1'
        
        cells = info_table.rows[0].cells
        cells[0].text = '姓名'
        cells[1].text = str(patient_info.get('name', ''))
        cells[2].text = '性别'
        cells[3].text = str(patient_info.get('gender', ''))
        
        cells = info_table.rows[1].cells
        cells[0].text = '年龄'
        cells[1].text = str(patient_info.get('age', ''))
        cells[2].text = '患者ID'
        cells[3].text = str(patient_info.get('patient_id', ''))
        
        cells = info_table.rows[2].cells
        cells[0].text = '报告编号'
        cells[1].text = str(patient_info.get('report_id', ''))
        cells[2].text = '科室'
        cells[3].text = str(patient_info.get('department', ''))
        
        cells = info_table.rows[3].cells
        cells[0].text = '就诊时间'
        cells[1].text = str(patient_info.get('visit_time', ''))
        cells[2].text = ''
        cells[3].text = ''
        
        # 病史信息
        medical_history = data.get('medical_history', {})
        doc.add_heading('病史信息', level=1)
        
        doc.add_paragraph(f"主诉：{medical_history.get('chief_complaint', '')}")
        doc.add_paragraph(f"现病史：{medical_history.get('present_illness_history', '')}")
        doc.add_paragraph(f"既往病史：{medical_history.get('past_history', '无')}")
        doc.add_paragraph(f"过敏史：{medical_history.get('allergy_history', '无')}")
        doc.add_paragraph(f"家族史：{medical_history.get('family_history', '无')}")
        
        # 检查信息
        examinations = data.get('examinations', {})
        if examinations.get('special_exams') or examinations.get('auxiliary_exams'):
            doc.add_heading('检查信息', level=1)
            if examinations.get('special_exams'):
                doc.add_paragraph(f"专项检查：{examinations.get('special_exams')}")
            if examinations.get('auxiliary_exams'):
                doc.add_paragraph(f"辅助检查：{examinations.get('auxiliary_exams')}")
        
        # 诊断信息
        diagnosis = data.get('diagnosis', {})
        doc.add_heading('诊断', level=1)
        
        if diagnosis.get('ai_diagnosis'):
            doc.add_paragraph(f"AI诊断：{diagnosis.get('ai_diagnosis')}")
        doc.add_paragraph(f"初步诊断：{diagnosis.get('initial_diagnosis', '')}")
        
        # 治疗方案
        treatment = data.get('treatment', {})
        if treatment.get('treatment_plan'):
            doc.add_heading('治疗方案', level=1)
            doc.add_paragraph(treatment.get('treatment_plan'))
        
        # 签名和时间
        doc.add_paragraph('')
        meta = data.get('meta', {})
        doc.add_paragraph(f"医生签名：{meta.get('doctor_signature', '')}")
        doc.add_paragraph(f"打印时间：{meta.get('print_time', datetime.now().strftime('%Y-%m-%d %H:%M'))}")
        
        logger.info("创建了新的病例报告文档")
        return doc
    
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
    
    def batch_generate(self, patient_id: Union[str, int], medical_record_ids: list = None) -> list:
        """
        批量生成报告 (支持UUID)

        Args:
            patient_id: 用户ID（支持Patient_ID或Patient_UUID）
            medical_record_ids: 病例ID列表（支持混合INT和UUID），如果为None则生成该用户的所有报告

        Returns:
            生成的PDF文件路径列表
        """
        try:
            from database.report_service import ReportService
            from database.base_service import normalize_id

            # 规范化patient_id
            try:
                patient_id_normalized = normalize_id(patient_id)
            except ValueError as e:
                logger.error(f"无效的患者ID格式: {patient_id}, 错误: {e}")
                return []

            service = ReportService()

            # 如果没有指定病例ID，获取所有病例
            if medical_record_ids is None:
                reports = service.get_all_reports_by_patient(patient_id_normalized)
                # 优先使用Medical_Record_UUID，如果没有则使用Medical_Record_ID
                medical_record_ids = [r.get('Medical_Record_UUID') or r['Medical_Record_ID'] for r in reports]

            # 批量生成
            generated_files = []
            for record_id in medical_record_ids:
                pdf_path = self.generate_report_from_db(record_id)
                if pdf_path:
                    generated_files.append(pdf_path)

            service.close()
            logger.info(f"批量生成完成: 成功 {len(generated_files)}/{len(medical_record_ids)}")
            return generated_files

        except Exception as e:
            logger.error(f"批量生成失败: {e}")
            return []


# ==================== 使用说明 ====================
# 
# 【创建生成器实例】
# generator = ReportGenerator()
# 
# 【从数据库生成报告】
# pdf_path = generator.generate_report_from_db(medical_record_id=1)
# 
# 【从数据字典生成报告】
# data = {
#     "patient_info": {...},
#     "medical_history": {...},
#     ...
# }
# pdf_path = generator.generate_report_from_data(data)
# 
# 【批量生成】
# pdf_paths = generator.batch_generate(patient_id=1)
#

