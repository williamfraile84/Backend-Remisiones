import io
import os
import asyncio
from typing import Dict, Any, Optional
from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.drawing.image import Image as OpenpyxlImage
from app.core.config import settings
from app.services.storage.storage_factory import get_storage_provider

DEFAULT_OBSERVACIONES = "Recibido a satisfacción por el responsable designado en el punto de entrega."


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _round_hundred(val: Any) -> float:
    f = _safe_float(val)
    if f <= 0:
        return 0.0
    return round(f / 100.0) * 100.0


def _get_logo_bytes(logo_path: Optional[str]) -> Optional[bytes]:
    """
    Obtiene los bytes crudos del archivo de logo de manera agnóstica
    (desde Storage Provider o disco local en múltiples ubicaciones relativas/absolutas).
    """
    if not logo_path:
        return None

    clean_path = str(logo_path).replace("\\", "/").lstrip("/")

    # 1. Búsqueda exhaustiva en disco local primero para máxima velocidad y fiabilidad
    possible_paths = [
        os.path.normpath(os.path.join(settings.STORAGE_BASE_DIR, clean_path)),
        os.path.normpath(os.path.join(os.path.abspath(settings.STORAGE_BASE_DIR), clean_path)),
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "storage_data", clean_path)),
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage_data", clean_path)),
        os.path.normpath(os.path.join(".", "storage_data", clean_path)),
        os.path.normpath(os.path.join("..", "storage_data", clean_path)),
        clean_path,
        str(logo_path),
    ]
    for p in possible_paths:
        if os.path.isfile(p):
            try:
                with open(p, "rb") as f:
                    return f.read()
            except Exception:
                pass

    # 2. Intentar proveedor de almacenamiento activo (S3 / Supabase / Google Drive)
    try:
        storage = get_storage_provider()
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                exists = pool.submit(asyncio.run, storage.file_exists(clean_path)).result()
                if exists:
                    return pool.submit(asyncio.run, storage.get_file_bytes(clean_path)).result()
        else:
            if loop.run_until_complete(storage.file_exists(clean_path)):
                return loop.run_until_complete(storage.get_file_bytes(clean_path))
    except Exception:
        pass

    return None


def _get_sanitized_png_bytes(logo_path: Optional[str], max_width: int = 240, max_height: int = 120) -> Optional[bytes]:
    """
    Lee la imagen (PNG, JPG, WebP, BMP, etc.), la convierte a PNG estándar en memoria
    y garantiza que no falle en ReportLab ni OpenPyXL.
    """
    raw_bytes = _get_logo_bytes(logo_path)
    if not raw_bytes:
        return None

    try:
        img = PILImage.open(io.BytesIO(raw_bytes))
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        img.thumbnail((max_width, max_height), PILImage.Resampling.LANCZOS)

        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG")
        return out_buf.getvalue()
    except Exception:
        return None


def _find_logo_image(logo_path: Optional[str], target_h: int = 45, max_w: int = 110):
    """Genera un componente de imagen para ReportLab con dimensiones proporcionales."""
    png_bytes = _get_sanitized_png_bytes(logo_path, max_width=max_w * 2, max_height=target_h * 2)
    if not png_bytes:
        return None
    try:
        pil_img = PILImage.open(io.BytesIO(png_bytes))
        w, h = pil_img.size
        ratio = w / h if h > 0 else 1.5
        calculated_w = min(max_w, int(target_h * ratio))
        return RLImage(io.BytesIO(png_bytes), width=calculated_w, height=target_h)
    except Exception:
        return None


def generar_pdf_remision(empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    elements = []
    styles = getSampleStyleSheet()

    # 1. Encabezado con Logo y Título
    logo_elem = _find_logo_image(empresa.logo_path if empresa else None, target_h=46, max_w=100)

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        alignment=1,
        textTransform="uppercase"
    )

    header_data = [
        [logo_elem or "", Paragraph("<b>NOTA DE REMISIÓN</b>", title_style), ""]
    ]
    header_table = Table(header_data, colWidths=[100, 360, 100])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)

    # 2. Metadatos Remisión
    num_remision = payload.get('numero_remision') or '1'
    fecha_ent = payload.get('fecha_entrega') or '___/___/______'
    meta_data = [
        [
            Paragraph(f"<b>Nº PEDIDO:</b> {num_remision}", styles["Normal"]),
            Paragraph(f"<b>FECHA ENTREGA:</b> {fecha_ent}", styles["Normal"])
        ]
    ]
    meta_table = Table(meta_data, colWidths=[280, 280])
    meta_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)

    # 3. Datos Negocio y Cliente
    business_text = f"<b>NOMBRE:</b> {empresa.nombre if empresa else ''} &nbsp;&nbsp;&nbsp;&nbsp; <b>NIT:</b> {empresa.nit if empresa else ''}<br/><b>DIRECCIÓN:</b> {empresa.direccion if empresa else ''}<br/><b>TELÉFONO:</b> {empresa.telefono if empresa else ''} &nbsp;&nbsp;&nbsp;&nbsp; <b>EMAIL:</b> {empresa.email if empresa else ''}"
    client_text = f"<b>NOMBRE DEL CLIENTE:</b> {cliente.razon_social if cliente else ''} &nbsp;&nbsp;&nbsp;&nbsp; <b>NIT:</b> {cliente.nit if cliente else ''}<br/><b>DIRECCIÓN:</b> {cliente.direccion if cliente else 'N/A'}<br/><b>TELÉFONO:</b> {cliente.telefono if cliente else 'N/A'} &nbsp;&nbsp;&nbsp;&nbsp; <b>EMAIL:</b> {cliente.email if cliente else 'N/A'}"

    info_data = [
        [Paragraph("<b>DATOS DEL NEGOCIO (EMISOR)</b>", ParagraphStyle('H1', alignment=1, fontSize=8, fontName='Helvetica-Bold'))],
        [Paragraph(business_text, ParagraphStyle('B1', fontSize=8, leading=10))],
        [Paragraph("<b>DATOS DEL CLIENTE (RECEPTOR)</b>", ParagraphStyle('H2', alignment=1, fontSize=8, fontName='Helvetica-Bold'))],
        [Paragraph(client_text, ParagraphStyle('B2', fontSize=8, leading=10))]
    ]
    info_table = Table(info_data, colWidths=[560])
    info_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#F1F5F9")),
        ('BACKGROUND', (0, 2), (0, 2), colors.HexColor("#F1F5F9")),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(info_table)

    # 4. Tabla de 4 Columnas: PRODUCTO (50%), CANTIDAD (13%), UNIDAD (11%), DESCRIPCIÓN (26%)
    col_widths = [280, 72.8, 61.6, 145.6]
    items_data = [
        ["PRODUCTO", "CANTIDAD", "UNIDAD", "DESCRIPCIÓN"]
    ]
    for p in (payload.get("productos") or []):
        items_data.append([
            Paragraph(str(p.get("producto", "") or "").upper(), ParagraphStyle('P1', fontSize=8, fontName='Helvetica-Bold')),
            str(p.get("cantidad", "") if p.get("cantidad") is not None else ""),
            str(p.get("unidad", "Kg") or "Kg"),
            Paragraph(str(p.get("descripcion", "") or ""), ParagraphStyle('P2', fontSize=7.5, leading=9))
        ])

    items_table = Table(items_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('ALIGN', (1, 0), (2, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(items_table)

    # 5. Sección Inferior: Observaciones / Firma (74%) y Nº CANASTAS (26%)
    raw_obs = (payload.get('observaciones') or '').strip()
    obs = raw_obs if raw_obs else DEFAULT_OBSERVACIONES
    canastas = payload.get('numero_canastas') or '_____'

    obs_text = (
        f"<b>OBSERVACIONES / TÉRMINOS DE ENTREGA:</b><br/>"
        f"{obs}<br/><br/><br/><br/>"
        f"_______________________________________<br/>"
        f"Firma / Sello Responsable &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; C.C."
    )
    bottom_data = [
        [
            Paragraph(obs_text, ParagraphStyle('Obs', fontSize=7.5, leading=10)),
            Paragraph(f"<br/><b>Nº CANASTILLAS:</b><br/><br/><font size=16><b>{canastas}</b></font>", ParagraphStyle('Can', alignment=1, fontSize=8))
        ]
    ]
    bottom_table = Table(bottom_data, colWidths=[414.4, 145.6])
    bottom_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(bottom_table)

    doc.build(elements)
    return buffer.getvalue()


def generar_excel_remision(empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nota de Remision"
    ws.views.sheetView[0].showGridLines = True

    border_thin = Side(border_style="thin", color="000000")
    box_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

    # Inserción de Logo en Excel
    png_bytes = _get_sanitized_png_bytes(empresa.logo_path if empresa else None, max_width=200, max_height=80)
    has_logo = False
    if png_bytes:
        try:
            img_buf = io.BytesIO(png_bytes)
            xl_img = OpenpyxlImage(img_buf)
            pil_img = PILImage.open(io.BytesIO(png_bytes))
            w, h = pil_img.size
            ratio = w / h if h > 0 else 1.5
            xl_img.height = 45
            xl_img.width = int(45 * ratio)
            ws.add_image(xl_img, "A1")
            has_logo = True
        except Exception:
            has_logo = False

    # Fila 1: Título y Encabezado
    ws.merge_cells("A1:D1")
    ws["A1"] = f"          {empresa.nombre if empresa else 'EMPRESA'} - NOTA DE REMISIÓN" if has_logo else f"{empresa.nombre if empresa else 'EMPRESA'} - NOTA DE REMISIÓN"
    ws["A1"].font = Font(size=13, bold=True, color="FFFFFF")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A1"].fill = PatternFill("solid", fgColor="1E293B")
    ws.row_dimensions[1].height = 42

    # Fila 2: Metadatos
    ws["A2"] = f"Remisión #: {payload.get('numero_remision') or '1'}"
    ws["B2"] = f"OC: {payload.get('numero_oc') or 'S/N'}"
    ws["C2"] = f"Fecha: {payload.get('fecha_entrega') or ''}"
    ws["D2"] = f"Canastillas: {payload.get('numero_canastas') or ''}"
    for col in ["A", "B", "C", "D"]:
        ws[f"{col}2"].font = Font(bold=True)
        ws[f"{col}2"].border = box_border
        ws[f"{col}2"].fill = PatternFill("solid", fgColor="F8FAFC")
    ws.row_dimensions[2].height = 22

    # Fila 3: Cliente
    ws.merge_cells("A3:D3")
    ws["A3"] = f"Cliente: {cliente.razon_social if cliente else ''} | NIT: {cliente.nit if cliente else ''} | Dir: {cliente.direccion if cliente else ''} | Tel: {cliente.telefono if cliente else ''}"
    ws["A3"].font = Font(size=10, italic=True)
    ws["A3"].border = box_border
    ws["A3"].fill = PatternFill("solid", fgColor="F1F5F9")
    ws.row_dimensions[3].height = 20

    # Fila 4: Encabezados de productos
    headers = ["PRODUCTO", "CANTIDAD", "UNIDAD", "DESCRIPCIÓN"]
    ws.append(headers)
    for col_idx in range(1, 5):
        cell = ws.cell(row=4, column=col_idx)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="334155")
        cell.alignment = Alignment(horizontal="center")
        cell.border = box_border
    ws.row_dimensions[4].height = 22

    # Filas de productos
    for p in (payload.get("productos") or []):
        ws.append([
            str(p.get("producto", "") or "").upper(),
            p.get("cantidad", 0) if p.get("cantidad") is not None else 0,
            p.get("unidad", "Kg") or "Kg",
            p.get("descripcion", "") or ""
        ])
        curr_row = ws.max_row
        for c in range(1, 5):
            cell = ws.cell(row=curr_row, column=c)
            cell.border = box_border
            if c in (2, 3):
                cell.alignment = Alignment(horizontal="center")

    # Sección Inferior: Observaciones y Firma
    raw_obs = (payload.get('observaciones') or '').strip()
    obs = raw_obs if raw_obs else DEFAULT_OBSERVACIONES
    canastas = payload.get('numero_canastas') or '_____'

    start_obs_row = ws.max_row + 1
    end_obs_row = start_obs_row + 3

    # Bloque Observaciones A:C
    ws.merge_cells(start_row=start_obs_row, start_column=1, end_row=end_obs_row, end_column=3)
    obs_cell = ws.cell(row=start_obs_row, column=1)
    obs_cell.value = (
        f"OBSERVACIONES / TÉRMINOS DE ENTREGA:\n"
        f"{obs}\n\n"
        f"_______________________________________\n"
        f"Firma / Sello Responsable                C.C."
    )
    obs_cell.font = Font(size=9)
    obs_cell.alignment = Alignment(vertical="top", wrap_text=True)

    # Bloque Canastas D
    ws.merge_cells(start_row=start_obs_row, start_column=4, end_row=end_obs_row, end_column=4)
    can_cell = ws.cell(row=start_obs_row, column=4)
    can_cell.value = f"Nº CANASTILLAS:\n\n{canastas}"
    can_cell.font = Font(size=12, bold=True)
    can_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    can_cell.fill = PatternFill("solid", fgColor="F8FAFC")

    for r in range(start_obs_row, end_obs_row + 1):
        for c in range(1, 5):
            ws.cell(row=r, column=c).border = box_border

    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 30

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def generar_pdf_informe(empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()

    logo_elem = _find_logo_image(empresa.logo_path if empresa else None, target_h=40, max_w=90)
    title_style = ParagraphStyle("RepTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, alignment=1)

    header_data = [
        [logo_elem or "", Paragraph("<b>INFORME FINANCIERO DE LIQUIDACIÓN Y COSTEO</b>", title_style), ""]
    ]
    header_table = Table(header_data, colWidths=[90, 380, 90])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6))

    meta_text = f"<b>Cliente:</b> {cliente.razon_social if cliente else 'N/A'} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Remisión #:</b> {payload.get('numero_remision') or '1'} &nbsp;&nbsp;|&nbsp;&nbsp; <b>OC:</b> {payload.get('numero_oc') or 'S/N'} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Fecha:</b> {payload.get('fecha_entrega') or 'N/A'}"
    elements.append(Paragraph(meta_text, ParagraphStyle("Meta", fontSize=9, alignment=1)))
    elements.append(Spacer(1, 10))

    # Tabla de Liquidación
    headers = ["#", "Producto", "Cant/Kg", "Total Compra", "Costo Real/Kg", "% Util", "P. Venta/Kg", "Total Venta"]
    table_data = [headers]

    prods = payload.get("productos") or []
    for idx, p in enumerate(prods, start=1):
        cant = p.get('kilos') if p.get('kilos') is not None else p.get('cantidad', 0)
        table_data.append([
            str(idx),
            str(p.get("producto", "") or "").upper()[:22],
            f"{cant} {p.get('unidad', 'Kg') or 'Kg'}",
            f"${_round_hundred(p.get('valor_compra_total')):,.0f}",
            f"${_round_hundred(p.get('costo_real_kilo')):,.0f}",
            f"{p.get('porcentaje_utilidad') if p.get('porcentaje_utilidad') is not None else 30}%",
            f"${_round_hundred(p.get('precio_venta_kilo')):,.0f}",
            f"${_round_hundred(p.get('valor_total_venta')):,.0f}",
        ])

    items_table = Table(table_data, colWidths=[20, 140, 55, 65, 70, 45, 65, 80])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 14))

    # Resumen Financiero
    resumen = (payload.get("liquidacion") or {}).get("resumen") or {}
    total_kilos = resumen.get('total_kilos') or 0
    total_compras = resumen.get('total_compras') or 0
    total_gastos = resumen.get('total_gastos') or 0
    total_ventas = resumen.get('total_ventas') or 0
    ganancia = resumen.get('ganancia') or 0
    margen_global = resumen.get('margen_global_porcentaje') or 0

    summary_data = [
        ["Kilos Totales", "Total Compras", "Total Gastos", "Total Ventas", "Utilidad Neta", "Margen Global"],
        [
            f"{_safe_float(total_kilos):,.2f} Kg" if _safe_float(total_kilos) % 1 != 0 else f"{int(_safe_float(total_kilos))} Kg",
            f"${_round_hundred(total_compras):,.0f}",
            f"${_round_hundred(total_gastos):,.0f}",
            f"${_round_hundred(total_ventas):,.0f}",
            f"${_round_hundred(ganancia):,.0f}",
            f"{_safe_float(margen_global):,.1f}%",
        ]
    ]
    summary_table = Table(summary_data, colWidths=[90, 95, 90, 95, 100, 90])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#94A3B8")),
        ('TEXTCOLOR', (4, 1), (4, 1), colors.HexColor("#047857")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)

    doc.build(elements)
    return buffer.getvalue()


def generar_excel_informe(empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Informe Liquidacion"
    ws.views.sheetView[0].showGridLines = True

    border_thin = Side(border_style="thin", color="CBD5E1")
    box_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

    # Logo opcional en informe financiero
    png_bytes = _get_sanitized_png_bytes(empresa.logo_path if empresa else None, max_width=180, max_height=60)
    if png_bytes:
        try:
            img_buf = io.BytesIO(png_bytes)
            xl_img = OpenpyxlImage(img_buf)
            pil_img = PILImage.open(io.BytesIO(png_bytes))
            w, h = pil_img.size
            ratio = w / h if h > 0 else 1.5
            xl_img.height = 36
            xl_img.width = int(36 * ratio)
            ws.add_image(xl_img, "A1")
        except Exception:
            pass

    ws.merge_cells("A1:H1")
    ws["A1"] = "INFORME FINANCIERO DE LIQUIDACIÓN Y COSTEO"
    ws["A1"].font = Font(size=14, bold=True, color="FFFFFF")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A1"].fill = PatternFill("solid", fgColor="0F172A")
    ws.row_dimensions[1].height = 36

    headers = ["#", "Producto", "Kilos", "Total Compra", "Costo Real/Kg", "% Util", "P. Venta/Kg", "Total Venta"]
    ws.append(headers)
    for c_idx in range(1, 9):
        cell = ws.cell(row=2, column=c_idx)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E293B")
        cell.alignment = Alignment(horizontal="center")
        cell.border = box_border

    for idx, p in enumerate((payload.get("productos") or []), start=1):
        cant = p.get("kilos") if p.get("kilos") is not None else p.get("cantidad", 0)
        ws.append([
            idx,
            str(p.get("producto", "") or "").upper(),
            _safe_float(cant),
            _round_hundred(p.get("valor_compra_total")),
            _round_hundred(p.get("costo_real_kilo")),
            _safe_float(p.get("porcentaje_utilidad"), 30.0),
            _round_hundred(p.get("precio_venta_kilo")),
            _round_hundred(p.get("valor_total_venta")),
        ])
        for c in range(1, 9):
            ws.cell(row=ws.max_row, column=c).border = box_border

    # Resumen
    res = (payload.get("liquidacion") or {}).get("resumen") or {}
    ws.append([])
    ws.append(["RESUMEN FINANCIERO"])
    ws.append(["Kilos Totales", _safe_float(res.get("total_kilos"))])
    ws.append(["Total Compras", _round_hundred(res.get("total_compras"))])
    ws.append(["Total Gastos", _round_hundred(res.get("total_gastos"))])
    ws.append(["Total Ventas", _round_hundred(res.get("total_ventas"))])
    ws.append(["Utilidad Neta", _round_hundred(res.get("ganancia"))])
    ws.append(["Margen Global %", f"{_safe_float(res.get('margen_global_porcentaje'))}%"])

    for col in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        ws.column_dimensions[col].width = 18

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ==============================================================================
# STRATEGY PATTERN (GoF) PARA EXPORTACIÓN DE DOCUMENTOS
# ==============================================================================
from abc import ABC, abstractmethod


class ExportStrategy(ABC):
    """
    Estrategia abstracta para generación y exportación de documentos comerciales
    (PDF Remisiones, Excel Remisiones, PDF Informes Financieros, Excel Informes).
    Cumple con el Principio Abierto/Cerrado (Open-Closed Principle de SOLID).
    """

    @abstractmethod
    def export(self, empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
        pass

    @property
    @abstractmethod
    def media_type(self) -> str:
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        pass


class PdfRemisionStrategy(ExportStrategy):
    def export(self, empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
        return generar_pdf_remision(empresa, cliente, payload)

    @property
    def media_type(self) -> str:
        return "application/pdf"

    @property
    def file_extension(self) -> str:
        return "pdf"


class ExcelRemisionStrategy(ExportStrategy):
    def export(self, empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
        return generar_excel_remision(empresa, cliente, payload)

    @property
    def media_type(self) -> str:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @property
    def file_extension(self) -> str:
        return "xlsx"


class PdfInformeStrategy(ExportStrategy):
    def export(self, empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
        return generar_pdf_informe(empresa, cliente, payload)

    @property
    def media_type(self) -> str:
        return "application/pdf"

    @property
    def file_extension(self) -> str:
        return "pdf"


class ExcelInformeStrategy(ExportStrategy):
    def export(self, empresa: Any, cliente: Any, payload: Dict[str, Any]) -> bytes:
        return generar_excel_informe(empresa, cliente, payload)

    @property
    def media_type(self) -> str:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @property
    def file_extension(self) -> str:
        return "xlsx"


class ExportContext:
    """
    Contexto de despacho para el patrón Strategy.
    Permite obtener y ejecutar dinámicamente la estrategia requerida.
    """
    _strategies: Dict[str, ExportStrategy] = {
        "pdf-remision": PdfRemisionStrategy(),
        "excel-remision": ExcelRemisionStrategy(),
        "pdf-informe": PdfInformeStrategy(),
        "excel-informe": ExcelInformeStrategy(),
    }

    @classmethod
    def get_strategy(cls, export_type: str) -> ExportStrategy:
        clean_type = str(export_type).lower().strip()
        strategy = cls._strategies.get(clean_type)
        if not strategy:
            raise ValueError(f"Estrategia de exportación no soportada: {export_type}")
        return strategy

    @classmethod
    def register_strategy(cls, export_type: str, strategy: ExportStrategy):
        cls._strategies[export_type.lower().strip()] = strategy