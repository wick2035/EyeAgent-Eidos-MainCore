"""
处方单PDF生成工具 + UUID支持
创建日期：2025-11-17
更新日期：2025-11-20 (UUID支持)
功能：从数据库读取处方数据，使用Word模板填充并生成PDF，包含条形码和logo
"""

import os
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path
import tempfile

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.shared import qn
except ImportError:
    raise ImportError("请安装 python-docx: pip install python-docx")

try:
    import barcode
    from barcode.writer import ImageWriter
except ImportError:
    raise ImportError("请安装 python-barcode: pip install python-barcode")

try:
    from PIL import Image
except ImportError:
    raise ImportError("请安装 Pillow: pip install Pillow")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PrescriptionGenerator:
    """处方单PDF生成器"""
    
    def __init__(self, template_path: str = None, output_dir: str = None):
        """
        初始化处方生成器
        
        Args:
            template_path: Word模板文件路径
            output_dir: 输出目录
        """
        # 默认模板路径
        if template_path is None:
            project_root = Path(__file__).parent.parent
            template_path = project_root / "example" / "prescription_template.docx"
        
        # 默认输出目录
        if output_dir is None:
            project_root = Path(__file__).parent.parent
            output_dir = project_root / "example" / "prescriptions"
        
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"处方生成器初始化完成: 模板={self.template_path}, 输出={self.output_dir}")
    
    def generate_prescription_from_db(self, prescription_id: Union[str, int]) -> Optional[str]:
        """
        从数据库生成处方单PDF (支持UUID)

        Args:
            prescription_id: 处方ID（支持Prescription_ID或Prescription_UUID）

        Returns:
            生成的PDF文件路径，失败返回 None
        """
        try:
            from database.prescription_service import PrescriptionService
            from database.base_service import normalize_id

            # 规范化prescription_id
            try:
                prescription_id_normalized = normalize_id(prescription_id)
            except ValueError as e:
                logger.error(f"无效的处方ID格式: {prescription_id}, 错误: {e}")
                return None

            # 获取处方数据
            service = PrescriptionService()
            data = service.get_prescription_full(prescription_id_normalized)

            if not data:
                logger.error(f"未找到处方ID: {prescription_id_normalized}")
                service.close()
                return None

            # 生成输出文件名（使用规范化的ID）
            prescription_number = data['prescription_info']['prescription_number']
            output_filename = f"prescription_{prescription_id_normalized}_{prescription_number}"

            # 生成处方单
            pdf_path = self.generate_prescription_from_data(data, output_filename)

            service.close()
            return pdf_path

        except Exception as e:
            logger.error(f"从数据库生成处方单失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_prescription_from_data(self, data: Dict[str, Any], output_filename: str = None) -> Optional[str]:
        """
        根据数据字典生成处方单
        
        Args:
            data: 处方数据字典
            output_filename: 输出文件名（不含扩展名）
            
        Returns:
            生成的PDF文件路径，失败返回 None
        """
        try:
            # 生成输出文件名
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"prescription_{timestamp}"
            
            # 生成条形码
            prescription_number = data['prescription_info']['prescription_number']
            barcode_path = self._generate_barcode(prescription_number)
            
            # 填充模板
            doc = self._fill_template(data, barcode_path)
            
            if doc is None:
                logger.error("填充模板失败")
                return None
            
            # 保存为docx
            docx_path = self.output_dir / f"{output_filename}.docx"
            doc.save(str(docx_path))
            logger.info(f"生成docx文件: {docx_path}")
            
            # 转换为PDF
            pdf_path = self._convert_to_pdf(str(docx_path))
            
            # 清理临时条形码文件
            if barcode_path and os.path.exists(barcode_path):
                try:
                    os.remove(barcode_path)
                except:
                    pass
            
            if pdf_path:
                logger.info(f"成功生成处方单: {pdf_path}")
                return pdf_path
            else:
                logger.warning(f"PDF转换失败，返回docx文件路径: {docx_path}")
                return str(docx_path)
                
        except Exception as e:
            logger.error(f"生成处方单失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_barcode(self, prescription_number: str) -> Optional[str]:
        """
        生成处方编号条形码
        
        Args:
            prescription_number: 处方编号
            
        Returns:
            条形码图片路径
        """
        try:
            # 创建临时目录
            temp_dir = tempfile.gettempdir()
            barcode_filename = f"barcode_{prescription_number}"
            barcode_path = os.path.join(temp_dir, barcode_filename)
            
            # 生成条形码（Code128格式）
            code128 = barcode.get('code128', prescription_number, writer=ImageWriter())
            
            # 自定义条形码选项
            options = {
                'module_width': 0.3,  # 条形码宽度
                'module_height': 10.0,  # 条形码高度（mm）
                'quiet_zone': 2.0,  # 左右留白
                'font_size': 10,  # 字体大小
                'text_distance': 3.0,  # 文字距离
                'write_text': True  # 显示文本
            }
            
            # 保存条形码
            full_path = code128.save(barcode_path, options=options)
            
            logger.info(f"生成条形码: {full_path}")
            return full_path
            
        except Exception as e:
            logger.error(f"生成条形码失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _fill_template(self, data: Dict[str, Any], barcode_path: str = None) -> Optional[Document]:
        """
        填充Word模板
        
        Args:
            data: 处方数据
            barcode_path: 条形码图片路径
            
        Returns:
            填充后的Document对象
        """
        try:
            # 检查模板是否存在
            if not self.template_path.exists():
                logger.warning(f"模板文件不存在: {self.template_path}，将创建新文档")
                doc = self._create_new_document(data, barcode_path)
                return doc
            
            # 读取模板
            doc = Document(str(self.template_path))
            
            # 创建占位符映射
            placeholders = self._create_placeholder_mapping(data)
            
            # 替换页眉中的占位符
            for section in doc.sections:
                header = section.header
                # 替换页眉段落
                for paragraph in header.paragraphs:
                    self._replace_placeholders_in_paragraph(paragraph, placeholders)
                # 替换页眉表格
                for table in header.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for paragraph in cell.paragraphs:
                                self._replace_placeholders_in_paragraph(paragraph, placeholders)
            
            # 替换正文段落中的占位符
            for paragraph in doc.paragraphs:
                self._replace_placeholders_in_paragraph(paragraph, placeholders)
            
            # 替换正文表格中的占位符
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            self._replace_placeholders_in_paragraph(paragraph, placeholders)
            
            # 插入条形码（如果提供）
            if barcode_path and os.path.exists(barcode_path):
                self._insert_barcode_to_doc(doc, barcode_path)
            
            # 填充药物明细（支持表格和文本列表两种格式）
            if self._has_drug_list_placeholder(doc):
                # 新模板：使用文本列表格式
                self._fill_drug_details_list(doc, data['drug_details'])
            else:
                # 旧模板：使用表格格式
                self._fill_drug_details_table(doc, data['drug_details'])
            
            return doc
            
        except Exception as e:
            logger.error(f"填充模板失败: {e}")
            import traceback
            traceback.print_exc()
            # 如果模板有问题，创建新文档
            return self._create_new_document(data, barcode_path)
    
    def _create_placeholder_mapping(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        创建占位符到实际值的映射
        
        Args:
            data: 处方数据
            
        Returns:
            占位符映射字典
        """
        prescription_info = data.get('prescription_info', {})
        patient_info = data.get('patient_info', {})
        doctor_info = data.get('doctor_info', {})
        medical_record_info = data.get('medical_record_info', {})
        
        # 格式化日期时间
        prescription_date = prescription_info.get('prescription_date', '')
        if prescription_date:
            try:
                # 尝试解析并格式化日期
                from datetime import datetime
                if isinstance(prescription_date, str):
                    dt = datetime.strptime(prescription_date.split()[0], '%Y-%m-%d')
                    prescription_date = dt.strftime('%Y年%m月%d日')
            except:
                pass
        
        visit_time = medical_record_info.get('visit_time', '')
        if visit_time:
            try:
                # 格式化就诊时间
                if isinstance(visit_time, str) and ' ' in visit_time:
                    date_part, time_part = visit_time.split()
                    dt = datetime.strptime(date_part, '%Y-%m-%d')
                    visit_time = f"{dt.strftime('%Y年%m月%d日')} {time_part.split('.')[0]}"
            except:
                pass
        
        return {
            # 处方信息
            '{{prescription_number}}': str(prescription_info.get('prescription_number', '')),
            '{{prescription_date}}': prescription_date,
            '{{prescription_type}}': str(prescription_info.get('prescription_type', '普通')),
            '{{diagnosis}}': str(prescription_info.get('diagnosis', '')),
            '{{usage_instruction}}': str(prescription_info.get('usage_instruction', '')),
            '{{total_amount}}': f"{prescription_info.get('total_amount', 0):.2f}",
            '{{notes}}': str(prescription_info.get('notes', '')),
            
            # 患者信息
            '{{patient_name}}': str(patient_info.get('name', '')),
            '{{patient_gender}}': str(patient_info.get('gender', '')),
            '{{patient_age}}': str(patient_info.get('age', '')),
            '{{patient_id}}': str(patient_info.get('patient_id', '')),
            '{{patient_phone}}': str(patient_info.get('phone', '')),
            
            # 医生信息
            '{{doctor_name}}': str(doctor_info.get('name', '')),
            '{{doctor_title}}': str(doctor_info.get('title', '')),
            '{{prescriber_name}}': str(prescription_info.get('prescriber_name', doctor_info.get('name', ''))),
            '{{prescriber_signature}}': str(prescription_info.get('prescriber_signature', '')),
            
            # 病例信息
            '{{visit_time}}': visit_time,
            '{{visit_date}}': str(medical_record_info.get('visit_date', '')),
            '{{department}}': str(medical_record_info.get('department', '眼科')),
            '{{chief_complaint}}': str(medical_record_info.get('chief_complaint', '')),
            
            # 其他
            '{{pharmacist_name}}': str(prescription_info.get('pharmacist_name', '')),
            '{{print_time}}': datetime.now().strftime('%Y-%m-%d %H:%M')
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
    
    def _has_drug_list_placeholder(self, doc: Document) -> bool:
        """
        检查文档中是否有{{drug_list}}占位符
        
        Args:
            doc: Document对象
            
        Returns:
            是否存在占位符
        """
        # 检查段落
        for paragraph in doc.paragraphs:
            if '{{drug_list}}' in paragraph.text:
                return True
        
        # 检查表格中的单元格
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        if '{{drug_list}}' in paragraph.text:
                            return True
        
        return False
    
    def _fill_drug_details_list(self, doc: Document, drug_details: list):
        """
        填充药物明细（文本列表格式，非表格）
        
        Args:
            doc: Document对象
            drug_details: 药物明细列表
        """
        try:
            if not drug_details:
                logger.warning("药物明细为空")
                return
            
            # 生成药物列表文本
            drug_lines = []
            for drug in drug_details:
                # 第一行：序号、药物名称、规格、数量
                line1 = f"{drug['index']}、【{drug['drug_name']}】{drug['specification']} x {drug['quantity']} {drug['unit']}"
                drug_lines.append(line1)
                
                # 第二行：用法信息（缩进）
                usage_parts = [f"用法：{drug['dosage']}"]
                if drug.get('route'):
                    usage_parts.append(drug['route'])
                if drug.get('frequency'):
                    usage_parts.append(drug['frequency'])
                if drug.get('special_instructions'):
                    usage_parts.append(f"备注：{drug['special_instructions']}")
                
                line2 = "   " + "  ".join(usage_parts)
                drug_lines.append(line2)
            
            drug_text = "\n".join(drug_lines)
            
            # 替换占位符
            replaced = False
            
            # 在段落中查找并替换
            for paragraph in doc.paragraphs:
                if '{{drug_list}}' in paragraph.text:
                    # 清空段落并逐行添加
                    paragraph.clear()
                    # 将多行文本添加到段落中
                    paragraph.text = drug_text
                    # 设置字体为中文宋体
                    for run in paragraph.runs:
                        run.font.name = '宋体'
                        run.font.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                    replaced = True
                    logger.info(f"已填充药物明细列表（文本格式）: {len(drug_details)} 条")
                    break
            
            if not replaced:
                # 在表格中查找
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for paragraph in cell.paragraphs:
                                if '{{drug_list}}' in paragraph.text:
                                    paragraph.clear()
                                    paragraph.text = drug_text
                                    # 设置字体为中文宋体
                                    for run in paragraph.runs:
                                        run.font.name = '宋体'
                                        run.font.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                                    replaced = True
                                    logger.info(f"已填充药物明细列表（表格内文本格式）: {len(drug_details)} 条")
                                    return
            
            if not replaced:
                logger.warning("未找到{{drug_list}}占位符")
                
        except Exception as e:
            logger.warning(f"填充药物明细列表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _insert_barcode_to_doc(self, doc: Document, barcode_path: str):
        """
        在文档中插入条形码图片
        
        Args:
            doc: Document对象
            barcode_path: 条形码图片路径
        """
        try:
            # 优先扫描页眉区域
            for section in doc.sections:
                header = section.header
                # 检查页眉中的段落
                for paragraph in header.paragraphs:
                    if '{{barcode}}' in paragraph.text:
                        # 只替换包含{{barcode}}的run，不动其他内容（保留图片和艺术字）
                        for run in paragraph.runs:
                            if '{{barcode}}' in run.text:
                                # 替换{{barcode}}为条形码图片
                                run.text = run.text.replace('{{barcode}}', '')
                                run.add_picture(barcode_path, width=Inches(1.8))
                        
                        # 设置段落右对齐
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        logger.info("已插入条形码到页眉右边")
                        return
                
                # 检查页眉中的表格
                for table in header.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for paragraph in cell.paragraphs:
                                if '{{barcode}}' in paragraph.text:
                                    # 只替换包含{{barcode}}的run，不动其他内容（保留图片和艺术字）
                                    for run in paragraph.runs:
                                        if '{{barcode}}' in run.text:
                                            # 替换{{barcode}}为条形码图片
                                            run.text = run.text.replace('{{barcode}}', '')
                                            run.add_picture(barcode_path, width=Inches(1.5))
                                    
                                    # 设置单元格内容右对齐
                                    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                                    logger.info("已插入条形码到页眉表格右边")
                                    return
            
            # 查找包含条形码占位符的正文段落
            for paragraph in doc.paragraphs:
                if '{{barcode}}' in paragraph.text:
                    # 清空段落
                    paragraph.clear()
                    # 添加条形码图片
                    run = paragraph.add_run()
                    run.add_picture(barcode_path, width=Inches(2.5))
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    logger.info("已插入条形码到文档正文")
                    return
            
            # 如果没有找到占位符，尝试在正文表格中查找
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            if '{{barcode}}' in paragraph.text:
                                paragraph.clear()
                                run = paragraph.add_run()
                                run.add_picture(barcode_path, width=Inches(2.0))
                                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                logger.info("已插入条形码到正文表格")
                                return
                                
        except Exception as e:
            logger.warning(f"插入条形码失败: {e}")
    
    def _fill_drug_details_table(self, doc: Document, drug_details: list):
        """
        填充药物明细表格
        
        Args:
            doc: Document对象
            drug_details: 药物明细列表
        """
        try:
            # 查找药物明细表格（通常是包含"RP:"或药物列表的表格）
            target_table = None
            for table in doc.tables:
                # 检查表格的第一行是否包含药物相关标题
                first_row_text = ' '.join([cell.text for cell in table.rows[0].cells])
                if '盒' in first_row_text or '用法' in first_row_text or 'drug' in first_row_text.lower():
                    target_table = table
                    break
            
            if not target_table:
                logger.warning("未找到药物明细表格")
                return
            
            # 假设第一行是标题行，从第二行开始填充
            # 先清空现有数据行（保留标题行）
            while len(target_table.rows) > 1:
                target_table._element.remove(target_table.rows[-1]._element)
            
            # 填充每个药物
            for drug in drug_details:
                row_cells = target_table.add_row().cells
                
                # 根据表格列数填充（需要根据实际模板调整）
                if len(row_cells) >= 4:
                    # 序号
                    row_cells[0].text = str(drug['index'])
                    
                    # 药物名称、规格、数量
                    drug_info = f"【{drug['drug_name']}】{drug['specification']} × {drug['quantity']}{drug['unit']}"
                    row_cells[1].text = drug_info
                    
                    # 用法用量
                    usage_info = f"{drug['dosage']}  {drug['frequency']}"
                    if drug['duration']:
                        usage_info += f"  {drug['duration']}"
                    row_cells[2].text = usage_info
                    
                    # 超量原因/慢性病
                    row_cells[3].text = drug.get('special_instructions', '慢性病' if '慢' in drug.get('special_instructions', '') else '')
                
            logger.info(f"已填充药物明细表格: {len(drug_details)} 条")
            
        except Exception as e:
            logger.warning(f"填充药物明细表格失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_new_document(self, data: Dict[str, Any], barcode_path: str = None) -> Document:
        """
        创建新的处方单文档（当模板不存在时）
        
        Args:
            data: 处方数据
            barcode_path: 条形码图片路径
            
        Returns:
            新创建的Document对象
        """
        doc = Document()
        
        # 添加标题
        title = doc.add_heading('EA 中国视光中心', level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        subtitle = doc.add_heading('处方 笺', level=1)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 添加条形码
        if barcode_path and os.path.exists(barcode_path):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = p.add_run()
            run.add_picture(barcode_path, width=Inches(2.0))
        
        # 患者基本信息
        prescription_info = data.get('prescription_info', {})
        patient_info = data.get('patient_info', {})
        doctor_info = data.get('doctor_info', {})
        medical_record_info = data.get('medical_record_info', {})
        
        doc.add_paragraph(f"处方编号：{prescription_info.get('prescription_number', '')}")
        doc.add_paragraph(f"费别：自费        医保卡号：")
        
        # 患者信息表格
        info_table = doc.add_table(rows=2, cols=6)
        info_table.style = 'Light Grid Accent 1'
        
        cells = info_table.rows[0].cells
        cells[0].text = '姓名'
        cells[1].text = patient_info.get('name', '')
        cells[2].text = '性别'
        cells[3].text = patient_info.get('gender', '')
        cells[4].text = '年龄'
        cells[5].text = str(patient_info.get('age', ''))
        
        cells = info_table.rows[1].cells
        cells[0].text = '患者ID'
        cells[1].text = str(patient_info.get('patient_id', ''))
        cells[2].text = '联系电话'
        cells[3].text = patient_info.get('phone', '')
        cells[4].text = '就诊科室'
        cells[5].text = medical_record_info.get('department', '眼科')
        
        # RP: 标题
        doc.add_heading('RP:', level=2)
        
        # 药物明细表格
        drug_table = doc.add_table(rows=1, cols=4)
        drug_table.style = 'Light Grid Accent 1'
        
        header_cells = drug_table.rows[0].cells
        header_cells[0].text = '序号'
        header_cells[1].text = '药物规格×数量'
        header_cells[2].text = '用法'
        header_cells[3].text = '超量原因/慢性病'
        
        # 填充药物明细
        for drug in data.get('drug_details', []):
            row_cells = drug_table.add_row().cells
            row_cells[0].text = str(drug['index'])
            row_cells[1].text = f"【{drug['drug_name']}】{drug['specification']} × {drug['quantity']}{drug['unit']}"
            row_cells[2].text = f"{drug['dosage']}  {drug['frequency']}"
            row_cells[3].text = drug.get('special_instructions', '')
        
        # 底部信息
        doc.add_paragraph('')
        doc.add_paragraph(f"医生签名：{doctor_info.get('name', '')}            "
                         f"药品金额：{prescription_info.get('total_amount', 0):.2f} 元")
        doc.add_paragraph(f"调配人：                核发：")
        doc.add_paragraph(f"打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        # 注意事项
        doc.add_paragraph('')
        doc.add_paragraph("1. 处方当日有效")
        doc.add_paragraph("2. 大病、特检通道结算者到门诊缴费")
        doc.add_paragraph("3. 自助缴费处无需到窗口盖收费章。")
        
        logger.info("创建了新的处方单文档")
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


# 使用示例
if __name__ == "__main__":
    # 创建生成器实例
    generator = PrescriptionGenerator()
    
    # 从数据库生成处方单
    pdf_path = generator.generate_prescription_from_db(prescription_id=1)
    
    if pdf_path:
        print(f"\n✅ 成功生成处方单: {pdf_path}")
    else:
        print("\n❌ 生成处方单失败")

