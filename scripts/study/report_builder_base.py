import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

sys.stdout.reconfigure(encoding='utf-8')

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_shading(cell, color_hex):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_borders(cell, color="A0A0A0", sz="4", val="single"):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)

def format_document(doc):
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(1.5)
        
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Times New Roman'
    style_normal.font.size = Pt(12)
    style_normal.font.color.rgb = RGBColor(0, 0, 0)
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(4)
    style_normal.paragraph_format.space_before = Pt(0)

def add_title_page(doc, pr_num, pr_theme):
    p0 = doc.add_paragraph()
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p0.paragraph_format.space_after = Pt(2)
    r = p0.add_run("МИНИСТЕРСТВО НАУКИ И ВЫСШЕГО ОБРАЗОВАНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИ")
    r.font.size = Pt(10)
    r.font.bold = True

    p1 = doc.add_paragraph()
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1.paragraph_format.space_after = Pt(2)
    r = p1.add_run("Федеральное государственное бюджетное образовательное учреждение высшего образования\n")
    r.font.size = Pt(10)
    r2 = p1.add_run("«МИРЭА – Российский технологический университет»")
    r2.font.size = Pt(11)
    r2.font.bold = True

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_after = Pt(12)
    r = p2.add_run("РТУ МИРЭА")
    r.font.size = Pt(13)
    r.font.bold = True

    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_after = Pt(2)
    r = p3.add_run("Институт информационных технологий (ИИТ)\nКафедра Промышленной информатики (ПИ)")
    r.font.size = Pt(11)

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_before = Pt(36)
    p_spacer.paragraph_format.space_after = Pt(12)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(6)
    r = p_title.add_run(f"ОТЧЁТ\nПО ПРАКТИЧЕСКОЙ РАБОТЕ № {pr_num}")
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(6)
    r = p_sub.add_run(f"«{pr_theme}»")
    r.font.size = Pt(13)
    r.font.bold = True

    p_disc = doc.add_paragraph()
    p_disc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_disc.paragraph_format.space_after = Pt(40)
    r = p_disc.add_run("по дисциплине «Информатика»\n(Вариант № 6)")
    r.font.size = Pt(12)
    r.font.italic = True

    # Info table
    table = doc.add_table(rows=3, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Cm(8.0)
    table.columns[1].width = Cm(7.5)

    c00 = table.cell(0, 0)
    c01 = table.cell(0, 1)
    c10 = table.cell(1, 0)
    c11 = table.cell(1, 1)
    c20 = table.cell(2, 0)
    c21 = table.cell(2, 1)

    p = c00.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("Выполнил студент:")
    r.font.bold = True
    
    p = c01.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("Жуков Максим Дмитриевич\nГруппа: ИВБО-22-25\nШифр: 25И0566")

    p = c10.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("Дата выполнения:")
    r.font.bold = True
    
    p = c11.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.add_run("«30» сентября 2026 г.")

    p = c20.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("Проверил:")
    r.font.bold = True

    p = c21.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.add_run("ст. преп. каф. ПИ Кодабашян Л.С. /\nдоц. каф. ПИ Сухатерина С.Н.")

    for row in table.rows:
        for cell in row.cells:
            set_cell_borders(cell, color="FFFFFF", sz="0") # invisible border
            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)

    p_bot_space = doc.add_paragraph()
    p_bot_space.paragraph_format.space_before = Pt(60)

    p_city = doc.add_paragraph()
    p_city.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_city.add_run("Москва 2026")
    r.font.size = Pt(12)

    doc.add_page_break()

def add_heading_1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    return p

def add_heading_2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Cm(1.25)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(12)
    r.font.bold = True
    return p

def add_body_p(doc, text="", bold_prefix=""):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(1.25)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(4)
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Times New Roman"
        r_pre.font.size = Pt(12)
        r_pre.font.bold = True
    if text:
        r_txt = p.add_run(text)
        r_txt.font.name = "Times New Roman"
        r_txt.font.size = Pt(12)
    return p

print("Loaded base docx report generator tools successfully.")
