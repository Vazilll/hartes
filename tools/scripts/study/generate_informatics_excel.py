import os
import sys
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding='utf-8')

wb = openpyxl.Workbook()
# remove default sheet
wb.remove(wb.active)

thin = Side(border_style="thin", color="000000")
border = Border(top=thin, left=thin, right=thin, bottom=thin)
header_font = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
sub_header_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
sub_header_font = Font(name="Times New Roman", size=11, bold=True)
regular_font = Font(name="Times New Roman", size=11)
bold_font = Font(name="Times New Roman", size=11, bold=True)
center = Alignment(horizontal="center", vertical="center", wrap_text=True)
left = Alignment(horizontal="left", vertical="center")

# ==========================================
# SHEET 1: ПР1_Кодирование
# ==========================================
ws1 = wb.create_sheet(title="ПР1_Кодирование")
ws1.views.sheetView[0].showGridLines = True

ws1.merge_cells("A1:G1")
ws1["A1"] = "Практическая работа №1: Методы и способы кодировки информации (Вариант 6)"
ws1["A1"].font = Font(name="Times New Roman", size=14, bold=True, color="1F497D")
ws1["A1"].alignment = center

ws1.merge_cells("A2:G2")
ws1["A2"] = "Студент: Жуков Максим Дмитриевич | Группа: ИВБО-22-25 | Шифр: 25И0566"
ws1["A2"].font = Font(name="Times New Roman", size=11, italic=True)
ws1["A2"].alignment = center

# Таблица видеопамяти
headers1 = ["Рисунок", "Формат", "Разрешение (WxH)", "Глубина цвета i (бит)", "Объем по формуле (Кб)", "Размер файла свойства (Кб)", "Размер файла (Байт)"]
for col_idx, h in enumerate(headers1, 1):
    cell = ws1.cell(row=4, column=col_idx, value=h)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = center
    cell.border = border

rows1 = [
    ("Черно-белый «Домик»", "BMP (24-бит)", "640x480", 24, "=ROUND((640*480*24)/(8*1024), 2)", 900.05, 921654),
    ("Черно-белый «Домик»", "JPG", "640x480", 24, "-", 11.37, 11642),
    ("Цветной «Домик2»", "BMP (24-бит)", "640x480", 24, "=ROUND((640*480*24)/(8*1024), 2)", 900.05, 921654),
    ("Цветной «Домик2»", "JPG", "640x480", 24, "-", 20.86, 21360),
    ("Цветной «Домик3» (16 цв.)", "BMP (4-бит)", "640x480", 4, "=ROUND((640*480*4)/(8*1024), 2)", 150.10, 153718),
    ("Цветной «Домик4» (уменьш.)", "BMP (24-бит)", "320x240", 24, "=ROUND((320*240*24)/(8*1024), 2)", 225.05, 230454),
    ("Цветной «Домик4» (уменьш.)", "JPG", "320x240", 24, "-", 8.43, 8628)
]

for r_idx, r_data in enumerate(rows1, 5):
    for c_idx, val in enumerate(r_data, 1):
        cell = ws1.cell(row=r_idx, column=c_idx, value=val)
        cell.font = regular_font
        cell.border = border
        cell.alignment = center if c_idx > 2 else left

# ==========================================
# SHEET 2: ПР5_Логика_2_переменных
# ==========================================
ws2 = wb.create_sheet(title="ПР5_Таблица_истинности")
ws2.views.sheetView[0].showGridLines = True

ws2.merge_cells("A1:F1")
ws2["A1"] = "Практическая работа №5: Логические функции 2-х переменных (Вариант 6)"
ws2["A1"].font = Font(name="Times New Roman", size=14, bold=True, color="1F497D")
ws2["A1"].alignment = center

ws2.merge_cells("A2:F2")
ws2["A2"] = "Функция Варианта 6: F(A, B) = A ∧ (B ∨ ¬A)  |  Студент: Жуков М.Д. (ИВБО-22-25)"
ws2["A2"].font = Font(name="Times New Roman", size=11, italic=True)
ws2["A2"].alignment = center

headers2 = ["A", "B", "¬A (НЕ A)", "B ∨ ¬A (ИЛИ)", "F(A,B) = A ∧ (B ∨ ¬A)", "Аналитич. упрощение (A ∧ B)"]
for col_idx, h in enumerate(headers2, 1):
    cell = ws2.cell(row=4, column=col_idx, value=h)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = center
    cell.border = border

rows2_inputs = [
    (0, 0),
    (0, 1),
    (1, 0),
    (1, 1)
]

for r_idx, (a_val, b_val) in enumerate(rows2_inputs, 5):
    cell_a = ws2.cell(row=r_idx, column=1, value=a_val)
    cell_b = ws2.cell(row=r_idx, column=2, value=b_val)
    # NOT A: =IF(NOT(A5), 1, 0)
    cell_nota = ws2.cell(row=r_idx, column=3, value=f"=IF(NOT(A{r_idx}), 1, 0)")
    # B OR NOT A: =IF(OR(B{r_idx}=1, C{r_idx}=1), 1, 0)
    cell_or = ws2.cell(row=r_idx, column=4, value=f"=IF(OR(B{r_idx}=1, C{r_idx}=1), 1, 0)")
    # F = A AND (B OR NOT A): =IF(AND(A{r_idx}=1, D{r_idx}=1), 1, 0)
    cell_f = ws2.cell(row=r_idx, column=5, value=f"=IF(AND(A{r_idx}=1, D{r_idx}=1), 1, 0)")
    # A AND B: =IF(AND(A{r_idx}=1, B{r_idx}=1), 1, 0)
    cell_simp = ws2.cell(row=r_idx, column=6, value=f"=IF(AND(A{r_idx}=1, B{r_idx}=1), 1, 0)")

    for c in [cell_a, cell_b, cell_nota, cell_or, cell_f, cell_simp]:
        c.font = regular_font
        c.border = border
        c.alignment = center

# ==========================================
# SHEET 3: ПР6_СДНФ_СКНФ
# ==========================================
ws3 = wb.create_sheet(title="ПР6_СДНФ_СКНФ")
ws3.views.sheetView[0].showGridLines = True

ws3.merge_cells("A1:I1")
ws3["A1"] = "Практическая работа №6: СДНФ и СКНФ (Вариант 6, F = 4C3B_16 = 0100 1100 0011 1011_2)"
ws3["A1"].font = Font(name="Times New Roman", size=14, bold=True, color="1F497D")
ws3["A1"].alignment = center

ws3.merge_cells("A2:I2")
ws3["A2"] = "Студент: Жуков Максим Дмитриевич | Группа: ИВБО-22-25 | Шифр: 25И0566"
ws3["A2"].font = Font(name="Times New Roman", size=11, italic=True)
ws3["A2"].alignment = center

headers3 = ["№", "a", "b", "c", "d", "F (Заданная)", "СДНФ (Формула)", "СКНФ (Формула)", "Проверка эквивалентности"]
for col_idx, h in enumerate(headers3, 1):
    cell = ws3.cell(row=4, column=col_idx, value=h)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = center
    cell.border = border

bin_str = "0100110000111011"
# Minterms: 1, 4, 5, 10, 11, 12, 14, 15
# Maxterms: 0, 2, 3, 6, 7, 8, 9, 13

# Формулы Excel для минтермов на строке i:
# m1: =IF(AND(NOT(B5), NOT(C5), NOT(D5), E5), 1, 0)
sdnf_excel_terms = [
    "AND(NOT(B{r}), NOT(C{r}), NOT(D{r}), E{r})",       # m1
    "AND(NOT(B{r}), C{r}, NOT(D{r}), NOT(E{r}))",       # m4
    "AND(NOT(B{r}), C{r}, NOT(D{r}), E{r})",            # m5
    "AND(B{r}, NOT(C{r}), D{r}, NOT(E{r}))",            # m10
    "AND(B{r}, NOT(C{r}), D{r}, E{r})",                 # m11
    "AND(B{r}, C{r}, NOT(D{r}), NOT(E{r}))",            # m12
    "AND(B{r}, C{r}, D{r}, NOT(E{r}))",                 # m14
    "AND(B{r}, C{r}, D{r}, E{r})"                       # m15
]

sknf_excel_terms = [
    "OR(B{r}, C{r}, D{r}, E{r})",                       # M0
    "OR(B{r}, C{r}, NOT(D{r}), E{r})",                  # M2
    "OR(B{r}, C{r}, NOT(D{r}), NOT(E{r}))",             # M3
    "OR(B{r}, NOT(C{r}), NOT(D{r}), E{r})",             # M6
    "OR(B{r}, NOT(C{r}), NOT(D{r}), NOT(E{r}))",        # M7
    "OR(NOT(B{r}), C{r}, D{r}, E{r})",                  # M8
    "OR(NOT(B{r}), C{r}, D{r}, NOT(E{r}))",             # M9
    "OR(NOT(B{r}), NOT(C{r}), D{r}, NOT(E{r}))"         # M13
]

for i in range(16):
    r_idx = i + 5
    a = (i >> 3) & 1
    b = (i >> 2) & 1
    c = (i >> 1) & 1
    d = i & 1
    f_val = int(bin_str[i])

    ws3.cell(row=r_idx, column=1, value=i)
    ws3.cell(row=r_idx, column=2, value=a)
    ws3.cell(row=r_idx, column=3, value=b)
    ws3.cell(row=r_idx, column=4, value=c)
    ws3.cell(row=r_idx, column=5, value=d)
    ws3.cell(row=r_idx, column=6, value=f_val)

    # SDNF formula for this row:
    sdnf_formula = "=IF(OR(" + ", ".join([t.format(r=r_idx) for t in sdnf_excel_terms]) + "), 1, 0)"
    ws3.cell(row=r_idx, column=7, value=sdnf_formula)

    # SKNF formula for this row:
    sknf_formula = "=IF(AND(" + ", ".join([t.format(r=r_idx) for t in sknf_excel_terms]) + "), 1, 0)"
    ws3.cell(row=r_idx, column=8, value=sknf_formula)

    # Verification:
    ws3.cell(row=r_idx, column=9, value=f"=IF(AND(F{r_idx}=G{r_idx}, G{r_idx}=H{r_idx}), \"ИСТИНА (Совпадает)\", \"ОШИБКА\")")

    for col in range(1, 10):
        cell = ws3.cell(row=r_idx, column=col)
        cell.font = regular_font
        cell.border = border
        cell.alignment = center

# Auto-adjust column widths
for ws in [ws1, ws2, ws3]:
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

excel_path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics\Информатика_Лабораторные_Excel_Жуков_ИВБО-22-25.xlsx"
wb.save(excel_path)
print(f"Saved Excel file: {excel_path} ({os.path.getsize(excel_path)} bytes)")
