import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

sys.stdout.reconfigure(encoding='utf-8')

# Paths
DOCX_PATH = r"C:\Users\Vaz\Downloads\Решение_Кейса_Установка_сервера_HPE_DL580_Gen10.docx"
PDF_PATH = r"C:\Users\Vaz\Downloads\Решение_Кейса_Установка_сервера_HPE_DL580_Gen10.pdf"

# --- 1. BUILD DOCX ---
def build_docx():
    doc = docx.Document()
    
    # Page Setup (A4, 2 cm margins)
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(0.79)
        section.bottom_margin = Inches(0.79)
        section.left_margin = Inches(0.79)
        section.right_margin = Inches(0.79)

    # Base Styles
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    style_normal.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(6)

    def set_cell_background(cell, hex_color):
        shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading_elm)

    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    # Document Header / Title Block
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    run_sub = title_p.add_run("РЕШЕНИЕ КЕЙСА № 2 | HARDWARE-ИНЖЕНЕРИЯ И ИТ-ИНФРАСТРУКТУРА\n")
    run_sub.font.size = Pt(10)
    run_sub.font.bold = True
    run_sub.font.color.rgb = RGBColor(0x00, 0x56, 0x91)

    run_title = title_p.add_run("Физическая установка и регламент ввода в эксплуатацию сервера HPE ProLiant DL580 Gen10 в серверную стойку")
    run_title.font.size = Pt(18)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x11, 0x11, 0x11)

    # Info Table
    meta_table = doc.add_table(rows=2, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False

    meta_data = [
        [("Объект установки:", True), ("Сервер HPE ProLiant DL580 Gen10 (4U Chassis)", False)],
        [("Ответственный инженер:", True), ("Инженер ИТ-инфраструктуры (Жуков М. Д.)", False)],
    ]
    for r_idx, row in enumerate(meta_data):
        for c_idx, (text, is_bold) in enumerate(row):
            cell = meta_table.cell(r_idx, c_idx)
            cell.text = text
            p = cell.paragraphs[0]
            p.runs[0].font.bold = is_bold
            p.runs[0].font.size = Pt(9.5)
            set_cell_background(cell, "F2F4F7")
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

    doc.add_paragraph() # Spacer

    # Section 1: Introduction & Scenario
    h1 = doc.add_heading("1. Вводная часть и сценарий задачи", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x00, 0x56, 0x91)
    
    p = doc.add_paragraph(
        "В рамках полученного тикета компании необходимо произвести физический монтаж, подключение питания "
        "и высокоскоростной сетевой инфраструктуры, а также выполнить первичную программно-аппаратную настройку "
        "нового 4-сокетного флагманского сервера HPE ProLiant DL580 Gen10 в серверный шкаф 19\"."
    )
    
    # Specs Box
    callout = doc.add_table(rows=1, cols=1)
    callout.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_cell = callout.cell(0, 0)
    set_cell_background(c_cell, "EBF3FA")
    set_cell_margins(c_cell, top=120, bottom=120, left=180, right=180)
    cp = c_cell.paragraphs[0]
    c_run = cp.add_run("📋 ТЕХНИЧЕСКИЙ ПРОФИЛЬ ОБЪЕКТА (HPE ProLiant DL580 Gen10):\n")
    c_run.font.bold = True
    c_run.font.size = Pt(10)
    c_run.font.color.rgb = RGBColor(0x00, 0x56, 0x91)
    
    specs_text = (
        "• Форм-фактор: 4U Rack Mount (Высота: 17.48 см, Ширина: 44.55 см, Глубина: 75.18 см, Вес: до 52 кг).\n"
        "• Архитектура: До 4 процессоров Intel Xeon Scalable 1-го/2-го поколения, 48 слотов DIMM (до 6 ТБ RAM DDR4).\n"
        "• Питание: До 4 х резервируемых БП HPE Flex Slot мощностью 800W/1600W Platinum/Titanium (Схема N+N / N+1).\n"
        "• Чипсет управления: HPE iLO 5 (Integrated Lights-Out) с аппаратным модулем защиты Silicon Root of Trust."
    )
    cp.add_run(specs_text).font.size = Pt(9.5)

    doc.add_paragraph()

    # Section 2: Preparation
    h2 = doc.add_heading("2. Шаг 1. Подготовка к установке оборудования", level=1)
    h2.runs[0].font.color.rgb = RGBColor(0x00, 0x56, 0x91)

    doc.add_heading("2.1. Проверка комплектности поставки", level=2)
    p = doc.add_paragraph(
        "Перед началом физических работ производится распаковка и аудит по упаковочному листу (Packing Slip):\n"
        "1. Шасси сервера HPE ProLiant DL580 Gen10 с установленными компонентами (CPU, RAM, RAID, БП, Fan modules).\n"
        "2. Комплект телескопических шариковых рельс скольжения (HPE Easy Install Rack Rail Kit 4U).\n"
        "3. Кабельный органайзер за задней панелью (Cable Management Arm — CMA).\n"
        "4. Силовые кабели питания C19-C20 (или C13-C14 в зависимости от установленнных БП) — 4 шт.\n"
        "5. Сетевые трансиверы SFP+/QSFP+ или оптические/медные патч-корды Cat6A.\n"
        "6. Конверт с лицензионными ключами (iLO 5 Advanced License) и конверт с заводским паролем iLO Tag."
    )

    doc.add_heading("2.2. Подготовка монтажного инструментария", level=2)
    p = doc.add_paragraph(
        "Для безопасного монтажа подготавливается комплект инструментарии и средств защиты:\n"
        "• Антистатический браслет (ESD Wrist Strap) с заземляющим проводником (крокодил) — ОБЯЗАТЕЛЬНО.\n"
        "• Отвертка крестовая PH2 / PH3 и отвертка Torx T15 (стандарт HPE).\n"
        "• Серверный подъемник (ServerLIFT) или помощь второго/третьего инженера (вес шасси ~50 кг).\n"
        "• Маркировочный принтер (Brady/Brother) для наклейки этикеток на кабельные трассы.\n"
        "• Нейлоновые стяжки-липучки (Velcro) для формирования чистых кабельных жгутов."
    )

    doc.add_heading("2.3. Планирование пространства и теплового баланса в стойке", level=2)
    p = doc.add_paragraph(
        "• Расчет юнитов (U-место): Сервер занимает 4U. Выбирается нижняя часть стойки (юниты U5–U8). "
        "Это снижает центр тяжести шкафа и предотвращает его опрокидывание при выдвижении сервера на рельсах.\n"
        "• Охлаждение (Airflow): Направление воздушного потока Front-to-Back (холодный коридор спереди, горячий сзади). "
        "Проверяется наличие заглушек (Blanking panels) в неиспользуемых юнитах стойки для предотвращения закольцовывания горячего воздуха.\n"
        "• Энерговыделение и PDU: Максимальное энергопотребление сервера при peak-нагрузке может достигать 3200 Вт. "
        "Питание равномерно распределяется между двумя независимыми стойковыми блоками распределения питания PDU-A (Ввод А) и PDU-B (Ввод Б от ИБП)."
    )

    # Section 3: Cabling
    h3 = doc.add_heading("3. Шаг 2. Кабельные подключения и коммутация", level=1)
    h3.runs[0].font.color.rgb = RGBColor(0x00, 0x56, 0x91)

    p = doc.add_paragraph(
        "Все кабельные линии маркируются с обоих концов согласно схеме коммутации [ИмяСервера_Порт <-> Коммутатор_Порт]."
    )

    # Table of Connections
    table_cables = doc.add_table(rows=5, cols=4)
    table_cables.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_cables.autofit = False

    headers = ["Интерфейс сервера", "Тип кабеля / Разъем", "Точка назначения", "Назначение и Резервирование"]
    for idx, text in enumerate(headers):
        cell = table_cables.cell(0, idx)
        cell.text = text
        p = cell.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(cell, "005691")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)

    rows_data = [
        ["Power Supply 1 & 2 (БП1, БП2)", "C19-C20 / C13-C14 c защелкой", "PDU A (Основной фидер А)", "Питание контура А (N+N Redundancy)"],
        ["Power Supply 3 & 4 (БП3, БП4)", "C19-C20 / C13-C14 c защелкой", "PDU B (Резервный ИБП Б)", "Питание контура Б (N+N Redundancy)"],
        ["HPE iLO 5 Dedicated Port", "UTP Cat6A (RJ-45)", "OOB Mgmt Switch (VLAN 100)", "Выделенный Out-of-Band канал управления"],
        ["FlexibleLOM / PCIe Port 1 & 2", "SFP+ Direct Attach / Fiber 10G", "TOR-Switch-A & TOR-Switch-B", "Data Traffic (LACP Bonding / 802.3ad)"]
    ]

    for r_idx, r_data in enumerate(rows_data, start=1):
        bg = "F9FAFC" if r_idx % 2 == 0 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            cell = table_cables.cell(r_idx, c_idx)
            cell.text = val
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)

    doc.add_paragraph()

    # ASCII Wiring Diagram Box
    diag_box = doc.add_table(rows=1, cols=1)
    diag_box.alignment = WD_TABLE_ALIGNMENT.CENTER
    d_cell = diag_box.cell(0, 0)
    set_cell_background(d_cell, "1E1E1E")
    set_cell_margins(d_cell, top=120, bottom=120, left=150, right=150)
    dp = d_cell.paragraphs[0]
    dp.paragraph_format.line_spacing = 1.0
    dp.paragraph_format.space_after = Pt(0)

    ascii_art = (
        "┌─────────────────────────────────────────────────────────────────────────┐\n"
        "│              СХЕМА КАБЕЛЬНЫХ ПОДКЛЮЧЕНИЙ HPE DL580 GEN10                │\n"
        "├─────────────────────────────────────────────────────────────────────────┤\n"
        "│                                                                         │\n"
        "│ [PDU-A (Grid A)] <====== (C19) ===== [ PSU 1 ][ PSU 2 ]                 │\n"
        "│ [PDU-B (UPS B) ] <====== (C19) ===== [ PSU 3 ][ PSU 4 ]                 │\n"
        "│                                                                         │\n"
        "│ [OOB Mgmt Switch] <==== (Cat6A) ==== [ iLO 5 Dedicated Mgmt Port ]     │\n"
        "│                                                                         │\n"
        "│ [TOR Switch A] <======= (10G SFP+) == [ FlexibleLOM Port 1 ]            │\n"
        "│                                               || (LACP Bonding / L2)    │\n"
        "│ [TOR Switch B] <======= (10G SFP+) == [ FlexibleLOM Port 2 ]            │\n"
        "└─────────────────────────────────────────────────────────────────────────┘"
    )
    d_run = dp.add_run(ascii_art)
    d_run.font.name = 'Consolas'
    d_run.font.size = Pt(8.5)
    d_run.font.color.rgb = RGBColor(0x00, 0xFF, 0x66) # Matrix green style

    doc.add_paragraph()

    # Section 4: Initial Config
    h4 = doc.add_heading("4. Шаг 3. Порядок первичной настройки сервера", level=1)
    h4.runs[0].font.color.rgb = RGBColor(0x00, 0x56, 0x91)

    doc.add_heading("4.1. Настройка интерфейса управления HPE iLO 5 (Integrated Lights-Out)", level=2)
    p = doc.add_paragraph(
        "1. Первичное подключение: Подключение монитора к VGA-порту и клавиатуры к USB-порту на передней/задней панели сервера "
        "(или через Front iLO Service Port при помощи ноутбука).\n"
        "2. Вход в конфигуратор: При старте сервера нажать ключ F8 для запуска iLO 5 On-Screen Configuration Utility.\n"
        "3. Настройка IPv4/IPv6: Отключить DHCP, задать статический IP-адрес управления (напр., 192.168.100.50/24), Маску подсети, Шлюз и DNS.\n"
        "4. Создание учетной записи Администратора:\n"
        "   - Создать нового локального пользователя `sys_admin` с правами Administrator (Remote Console, Power & Reset, Virtual Media, Config iLO).\n"
        "   - Установить стойкий пароль (не менее 16 символов, содержащий буквы верхнего/нижнего регистра, цифры и спецсимволы).\n"
        "   - Отключить или сменить стандартный дефолтный пароль с фабричного ярлыка (Default Serial Tag).\n"
        "   - Настроить импорт SSH-ключей для беспарольного доступа инженеров по CLI.\n"
        "5. Ввод лицензии: Ввести ключ лицензии iLO Advanced License для разблокировки полного функционала HTML5 Virtual Console, Virtual Media и Power Discovery Services."
    )

    doc.add_heading("4.2. Проверка и настройка BIOS/UEFI System ROM", level=2)
    p = doc.add_paragraph(
        "При загрузке нажать F9 для входа в System Utilities (UEFI Setup):\n"
        "• Режим загрузки (Boot Mode): Установить `UEFI Native Mode` (legacy BIOS отключить).\n"
        "• Рабочие профили (Workload Profiles): Установить `Virtualization - Max Performance` или `General Power Efficient` в зависимости от задач бизнеса.\n"
        "• Безопасность и виртуализация: Включить Intel Virtualization Technology (VT-x), Intel VT for Directed I/O (VT-d), TPM 2.0 Security Chip и режим `Secure Boot Enabled`.\n"
        "• Настройка дискового контроллера (HPE Smart Array P816i-a SR Gen10): "
        "Вход в Smart Storage Administrator (SSA) -> Задать режим RAID 1 (зеркалирование) для двух системных SSD под операционную систему и RAID 10/6 для массива данных."
    )

    doc.add_heading("4.3. Базовое аппаратное тестирование (Hardware Diagnostics)", level=2)
    p = doc.add_paragraph(
        "1. Запуск HPE Intelligent Provisioning (клавиша F10 при загрузке) -> Раздел `Insight Diagnostics`.\n"
        "2. Проведение стресс-тестирования оперативной памяти (Extended RAM Test) для проверки 48 слотов DIMM на отсутствие ошибок 1-bit/2-bit ECC.\n"
        "3. Проверка системы охлаждения: Контроль состояния 6 горячезаменяемых вентиляторов (Hot-plug fans), проверка датчиков температуры Smart Array и CPU.\n"
        "4. Проверка индикаторов статуса БП (Power Supply Status) и тестирование эмуляции сбоя одного из силовых вводов (выдергивание одного из кабелей PDU)."
    )

    # Section 5: Firmware & Drivers
    h5 = doc.add_heading("5. Шаг 4. Обновление микрокода (Firmware) и драйверов", level=1)
    h5.runs[0].font.color.rgb = RGBColor(0x00, 0x56, 0x91)

    doc.add_heading("5.1. Зачем обновлять микрокод (Firmware)", level=2)
    p = doc.add_paragraph(
        "• Устранение критических аппаратных уязвимостей CPU и чипсета (Spectre, Meltdown, Downfall, Microarchitectural Data Sampling).\n"
        "• Исправление микропрограммных ошибок (Bugs/Errata) в контроллерах RAID, сетевых адаптерах и блоках питания.\n"
        "• Повышение стабильности работы системы при высокой нагрузке и обеспечение совместимости с актуальными ОС (Windows Server 2022/2025, RHEL 9, VMware ESXi 8.0)."
    )

    doc.add_heading("5.2. Перечень обновляемых компонентов", level=2)
    p = doc.add_paragraph(
        "1. System ROM / BIOS (главная прошивка сервера).\n"
        "2. HPE iLO 5 Firmware (контроллер управления).\n"
        "3. CPLD (Complex Programmable Logic Device — системная логика материнской платы).\n"
        "4. HPE Smart Array Controller Firmware (прошивка дискового RAID-контроллера).\n"
        "5. Network Adapter Firmware (микрокод сетевых карт LOM и PCIe).\n"
        "6. Power Supply Firmware (прошивка цифровых контроллеров БП)."
    )

    doc.add_heading("5.3. Способы выполнения обновления", level=2)
    p = doc.add_paragraph(
        "• Способ 1 (Онлайн через Web-интерфейс iLO 5): Загрузка готовых бинарных файлов (.bin / .flash) в разделе Firmware & OS Software -> Flash Firmware. Подходит для точечного обновления iLO и System ROM без остановки ОС.\n"
        "• Способ 2 (Автоматический пакетный через HPE SPP & SUM): Использование официального образа HPE Service Pack for ProLiant (SPP) и утилиты Smart Update Manager (SUM). "
        "Образ монтируется через Virtual Media iLO 5 или запускается из Intelligent Provisioning. SUM автоматически сканирует сервер, строит матрицу зависимостей компонентов и выполняет безопасное поэтапное обновление всех прошивок за один цикл."
    )

    doc.add_heading("5.4. Различие понятия Микрокода (Firmware) и Драйвера (Driver)", level=2)

    # Comparison Table
    t_comp = doc.add_table(rows=5, cols=3)
    t_comp.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_comp.autofit = False

    comp_headers = ["Критерий сравнения", "Микрокод (Firmware / Microcode)", "Драйвер (Device Driver)"]
    for idx, text in enumerate(comp_headers):
        cell = t_comp.cell(0, idx)
        cell.text = text
        p = cell.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(cell, "005691")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)

    comp_rows = [
        ["Уровень исполнения", "Аппаратный уровень (записывается в EEPROM/Flash микросхемы самого устройства)", "Программный уровень (исполняется внутри ядра Операционной Системы)"],
        ["Зависимость от ОС", "Абсолютно независим от установленной ОС (работает даже без ОС)", "Строго привязан к конкретной ОС и ее версии (Windows, Linux, ESXi)"],
        ["Основная функция", "Управляет физической логикой работы чипа, инициализацией и регистрами железа", "Транслирует универсальные системные вызовы ОС в команды конкретного железа"],
        ["Пример компонента", "System ROM (BIOS), прошивка контроллера iLO 5, прошивка SSD", "HPE Smart Array RAID Driver for Windows/Linux, 10G NIC Driver"]
    ]

    for r_idx, r_data in enumerate(comp_rows, start=1):
        bg = "F9FAFC" if r_idx % 2 == 0 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            cell = t_comp.cell(r_idx, c_idx)
            cell.text = val
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)

    doc.add_paragraph()

    # Section 6: Safety Rules
    h6 = doc.add_heading("6. Шаг 5. Меры безопасности при установке и эксплуатации", level=1)
    h6.runs[0].font.color.rgb = RGBColor(0x00, 0x56, 0x91)

    doc.add_heading("6.1. Электробезопасность и ESD-защита", level=2)
    p = doc.add_paragraph(
        "• Антистатическая защита: При проведении любых манипуляций внутри шасси инженеры ОБЯЗАНЫ использовать антистатический браслет, "
        "подключенный к контуру заземления стойки. Чувствительные платы (RAM, PCIe cards) переносятся только в антистатических пакетах (ESD Bags).\n"
        "• Заземление стойки: Металлический корпус стойки и сервера должен быть надежно присоединен к шине защитного заземления (PE) здания.\n"
        "• Отключение питания: Любые работы по замене не-Hot-Plug компонентов производятся только после полного обесточивания сервера (отключение всех 4 кабелей питания)."
    )

    doc.add_heading("6.2. Физическая безопасность и охрана труда", level=2)
    p = doc.add_paragraph(
        "• Подъем тяжестей: Шасси HPE DL580 Gen10 имеет массу до 52 кг. Категорически запрещается поднимать и монтировать сервер в одиночку. "
        "Монтаж выполняется минимум двумя инженерами либо с применением сервоподъемника ServerLIFT.\n"
        "• Надежность рельс: Проверяется срабатывание металлических защелок-фиксаторов рельс Easy Install Rails. "
        "Выдвижение сервера на рельсах из стойки разрешено только при выдвинутой противоопрокидывающей ножке шкафа (Anti-tip bar)."
    )

    doc.add_heading("6.3. Информационная и сетевая безопасность", level=2)
    p = doc.add_paragraph(
        "• Смена дефолтных учетных данных: Немедленная смена заводского пароля iLO 5 и отключение учетных записей по умолчанию.\n"
        "• Сетевая изоляция (Out-of-Band VLAN): Интерфейс iLO 5 помещается в изолированный VLAN управления, "
        "доступ к которому ограничен на межсетевом экране (Firewall ACL) только для авторизованных подсетей администраторов.\n"
        "• Безопасность прошивки (Silicon Root of Trust): Включение аппаратного контроля целостности прошивки HPE Silicon Root of Trust. "
        "Если микрокод iLO или BIOS поврежден или подменен, сервер заблокирует загрузку и восстановит проверенную копию из резервного чипа.\n"
        "• Протоколы шифрования: Принудительное включение TLS 1.3 / High Security Mode для веб-интерфейса iLO 5 и отключение устаревших протоколов HTTP/SNMPv1/v2."
    )

    # Conclusion Box
    concl = doc.add_table(rows=1, cols=1)
    concl.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_cell = concl.cell(0, 0)
    set_cell_background(c_cell, "EAF6ED") # Light green
    set_cell_margins(c_cell, top=120, bottom=120, left=180, right=180)
    cp = c_cell.paragraphs[0]
    c_run = cp.add_run("✅ ИТОГОВЫЙ СТАТУС ВВОДА В ЭКСПЛУАТАЦИЮ:\n")
    c_run.font.bold = True
    c_run.font.size = Pt(10)
    c_run.font.color.rgb = RGBColor(0x1E, 0x7E, 0x34)
    
    concl_text = (
        "Сервер HPE ProLiant DL580 Gen10 успешно смонтирован в стойку (юниты U5-U8), подключен к резервированным контурам питания PDU-A/PDU-B "
        "и сетевым коммутаторам TOR-A/TOR-B (LACP Bonding). Выделенный порт iLO 5 сконфигурирован, заведена защищенная учетная запись `sys_admin`, "
        "обновлен пакет прошивок SPP до актуальной версии. Проведены стресс-тесты RAM и дискового массива RAID 1/10. "
        "Оборудование полностью готово к развертыванию гипервизора / Операционной Системы."
    )
    cp.add_run(concl_text).font.size = Pt(9.5)

    doc.save(DOCX_PATH)
    print(f"DOCX report saved to {DOCX_PATH}")


# --- 2. BUILD PDF VIA REPORTLAB ---
def build_pdf():
    pdfmetrics.registerFont(TTFont('Arial', r'C:\Windows\Fonts\arial.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Bold', r'C:\Windows\Fonts\arialbd.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Italic', r'C:\Windows\Fonts\ariali.ttf'))
    pdfmetrics.registerFont(TTFont('Courier', r'C:\Windows\Fonts\couri.ttf'))

    styles = getSampleStyleSheet()
    
    # Custom Palette
    COLOR_PRIMARY = colors.HexColor('#005691')
    COLOR_DARK = colors.HexColor('#111111')
    _COLOR_MUTED = colors.HexColor('#555555')
    COLOR_BG_CALLOUT = colors.HexColor('#EBF3FA')
    COLOR_BG_CODE = colors.HexColor('#1E1E1E')

    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=16,
        leading=20,
        textColor=COLOR_DARK,
        spaceAfter=10
    )

    style_sub = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=9,
        leading=12,
        textColor=COLOR_PRIMARY,
        spaceAfter=4
    )

    style_h1 = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=13,
        leading=16,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    style_h2 = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=10.5,
        leading=14,
        textColor=COLOR_DARK,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    style_body = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Arial',
        fontSize=9.5,
        leading=13.5,
        textColor=COLOR_DARK,
        spaceAfter=6
    )

    style_callout = ParagraphStyle(
        'Callout_Text',
        parent=styles['Normal'],
        fontName='Arial',
        fontSize=9,
        leading=13,
        textColor=COLOR_DARK
    )

    style_ascii = ParagraphStyle(
        'ASCII_Text',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#00FF66')
    )

    story = []

    # Title & Sub
    story.append(Paragraph("РЕШЕНИЕ КЕЙСА № 2 | HARDWARE-ИНЖЕНЕРИЯ И ИТ-ИНФРАСТРУКТУРА", style_sub))
    story.append(Paragraph("Физическая установка и регламент ввода в эксплуатацию сервера HPE ProLiant DL580 Gen10 в серверную стойку", style_title))
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_PRIMARY, spaceBefore=2, spaceAfter=10))

    # Meta Table
    meta_table_data = [
        [Paragraph("<b>Объект установки:</b>", style_body), Paragraph("Сервер HPE ProLiant DL580 Gen10 (4U Chassis)", style_body)],
        [Paragraph("<b>Ответственный инженер:</b>", style_body), Paragraph("Инженер ИТ-инфраструктуры (Жуков М. Д.)", style_body)]
    ]
    t_meta = Table(meta_table_data, colWidths=[140, 370])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F4F7')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D5DD')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E4E7EC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # Section 1
    story.append(Paragraph("1. Вводная часть и сценарий задачи", style_h1))
    story.append(Paragraph(
        "В рамках полученного тикета компании необходимо произвести физический монтаж, подключение питания "
        "и высокоскоростной сетевой инфраструктуры, а также выполнить первичную программно-аппаратную настройку "
        "нового 4-сокетного флагманского сервера HPE ProLiant DL580 Gen10 в серверный шкаф 19\".", style_body
    ))

    # Callout Box
    specs_html = (
        "<b>📋 ТЕХНИЧЕСКИЙ ПРОФИЛЬ ОБЪЕКТА (HPE ProLiant DL580 Gen10):</b><br/>"
        "• <b>Форм-фактор:</b> 4U Rack Mount (Высота: 17.48 см, Ширина: 44.55 см, Глубина: 75.18 см, Вес: до 52 кг).<br/>"
        "• <b>Архитектура:</b> До 4 процессоров Intel Xeon Scalable 1-го/2-го поколения, 48 слотов DIMM (до 6 ТБ RAM DDR4).<br/>"
        "• <b>Питание:</b> До 4 х резервируемых БП HPE Flex Slot мощностью 800W/1600W Platinum/Titanium (Схема N+N / N+1).<br/>"
        "• <b>Чипсет управления:</b> HPE iLO 5 (Integrated Lights-Out) с аппаратным чипом защиты Silicon Root of Trust."
    )
    t_callout = Table([[Paragraph(specs_html, style_callout)]], colWidths=[510])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_CALLOUT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_PRIMARY),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_callout)
    story.append(Spacer(1, 10))

    # Section 2
    story.append(Paragraph("2. Шаг 1. Подготовка к установке оборудования", style_h1))
    story.append(Paragraph("2.1. Проверка комплектности поставки", style_h2))
    story.append(Paragraph(
        "Перед началом физических работ производится распаковка и аудит по упаковочному листу (Packing Slip):<br/>"
        "1. Шасси сервера HPE ProLiant DL580 Gen10 (CPU, RAM, RAID, БП, Fan modules).<br/>"
        "2. Комплект телескопических рельс (HPE Easy Install Rack Rail Kit 4U).<br/>"
        "3. Кабельный органайзер за задней панелью (Cable Management Arm — CMA).<br/>"
        "4. Силовые кабели питания C19-C20 (или C13-C14) — 4 шт.<br/>"
        "5. Сетевые трансиверы SFP+/QSFP+ или патч-корды Cat6A.<br/>"
        "6. Конверт с лицензионным ключом iLO 5 Advanced License и заводским паролем iLO Tag.", style_body
    ))

    story.append(Paragraph("2.2. Подготовка монтажного инструментария", style_h2))
    story.append(Paragraph(
        "• <b>Антистатический браслет (ESD Wrist Strap)</b> с заземляющим проводником — ОБЯЗАТЕЛЬНО.<br/>"
        "• Отвертка крестовая PH2/PH3 и отвертка Torx T15 (стандарт HPE).<br/>"
        "• Серверный подъемник (ServerLIFT) или помощь второго/третьего инженера (вес шасси ~50 кг).<br/>"
        "• Маркировочный принтер (Brady/Brother) и нейлоновые стяжки-липучки (Velcro).", style_body
    ))

    story.append(Paragraph("2.3. Планирование пространства и теплового баланса в стойке", style_h2))
    story.append(Paragraph(
        "• <b>Расчет юнитов (U-место):</b> Сервер занимает 4U. Выбираются нижние юниты (U5–U8) для смещения центра тяжести шкафа вниз.<br/>"
        "• <b>Охлаждение (Airflow):</b> Направление воздушного потока Front-to-Back (холодный коридор спереди, горячий сзади). Устанавливаются заглушки (Blanking panels) в неиспользуемые юниты.<br/>"
        "• <b>Энерговыделение и PDU:</b> Пиковое потребление до 3200 Вт. Нагрузка распределяется между блоками PDU-A (Ввод А) и PDU-B (Ввод Б от ИБП).", style_body
    ))

    # Section 3
    story.append(Paragraph("3. Шаг 2. Кабельные подключения и коммутация", style_h1))
    
    t_cables_data = [
        [Paragraph("<b>Интерфейс сервера</b>", style_callout), Paragraph("<b>Тип кабеля</b>", style_callout), Paragraph("<b>Точка назначения</b>", style_callout), Paragraph("<b>Назначение и Резервирование</b>", style_callout)],
        [Paragraph("PSU 1 & PSU 2", style_body), Paragraph("C19-C20 c фиксатором", style_body), Paragraph("PDU A (Основной)", style_body), Paragraph("Питание контура А (N+N)", style_body)],
        [Paragraph("PSU 3 & PSU 4", style_body), Paragraph("C19-C20 c фиксатором", style_body), Paragraph("PDU B (ИБП Резерв)", style_body), Paragraph("Питание контура Б (N+N)", style_body)],
        [Paragraph("iLO 5 Dedicated Port", style_body), Paragraph("UTP Cat6A (RJ-45)", style_body), Paragraph("OOB Mgmt Switch", style_body), Paragraph("Выделенный Out-of-Band канал", style_body)],
        [Paragraph("FlexibleLOM 1 & 2", style_body), Paragraph("SFP+ Direct Attach 10G", style_body), Paragraph("TOR-Switch-A / TOR-B", style_body), Paragraph("Data Traffic (LACP Bonding)", style_body)],
    ]
    t_cables = Table(t_cables_data, colWidths=[110, 120, 130, 150])
    t_cables.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D5DD')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_cables)
    story.append(Spacer(1, 10))

    # ASCII Diagram
    ascii_html = (
        "┌─────────────────────────────────────────────────────────────────────────┐<br/>"
        "│              СХЕМА КАБЕЛЬНЫХ ПОДКЛЮЧЕНИЙ HPE DL580 GEN10                │<br/>"
        "├─────────────────────────────────────────────────────────────────────────┤<br/>"
        "│                                                                         │<br/>"
        "│ [PDU-A (Grid A)] &lt;====== (C19) ===== [ PSU 1 ][ PSU 2 ]                 │<br/>"
        "│ [PDU-B (UPS B) ] &lt;====== (C19) ===== [ PSU 3 ][ PSU 4 ]                 │<br/>"
        "│                                                                         │<br/>"
        "│ [OOB Mgmt Switch] &lt;==== (Cat6A) ==== [ iLO 5 Dedicated Mgmt Port ]     │<br/>"
        "│                                                                         │<br/>"
        "│ [TOR Switch A] &lt;======= (10G SFP+) == [ FlexibleLOM Port 1 ]            │<br/>"
        "│                                               || (LACP Bonding / L2)    │<br/>"
        "│ [TOR Switch B] &lt;======= (10G SFP+) == [ FlexibleLOM Port 2 ]            │<br/>"
        "└─────────────────────────────────────────────────────────────────────────┘"
    )
    t_ascii = Table([[Paragraph(ascii_html, style_ascii)]], colWidths=[510])
    t_ascii.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_CODE),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#333333')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_ascii)
    story.append(Spacer(1, 10))

    # Section 4
    story.append(Paragraph("4. Шаг 3. Порядок первичной настройки сервера", style_h1))
    story.append(Paragraph("4.1. Настройка интерфейса управления HPE iLO 5", style_h2))
    story.append(Paragraph(
        "1. <b>Вход в утилиту:</b> Подключить консоль (VGA/USB) и при старте сервера нажать клавишу <b>F8</b> (iLO 5 Configuration Utility).<br/>"
        "2. <b>Сеть IPv4:</b> Отключить DHCP, задать статический IP (192.168.100.50/24), шлюз и DNS.<br/>"
        "3. <b>Учетная запись администратора:</b> Создать пользователя <code>sys_admin</code> с правами Administrator, "
        "задать стойкий пароль (16+ символов) и отключить стандартный фабричный пароль с ярлыка.<br/>"
        "4. <b>Лицензирование:</b> Активировать iLO Advanced License для разблокировки HTML5 Virtual Console и Virtual Media.", style_body
    ))

    story.append(Paragraph("4.2. Проверка и настройка BIOS/UEFI System ROM", style_h2))
    story.append(Paragraph(
        "При загрузке нажать <b>F9</b> (System Utilities):<br/>"
        "• <b>Boot Mode:</b> Установить <code>UEFI Native Mode</code>.<br/>"
        "• <b>Workload Profiles:</b> Выбрать <code>Virtualization - Max Performance</code>.<br/>"
        "• <b>Безопасность:</b> Включить Intel VT-x, VT-d, TPM 2.0 Module и <code>Secure Boot Enabled</code>.<br/>"
        "• <b>RAID Контроллер:</b> В HPE Smart Storage Administrator (SSA) сформировать массив <b>RAID 1</b> для ОС и <b>RAID 10/6</b> для данных.", style_body
    ))

    story.append(Paragraph("4.3. Базовое аппаратное тестирование (Diagnostics)", style_h2))
    story.append(Paragraph(
        "Запустить HPE Intelligent Provisioning (F10) -> <code>Insight Diagnostics</code>. Провести стресс-тестирование RAM (48 слотов DIMM), "
        "проверить кулеры охлаждения, статус датчиков температуры и протестировать отключение одного из лучей питания PDU.", style_body
    ))

    # Section 5
    story.append(Paragraph("5. Шаг 4. Обновление микрокода (Firmware) и драйверов", style_h1))
    story.append(Paragraph(
        "<b>Зачем обновлять:</b> Устранение критических уязвимостей CPU (Spectre, Meltdown, Downfall), исправление микропрограммных ошибок в RAID и NIC, поддержка актуальных ОС.<br/>"
        "<b>Компоненты:</b> System ROM (BIOS), iLO 5 Firmware, CPLD, Smart Array Firmware, Network Adapter Firmware, PSU Firmware.<br/>"
        "<b>Способы:</b> Онлайн через Web-интерфейс iLO 5 (Flash Firmware) или пакетно через HPE SPP (Service Pack for ProLiant) и утилиту SUM (Smart Update Manager).", style_body
    ))

    story.append(Paragraph("<b>Сравнение микрокода и драйвера:</b>", style_h2))
    t_comp_data = [
        [Paragraph("<b>Критерий</b>", style_callout), Paragraph("<b>Микрокод (Firmware / Microcode)</b>", style_callout), Paragraph("<b>Драйвер (Device Driver)</b>", style_callout)],
        [Paragraph("Уровень исполнения", style_body), Paragraph("Аппаратный (EEPROM/Flash чипа устройства)", style_body), Paragraph("Программный (внутри ядра ОС)", style_body)],
        [Paragraph("Зависимость от ОС", style_body), Paragraph("Абсолютно независим от ОС", style_body), Paragraph("Строго привязан к ОС и ее версии", style_body)],
        [Paragraph("Функция", style_body), Paragraph("Физическое управление логикой чипа", style_body), Paragraph("Интерфейс между вызовами ОС и железом", style_body)],
    ]
    t_comp = Table(t_comp_data, colWidths=[100, 205, 205])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D5DD')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 10))

    # Section 6
    story.append(Paragraph("6. Шаг 5. Меры безопасности при установке и эксплуатации", style_h1))
    story.append(Paragraph(
        "• <b>Электробезопасность & ESD:</b> Использование заземленного антистатического браслета, обязательное заземление стойки (PE-шина), обесточивание перед обслуживанием.<br/>"
        "• <b>Физическая безопасность:</b> Монтаж тяжелого шасси (52 кг) производить СТРОГО вдвоем или сервоподъемником. Выдвижение на рельсах — только с зафиксированной противоопрокидывающей ножкой стойки.<br/>"
        "• <b>Сетевая & Информационная безопасность:</b> Выделение iLO 5 в изолированный OOB VLAN, немедленная смена фабричного пароля, включение аппаратной защиты <b>HPE Silicon Root of Trust</b>, активация TLS 1.3.", style_body
    ))

    # Conclusion Callout
    concl_html = (
        "<b>✅ ИТОГОВЫЙ СТАТУС ВВОДА В ЭКСПЛУАТАЦИЮ:</b><br/>"
        "Сервер HPE ProLiant DL580 Gen10 успешно смонтирован в стойку (U5-U8), подключен к резервированным контурам питания PDU-A/PDU-B "
        "и сетевым коммутаторам TOR-A/TOR-B (LACP Bonding). Выделенный порт iLO 5 сконфигурирован, заведена защищенная учетная запись <code>sys_admin</code>, "
        "обновлен пакет прошивок SPP. Проведены стресс-тесты RAM и дискового массива RAID 1/10. Оборудование полностью готово к развертыванию гипервизора."
    )
    t_concl = Table([[Paragraph(concl_html, style_callout)]], colWidths=[510])
    t_concl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EAF6ED')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#28A745')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_concl)

    doc_pdf = SimpleDocTemplate(
        PDF_PATH,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    doc_pdf.build(story)
    print(f"PDF report saved to {PDF_PATH}")

if __name__ == "__main__":
    build_docx()
    build_pdf()
