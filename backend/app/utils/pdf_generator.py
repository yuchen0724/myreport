# backend/app/utils/pdf_generator.py
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import List, Any
import os
import logging

logger = logging.getLogger(__name__)

class PDFGenerator:
    """PDF 生成器"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_fonts()

    def _setup_fonts(self):
        """设置中文字体"""
        try:
            # 尝试使用系统字体
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('DejaVu', font_path))
                self.styles['Normal'].fontName = 'DejaVu'
                self.styles['Heading1'].fontName = 'DejaVu'
        except Exception:
            logger.warning("中文字体注册失败，使用默认字体")

    def generate_pdf(
        self,
        title: str,
        columns: List[str],
        rows: List[List[Any]],
        filename: str = "report.pdf"
    ) -> BytesIO:
        """
        生成 PDF 文件

        Args:
            title: 报表标题
            columns: 列名列表
            rows: 数据行列表
            filename: 文件名

        Returns:
            PDF 文件流
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        # 创建内容
        story = []

        # 添加标题
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # 居中
        )
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 12))

        # 创建表格数据
        table_data = [columns]  # 表头
        table_data.extend(rows)  # 数据行

        # 创建表格
        table = Table(table_data, repeatRows=1)

        # 设置表格样式
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVu'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        story.append(table)

        # 生成 PDF
        doc.build(story)
        buffer.seek(0)

        return buffer
