import io
import os
import re
import json
import base64
import logging
import asyncio
import datetime
from typing import Dict, Any, List, Tuple, Optional
import httpx
import pdfplumber
import numpy as np
from PIL import Image, ImageOps
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from app.core.config import settings

logger = logging.getLogger("DocumentParser")

def warmup_ocr_engine():
    """No-op: los motores locales OCR han sido descontinuados en favor de Gemini Vision multimodal y lectura documental nativa."""
    pass


def optimize_image_for_vision(file_bytes: bytes, max_dim: Optional[int] = None, quality: int = 85) -> bytes:
    """
    Normaliza y reescala imágenes para envío eficiente al motor multimodal Gemini Vision:
    - Normaliza orientación EXIF.
    - Convierte a RGB.
    - Escala proporcionalmente si excede max_dim (configurable vía VISION_MAX_IMAGE_DIMENSION, por defecto 1600px).
    - Comprime a JPEG optimizado en memoria.
    """
    if max_dim is None:
        max_dim = getattr(settings, "VISION_MAX_IMAGE_DIMENSION", 1600)

    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        max_side = max(w, h)
        if max_side > max_dim:
            scale = max_dim / float(max_side)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            resample_filter = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize((new_w, new_h), resample=resample_filter)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Error al optimizar imagen para visión multimodal: {e}")
        return file_bytes


def render_pdf_pages_to_images(file_bytes: bytes, max_pages: int = 5, dpi: Optional[int] = None) -> List[bytes]:
    """
    Renderiza páginas de un PDF escaneado a imágenes JPEG en memoria para su análisis con Gemini Vision.
    Usa pypdfium2 o pdfplumber sin requerir dependencias de sistema externas (poppler o tesseract).
    """
    if dpi is None:
        dpi = getattr(settings, "VISION_PDF_DPI", 150)

    images: List[bytes] = []

    # 1. Intentar renderizado con pypdfium2 (rápido y nativo en Python)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(file_bytes)
        total_pages = min(len(pdf), max_pages)
        for i in range(total_pages):
            page = pdf[i]
            pil_img = page.render(scale=dpi / 72.0).to_pil()
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=85, optimize=True)
            images.append(buf.getvalue())
        if images:
            return images
    except Exception as e_pdfium:
        logger.debug(f"Renderizado con pypdfium2 omitido ({e_pdfium}), intentando con pdfplumber...")

    # 2. Fallback a pdfplumber.to_image
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:max_pages]:
                page_img = page.to_image(resolution=dpi).original
                if page_img.mode != "RGB":
                    page_img = page_img.convert("RGB")
                buf = io.BytesIO()
                page_img.save(buf, format="JPEG", quality=85, optimize=True)
                images.append(buf.getvalue())
        if images:
            return images
    except Exception as e_plumber:
        logger.warning(f"Error al renderizar páginas de PDF a imágenes: {e_plumber}")

    return images


# Diccionario léxico de unidades de medida estándar y universales
KNOWN_UNIT_TOKENS = {
    # Peso / Masa
    "KG": "Kg", "KILOS": "Kg", "KILO": "Kg", "KQ": "Kg", "KGS": "Kg",
    "GR": "Gr", "GRAMOS": "Gr", "GRAMO": "Gr", "G": "Gr", "GRS": "Gr",
    "LIBRA": "Libra", "LIBRAS": "Libra", "LB": "Libra", "LBS": "Libra",
    "TONELADA": "Ton", "TONELADAS": "Ton", "TON": "Ton", "TN": "Ton",
    "ONZA": "Oz", "ONZAS": "Oz", "OZ": "Oz",
    # Volumen / Capacidad
    "LITRO": "Litro", "LITROS": "Litro", "LT": "Litro", "LTS": "Litro", "L": "Litro",
    "GALON": "Galon", "GALONES": "Galon", "GL": "Galon", "GLS": "Galon",
    "ML": "Ml", "MILILITROS": "Ml", "CC": "Ml",
    # Unidades y Cantidades
    "UND": "Und", "UNIDAD": "Und", "UNIDADES": "Und", "UN": "Und", "U": "Und",
    "PZ": "Und", "PZA": "Und", "PIEZA": "Und", "PIEZAS": "Und",
    "DOCENA": "Docena", "DOCENAS": "Docena", "DOC": "Docena",
    "PAR": "Par", "PARES": "Par",
    # Empaques y Presentaciones
    "PAQUETE": "Paquete", "PAQUETES": "Paquete", "PQ": "Paquete", "PAQ": "Paquete", "PKT": "Paquete",
    "CAJA": "Caja", "CAJAS": "Caja", "CJ": "Caja", "CJS": "Caja",
    "BOLSA": "Bolsa", "BOLSAS": "Bolsa", "BLS": "Bolsa",
    "BOTELLA": "Botella", "BOTELLAS": "Botella", "BOT": "Botella",
    "LATA": "Lata", "LATAS": "Lata",
    "FRASCO": "Frasco", "FRASCOS": "Frasco", "FCO": "Frasco",
    "CANASTILLA": "Canastilla", "CANASTILLAS": "Canastilla", "CANASTA": "Canastilla", "CANASTAS": "Canastilla", "CNA": "Canastilla",
    "CUBETA": "Cubeta", "CUBETAS": "Cubeta", "CUBETASA": "Cubeta", "CUBETA A": "Cubeta", "CUBETAS A": "Cubeta",
    "BLOQUE": "Bloque", "BLOQUES": "Bloque",
    "BULTO": "Bulto", "BULTOS": "Bulto", "SACO": "Bulto", "SACOS": "Bulto",
    "ROLLO": "Rollo", "ROLLOS": "Rollo",
    "ATADO": "Atado", "ATADOS": "Atado",
    "MANOJO": "Manojo", "MANOJOS": "Manojo",
    "PORCION": "Porcion", "PORCIONES": "Porcion",
    "BANDEJA": "Bandeja", "BANDEJAS": "Bandeja",
    "KIT": "Kit", "KITS": "Kit",
    "TAMBOR": "Tambor", "TAMBORES": "Tambor",
    # Longitud y Área
    "METRO": "Metro", "METROS": "Metro", "M": "Metro", "MTS": "Metro",
    "CM": "Cm", "CENTIMETROS": "Cm",
    "M2": "M2", "MT2": "M2",
}

# Expresiones regulares precompiladas para extracción de metadatos genéricos
RE_NON_NUMERIC = re.compile(r"[^\d,\.]")
RE_SPACES = re.compile(r"\s+")
RE_TRAILING_METADATA = re.compile(
    r"\b(NOMBRE|CEDULA|C[EÉ]DULA|CELULAR|NIT|RUT|RUC|EMAIL|CORREO|TELEFONO|TEL[EÉ]FONO|DIRECCION|DIRECCI[OÓ]N|CENTRO\s*COSTO|FECHA|DATOS|EMPRESA|PROVEEDOR|CLIENTE)\b.*$",
    re.IGNORECASE
)
RE_TRAILING_PUNCT = re.compile(r"[\s\|\:\-]+$")
RE_RAZON_SOCIAL = re.compile(
    r"(?:RAZ[OÓ]N\s*SOCIAL|CLIENTE|SE[ÑN]ORES|COMPRADOR|ADQUIRIENTE|CONSIGNATARIO|RECEPTOR|NOMBRE\s*(?:DEL\s*)?CLIENTE|FACTURAR\s*A\s*[:\|])[:\s\|]*([^\n\r\|]+)",
    re.IGNORECASE
)
RE_NIT = re.compile(
    r"(?:NIT|INIT|IDENTIFICACI[OÓ]N|RUT|RUC|C\.?C\.?|DOCUMENTO)[:\s\|]*([\d\.\-]+)",
    re.IGNORECASE
)
RE_EMAIL = re.compile(
    r"(?:EMAIL|CORREO|E-MAIL)[:\s\|]*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
    re.IGNORECASE
)
RE_OC = re.compile(
    r"(?:N[UÚ]MERO\s*(?:DE\s*)?(?:OC|ORDEN|PEDIDO)|(?:ORDEN\s*(?:DE\s*COMPRA)?|OC|PEDIDO|ORDEN)\s*(?:N[UÚ]MERO|NO\.?|#|N°|:)|N°\s*(?:OC|ORDEN|PEDIDO))[:\s#\|]+([A-Za-z0-9\-]+)",
    re.IGNORECASE
)
RE_OC_FALLBACK = re.compile(
    r"(?:ORDEN\s*DE\s*COMPRA|NRO\.?\s*PEDIDO|O\.C\.)\s*(?:N[UÚ]MERO|NO\.?|#|N°|:)[:\s#\|]+([A-Za-z0-9\-]+)",
    re.IGNORECASE
)
RE_DATE_PATTERN = r"(?:\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}|\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"
RE_ENTREGA_BLOCK = re.compile(
    rf"(?:DATOS\s*DE\s*ENTREGA|FECHA\s*(?:DE\s*)?ENTREGA|ENTREGA)[\s\S]*?FECHA[:\s\|]*({RE_DATE_PATTERN})",
    re.IGNORECASE
)
RE_EMISION_BLOCK = re.compile(
    rf"(?:FECHA\s*(?:DE\s*)?EMISI[OÓ]N|FECHA\s*(?:DE\s*)?EXPEDICI[OÓ]N|FECHA\s*(?:DEL\s*)?PEDIDO|FECHA)[:\s\|]*({RE_DATE_PATTERN})",
    re.IGNORECASE
)
RE_OBSERVACIONES = re.compile(r"OBSERVACIONES:?[\s\|]*([\s\S]+?)(?:$|\n\s*\n\s*\n)", re.IGNORECASE)
RE_PRICE_OR_BIG_NUM = re.compile(r"^\d{4,}")


def clean_text(text: str) -> str:
    """Limpia caracteres extraños y normaliza símbolos comunes de OCR."""
    if not text:
        return ""
    t = str(text)
    t = t.replace("Κα", "Kg").replace("Kα", "Kg").replace("κα", "kg").replace("kα", "kg")
    return t.strip()


def clean_razon_social(text: str) -> str:
    """Limpia y normaliza el nombre o razón social del cliente removiendo metadatos agregados por OCR."""
    if not text:
        return ""
    t = clean_text(text)
    t = RE_TRAILING_METADATA.sub("", t)
    t = RE_TRAILING_PUNCT.sub("", t)
    return RE_SPACES.sub(" ", t).strip()


def normalize_product_name(name: str) -> str:
    """Normaliza nombres de productos/ítems eliminando ruido de OCR, prefijos numéricos y metadatos."""
    if not name:
        return ""
    cleaned = clean_text(name).upper()
    cleaned = RE_TRAILING_METADATA.sub("", cleaned)
    cleaned = RE_TRAILING_PUNCT.sub("", cleaned)

    # Limpiar numeración inicial de fila como "1.", "01 -", "#1 ", "1) "
    cleaned = re.sub(r"^[#\d]+[\.\-\)\/\s]+", "", cleaned)

    # Limpiar caracteres de puntuación residual
    cleaned = cleaned.strip(" .-:,_#|*")
    return RE_SPACES.sub(" ", cleaned).strip()


def normalize_unit_and_description(raw_unit: str, raw_desc: str) -> Tuple[str, str]:
    """Separa y normaliza unidad y descripción de forma universal y desacoplada."""
    u = clean_text(raw_unit).strip()
    d = clean_text(raw_desc).strip()
    u_upper = u.upper()
    d_upper = d.upper()

    if not u_upper and d_upper:
        if d_upper in KNOWN_UNIT_TOKENS:
            u_upper = d_upper
            d = ""
            d_upper = ""
        else:
            first_word = d_upper.split()[0] if d_upper.split() else ""
            if first_word in KNOWN_UNIT_TOKENS:
                u_upper = first_word
                d = d[len(first_word):].strip(" -:,")
                d_upper = d.upper()

    final_unit = "Kg"
    if u_upper in KNOWN_UNIT_TOKENS:
        final_unit = KNOWN_UNIT_TOKENS[u_upper]
    elif u_upper:
        for token, norm in KNOWN_UNIT_TOKENS.items():
            if token == u_upper or token in u_upper.split():
                final_unit = norm
                break
        else:
            # Si es una unidad personalizada no estándar, preservarla en formato limpio
            cleaned_custom = re.sub(r"[^\w\s]", "", u).strip().capitalize()
            if cleaned_custom and len(cleaned_custom) <= 20:
                final_unit = cleaned_custom

    if d_upper in KNOWN_UNIT_TOKENS or d_upper == u_upper or d_upper == final_unit.upper():
        d = ""

    return final_unit, d


def parse_numeric(val: Any) -> float:
    """Convierte texto a float de forma robusta manejando comas/puntos decimales."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = RE_NON_NUMERIC.sub("", s)
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def extract_metadata_from_text(text: str) -> Dict[str, Any]:
    """Extrae metadatos estructurados (cliente, NIT, OC, fechas, observaciones) de texto completo."""
    metadata = {
        "numero_oc": "",
        "fecha_emision": "",
        "fecha_entrega": "",
        "observaciones": "",
        "cliente": {
            "razon_social": "",
            "nit": "",
            "email": "",
        }
    }
    if not text:
        return metadata

    # 1. Razón Social
    m_rs = RE_RAZON_SOCIAL.search(text)
    if m_rs:
        metadata["cliente"]["razon_social"] = clean_razon_social(m_rs.group(1))

    # 2. NIT
    m_nit = RE_NIT.search(text)
    if m_nit:
        raw_nit = m_nit.group(1).strip()
        metadata["cliente"]["nit"] = raw_nit.replace(".", "")

    # 3. Email
    m_email = RE_EMAIL.search(text)
    if m_email:
        metadata["cliente"]["email"] = m_email.group(1).strip()

    # 4. Número de Orden de Compra (OC)
    m_oc = RE_OC.search(text)
    if m_oc:
        metadata["numero_oc"] = m_oc.group(1).strip()
    else:
        m_oc_fb = RE_OC_FALLBACK.search(text)
        if m_oc_fb:
            metadata["numero_oc"] = m_oc_fb.group(1).strip()

    # 5. Fechas
    m_ent = RE_ENTREGA_BLOCK.search(text)
    if m_ent:
        metadata["fecha_entrega"] = m_ent.group(1).strip()

    m_em = RE_EMISION_BLOCK.search(text)
    if m_em:
        metadata["fecha_emision"] = m_em.group(1).strip()

    # 6. Observaciones (se mantienen limpias por defecto para no heredar términos de compra del cliente)
    metadata["observaciones"] = ""

    return metadata


def is_header_or_footer(text: str) -> bool:
    """Detecta si una fila o texto corresponde a encabezados de tabla o pie de página."""
    if not text:
        return True
    t = text.upper().strip()
    keywords = [
        "ITEM", "PRODUCTO", "DESCRIPCION", "DESCRIPCIÓN", "CANTIDAD", "UNIDAD", "SUBTOTAL",
        "TOTAL", "VALOR UNITARIO", "PRECIO", "VALOR TOTAL", "FECHA",
        "OBSERVACIONES", "AUTORIZADO", "FIRMA", "PAGINA", "ORDEN DE COMPRA",
        "NÚMERO DE OC", "NUMERO DE OC", "DATOS PROVEEDOR", "DATOS DE ENTREGA",
        "FACTURAR A", "RAZÓN SOCIAL", "RAZON SOCIAL", "CENTRO COSTO"
    ]
    matches = sum(1 for kw in keywords if kw in t)
    return matches >= 2 or t in keywords or t in ["ITEM", "PRODUCTO", "TOTAL", "SUBTOTAL", "NÚMERO DE OC", "NUMERO DE OC"]


def extract_products_from_pdf_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
    """Extrae y normaliza productos a partir de tablas nativas de PDF."""
    products = []
    if not tables:
        return products

    for table in tables:
        if not table:
            continue
        header_idx = -1
        col_map = {"producto": -1, "cantidad": -1, "unidad": -1, "descripcion": -1}

        for r_idx, row in enumerate(table):
            row_cells_upper = [clean_text(str(c or "")).upper() for c in row]
            has_prod = any("PRODUCTO" in c or "ARTICULO" in c for c in row_cells_upper)
            has_cant = any("CANT" in c or "KILOS" in c or "CANTIDAD" in c for c in row_cells_upper)
            has_desc = any("DESCRIP" in c or "DETALLE" in c for c in row_cells_upper)
            has_item = any(c == "ITEM" or c == "#" for c in row_cells_upper)

            if has_prod or (has_cant and (has_desc or has_item)):
                header_idx = r_idx
                # Pase 1: Priorizar columna explícita PRODUCTO / ARTICULO
                for c_idx, cell_text in enumerate(row_cells_upper):
                    if "PRODUCTO" in cell_text or "ARTICULO" in cell_text:
                        col_map["producto"] = c_idx
                    elif "CANT" in cell_text or "KILOS" in cell_text or "CANTIDAD" in cell_text:
                        col_map["cantidad"] = c_idx
                    elif "UNID" in cell_text or "U.M" in cell_text or "MEDIDA" in cell_text:
                        col_map["unidad"] = c_idx

                # Pase 2: Buscar DESCRIPCION / DETALLE (solo si producto no fue asignado aún)
                for c_idx, cell_text in enumerate(row_cells_upper):
                    if "DESCRIP" in cell_text or "DETALLE" in cell_text or "ESPECIFIC" in cell_text:
                        if col_map["producto"] == -1:
                            col_map["producto"] = c_idx
                        elif col_map["descripcion"] == -1 and c_idx != col_map["producto"]:
                            col_map["descripcion"] = c_idx
                break

        # Ignorar tablas auxiliares de metadatos donde no haya encabezado de productos
        if header_idx == -1:
            continue

        start_row = header_idx + 1
        for row in table[start_row:]:
            if not row or all(not str(c or "").strip() for c in row):
                continue
            row_concat = " ".join([str(c or "").upper() for c in row])
            if any(term in row_concat for term in ["SUBTOTAL", "TOTAL", "VALOR TOTAL", "OBSERVACIONES", "FIRMA"]):
                continue

            p_idx = col_map["producto"]
            q_idx = col_map["cantidad"]
            u_idx = col_map["unidad"]
            d_idx = col_map["descripcion"]

            p_name = str(row[p_idx] if p_idx < len(row) and p_idx != -1 else "").strip()
            raw_cant = row[q_idx] if q_idx < len(row) and q_idx != -1 else 0
            raw_unit = str(row[u_idx] if u_idx < len(row) and u_idx != -1 else "").strip()
            raw_desc = str(row[d_idx] if d_idx < len(row) and d_idx != -1 else "").strip()

            # Verificación de seguridad si el nombre del producto fue asignado por error a una unidad o índice numérico
            if p_name.upper() in KNOWN_UNIT_TOKENS or (parse_numeric(p_name) > 0 and len(p_name) < 5):
                for alt_idx, cell in enumerate(row):
                    cell_clean = clean_text(str(cell or "")).strip()
                    if cell_clean and cell_clean.upper() not in KNOWN_UNIT_TOKENS and parse_numeric(cell_clean) == 0:
                        if not raw_unit and p_name.upper() in KNOWN_UNIT_TOKENS:
                            raw_unit = p_name
                        p_name = cell_clean
                        break

            p_name = normalize_product_name(p_name)
            cant_val = parse_numeric(raw_cant)

            if cant_val <= 0:
                for alt_idx, cell in enumerate(row):
                    if alt_idx != p_idx:
                        val = parse_numeric(cell)
                        if val > 0:
                            cant_val = val
                            break

            if p_name and cant_val > 0 and not is_header_or_footer(p_name):
                unit, desc = normalize_unit_and_description(raw_unit, raw_desc)

                # Si la descripción quedó vacía (o era solo la unidad), buscar especificaciones en otras celdas
                if not desc:
                    used_indices = {p_idx, q_idx, u_idx, d_idx}
                    for alt_idx, cell in enumerate(row):
                        if alt_idx not in used_indices and alt_idx < len(row):
                            cell_str = clean_text(str(cell or "")).strip()
                            if cell_str and re.search(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]", cell_str):
                                cell_upper = cell_str.upper()
                                keywords = [
                                    "SUBTOTAL", "TOTAL", "VALOR", "PRECIO", "IVA", "BASE",
                                    "ITEM", "PRODUCTO", "CANTIDAD", "UNIDAD", "DESCRIPCION", "DESCRIPCIÓN"
                                ]
                                if cell_upper not in keywords and cell_upper not in KNOWN_UNIT_TOKENS:
                                    desc = cell_str
                                    break

                products.append({
                    "id": len(products) + 1,
                    "producto": p_name,
                    "cantidad": cant_val,
                    "unidad": unit,
                    "descripcion": desc,
                    "kilos": cant_val,
                    "valor_compra_total": 0.0,
                    "porcentaje_utilidad": settings.DEFAULT_PROFIT_MARGIN,
                })

    return products


def extract_products_from_ocr_boxes(ocr_results: List[Any]) -> List[Dict[str, Any]]:
    """Reconstruye líneas de tabla a partir de coordenadas espaciales de OCR."""
    if not ocr_results:
        return []

    items = []
    for item in ocr_results:
        box, text, score = item[0], item[1], item[2]
        if float(score) < 0.3 or not str(text).strip():
            continue
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        center_y = sum(ys) / len(ys)
        min_x = min(xs)
        max_x = max(xs)
        items.append({
            "text": clean_text(str(text)),
            "center_y": center_y,
            "min_x": min_x,
            "max_x": max_x,
            "height": max(ys) - min(ys)
        })

    items.sort(key=lambda x: x["center_y"])
    rows = []
    current_row = []
    current_y = None

    for it in items:
        if current_y is None:
            current_y = it["center_y"]
            current_row.append(it)
        else:
            if abs(it["center_y"] - current_y) <= (it["height"] * 0.65 or 12):
                current_row.append(it)
            else:
                current_row.sort(key=lambda x: x["min_x"])
                row_parts = []
                for idx_c, cell in enumerate(current_row):
                    if idx_c > 0:
                        prev = current_row[idx_c - 1]
                        gap = cell["min_x"] - prev["max_x"]
                        if gap > 35:
                            row_parts.append("|")
                    row_parts.append(cell["text"])
                rows.append(" ".join(row_parts))
                current_row = [it]
                current_y = it["center_y"]

    if current_row:
        current_row.sort(key=lambda x: x["min_x"])
        row_parts = []
        for idx_c, cell in enumerate(current_row):
            if idx_c > 0:
                prev = current_row[idx_c - 1]
                gap = cell["min_x"] - prev["max_x"]
                if gap > 35:
                    row_parts.append("|")
            row_parts.append(cell["text"])
        rows.append(" ".join(row_parts))

    products = []
    in_product_table = False

    for row_str in rows:
        upper_row = row_str.upper()

        if "PRODUCTO" in upper_row and ("CANTIDAD" in upper_row or "DESCRIP" in upper_row):
            in_product_table = True
            continue

        if any(term in upper_row for term in ["OBSERVACIONES", "SUBTOTAL", "TOTAL", "FIRMA"]):
            in_product_table = False

        if not in_product_table:
            continue

        if is_header_or_footer(row_str):
            continue

        parts = [p.strip() for p in row_str.split("|") if p.strip()]
        if len(parts) >= 2:
            p_name = normalize_product_name(parts[0])
            cant_val = parse_numeric(parts[1])

            if cant_val <= 0:
                for idx_p in range(1, len(parts)):
                    parsed = parse_numeric(parts[idx_p])
                    if parsed > 0:
                        cant_val = parsed
                        p_name = normalize_product_name(" ".join(parts[:idx_p]))
                        parts = [p_name, str(cant_val)] + parts[idx_p+1:]
                        break

            # Verificación de seguridad si p_name es una unidad o número
            if p_name.upper() in KNOWN_UNIT_TOKENS or (parse_numeric(p_name) > 0 and len(p_name) < 5):
                for alt_p in parts[1:]:
                    if alt_p.upper() not in KNOWN_UNIT_TOKENS and parse_numeric(alt_p) == 0:
                        p_name = normalize_product_name(alt_p)
                        break

            if p_name and cant_val > 0 and not is_header_or_footer(p_name):
                raw_u = parts[2] if len(parts) > 2 else ""
                raw_d = parts[3] if len(parts) > 3 else ""
                unit, desc = normalize_unit_and_description(raw_u, raw_d)

                products.append({
                    "id": len(products) + 1,
                    "producto": p_name,
                    "cantidad": cant_val,
                    "unidad": unit,
                    "descripcion": desc,
                    "kilos": cant_val,
                    "valor_compra_total": 0.0,
                    "porcentaje_utilidad": settings.DEFAULT_PROFIT_MARGIN,
                })

    return products


def format_cell_value(val: Any) -> str:
    """Convierte celdas de Excel (incluyendo datetime) a string limpio."""
    if val is None:
        return ""
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def _read_excel_to_grid(file_bytes: bytes, filename: str = "") -> List[List[Any]]:
    """
    Lee archivos .xlsx (openpyxl) o .xls (xlrd) a una matriz de celdas bidimensional.
    """
    ext = os.path.splitext(filename)[1].lower() if filename else ""
    raw_rows: List[List[Any]] = []

    if ext == ".xls":
        try:
            import xlrd
            book = xlrd.open_workbook(file_contents=file_bytes)
            sheet = book.sheet_by_index(0)
            for r in range(sheet.nrows):
                row_vals = []
                for c in range(sheet.ncols):
                    cell = sheet.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try:
                            dt_tuple = xlrd.xldate_as_tuple(cell.value, book.datemode)
                            val = datetime.date(dt_tuple[0], dt_tuple[1], dt_tuple[2])
                        except Exception:
                            val = str(cell.value)
                    elif cell.ctype == xlrd.XL_CELL_NUMBER:
                        val = int(cell.value) if cell.value.is_integer() else float(cell.value)
                    elif cell.ctype == xlrd.XL_CELL_EMPTY:
                        val = None
                    else:
                        val = cell.value
                    row_vals.append(val)
                raw_rows.append(row_vals)
            return raw_rows
        except Exception as e:
            raise ValueError(f"Error al procesar archivo Excel .xls: {str(e)}") from e

    # Intentar como .xlsx primero
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active if wb.active else wb.worksheets[0]
        for row in sheet.iter_rows(values_only=True):
            raw_rows.append(list(row))
        return raw_rows
    except InvalidFileException:
        # Fallback a xlrd si era un archivo .xls con extensión .xlsx o viceversa
        try:
            import xlrd
            book = xlrd.open_workbook(file_contents=file_bytes)
            sheet = book.sheet_by_index(0)
            for r in range(sheet.nrows):
                row_vals = []
                for c in range(sheet.ncols):
                    cell = sheet.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try:
                            dt_tuple = xlrd.xldate_as_tuple(cell.value, book.datemode)
                            val = datetime.date(dt_tuple[0], dt_tuple[1], dt_tuple[2])
                        except Exception:
                            val = str(cell.value)
                    elif cell.ctype == xlrd.XL_CELL_NUMBER:
                        val = int(cell.value) if cell.value.is_integer() else float(cell.value)
                    elif cell.ctype == xlrd.XL_CELL_EMPTY:
                        val = None
                    else:
                        val = cell.value
                    row_vals.append(val)
                raw_rows.append(row_vals)
            return raw_rows
        except Exception as err:
            raise ValueError("El archivo Excel no es válido o está dañado.") from err
    except Exception as e:
        raise ValueError(f"Error al leer el archivo Excel: {str(e)}") from e


def extract_data_from_excel(file_bytes: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Extrae metadatos del cliente, orden de compra y lista de productos 
    desde una hoja de cálculo Excel (.xlsx o .xls).
    """
    raw_rows = _read_excel_to_grid(file_bytes, filename)
    if not raw_rows:
        return {
            "numero_oc": "",
            "fecha_emision": "",
            "fecha_entrega": "",
            "observaciones": "",
            "cliente": {"razon_social": "", "nit": "", "email": ""},
            "productos": []
        }

    # Convertir celdas a strings limpios para análisis textual
    str_rows: List[List[str]] = [
        [format_cell_value(cell) for cell in row] for row in raw_rows
    ]

    # 1. Extracción de metadatos mediante inspección directa de celdas
    metadata: Dict[str, Any] = {
        "numero_oc": "",
        "fecha_emision": "",
        "fecha_entrega": "",
        "observaciones": "",
        "cliente": {
            "razon_social": "",
            "nit": "",
            "email": "",
        }
    }

    # Recorrer bloques superiores para metadatos (primeras 25 filas)
    in_entrega_section = False
    for r_idx, row in enumerate(str_rows[:25]):
        for c_idx, cell_str in enumerate(row):
            cell_upper = cell_str.upper()

            if "DATOS DE ENTREGA" in cell_upper:
                in_entrega_section = True

            # Número de Orden de Compra (OC)
            if not metadata["numero_oc"]:
                if any(kw in cell_upper for kw in ["NÚMERO DE OC", "NUMERO DE OC", "NUMERO OC", "N° DE OC", "NO. OC"]):
                    m_oc = RE_OC.search(cell_str)
                    if m_oc:
                        metadata["numero_oc"] = m_oc.group(1).strip()
                    else:
                        for next_c in range(c_idx + 1, min(c_idx + 4, len(row))):
                            val = row[next_c].strip()
                            if val:
                                metadata["numero_oc"] = val
                                break

            # Razón Social
            if not metadata["cliente"]["razon_social"]:
                if any(kw in cell_upper for kw in ["RAZÓN SOCIAL", "RAZON SOCIAL", "FACTURAR A", "CLIENTE", "SEÑORES", "COMPRADOR"]):
                    for next_c in range(c_idx + 1, min(c_idx + 4, len(row))):
                        val = row[next_c].strip()
                        if val and not is_header_or_footer(val):
                            metadata["cliente"]["razon_social"] = clean_razon_social(val)
                            break

            # NIT
            if not metadata["cliente"]["nit"]:
                if "NIT" in cell_upper or "IDENTIFICACI" in cell_upper:
                    m_nit = RE_NIT.search(cell_str)
                    if m_nit:
                        metadata["cliente"]["nit"] = m_nit.group(1).strip().replace(".", "")
                    else:
                        for next_c in range(c_idx + 1, min(c_idx + 4, len(row))):
                            val = row[next_c].strip().replace(".", "")
                            if re.search(r"\d", val):
                                metadata["cliente"]["nit"] = val
                                break

            # Email
            if not metadata["cliente"]["email"]:
                if "@" in cell_str:
                    m_em = RE_EMAIL.search(cell_str)
                    if m_em:
                        metadata["cliente"]["email"] = m_em.group(1).strip()
                    else:
                        metadata["cliente"]["email"] = cell_str.strip()

            # Fechas
            if "FECHA" in cell_upper:
                for next_c in range(c_idx + 1, min(c_idx + 4, len(row))):
                    val = row[next_c].strip()
                    m_date = re.search(RE_DATE_PATTERN, val)
                    if m_date:
                        date_found = m_date.group(0)
                        if in_entrega_section or "ENTREGA" in cell_upper:
                            if not metadata["fecha_entrega"]:
                                metadata["fecha_entrega"] = date_found
                        else:
                            if not metadata["fecha_emision"]:
                                metadata["fecha_emision"] = date_found
                        break

    # Fallback con texto concatenado para campos que aún falten
    combined_header_text = "\n".join([" ".join([c for c in r if c]) for r in str_rows[:25]])
    fb_meta = extract_metadata_from_text(combined_header_text)
    for k in ["numero_oc", "fecha_emision", "fecha_entrega"]:
        if not metadata[k] and fb_meta.get(k):
            metadata[k] = fb_meta[k]
    for ck in ["razon_social", "nit", "email"]:
        if not metadata["cliente"][ck] and fb_meta["cliente"].get(ck):
            metadata["cliente"][ck] = fb_meta["cliente"][ck]

    # 2. Localizar la cabecera de la tabla de productos
    header_row_idx = -1
    col_map = {"producto": -1, "cantidad": -1, "unidad": -1, "descripcion": -1}

    for idx, r in enumerate(str_rows):
        r_upper = [c.upper() for c in r]
        has_prod = any("PRODUCTO" in c or "ARTICULO" in c or "ITEM" in c for c in r_upper)
        has_cant = any("CANTIDAD" in c or "CANT" in c or "KILOS" in c or "KG" in c for c in r_upper)

        if has_prod and has_cant:
            header_row_idx = idx
            for col_idx, col_name in enumerate(r_upper):
                if "PRODUCTO" in col_name or "ARTICULO" in col_name:
                    col_map["producto"] = col_idx
                elif "CANTIDAD" in col_name or "CANT" in col_name or "KILOS" in col_name or "KG" in col_name:
                    col_map["cantidad"] = col_idx
                elif "UNIDAD" in col_name or "UND" in col_name or "MEDIDA" in col_name or "U.M" in col_name:
                    col_map["unidad"] = col_idx
                elif "DESCRIP" in col_name or "DETALLE" in col_name or "ESPECIFIC" in col_name:
                    if col_map["descripcion"] == -1:
                        col_map["descripcion"] = col_idx
            break

    if header_row_idx == -1:
        # Fallback si no hay cabecera explícita
        header_row_idx = 0
        col_map = {"producto": 0, "cantidad": 1, "unidad": 2, "descripcion": 3}

    # 3. Extraer productos y capturar observaciones al final
    productos_extraidos: List[Dict[str, Any]] = []
    observaciones_list: List[str] = []
    in_observaciones = False

    for r_idx in range(header_row_idx + 1, len(str_rows)):
        r = str_rows[r_idx]
        if not r or all(not str(c or "").strip() for c in r):
            continue

        row_concat = " ".join(r).upper()

        if "OBSERVACIONES" in row_concat:
            in_observaciones = True
            obs_clean = re.sub(r"^.*?OBSERVACIONES:?", "", " ".join(r), flags=re.IGNORECASE).strip()
            if obs_clean:
                observaciones_list.append(obs_clean)
            continue

        if in_observaciones:
            line_str = " ".join([c for c in r if c]).strip()
            if line_str and not any(kw in line_str.upper() for kw in ["TOTAL", "SUBTOTAL", "FIRMA", "AUTORIZADO"]):
                observaciones_list.append(line_str)
            continue

        if any(term in row_concat for term in ["SUBTOTAL", "TOTAL", "VALOR TOTAL", "FIRMA", "ELABORÓ", "APROBÓ"]):
            continue

        p_idx = col_map["producto"]
        q_idx = col_map["cantidad"]
        u_idx = col_map["unidad"]
        d_idx = col_map["descripcion"]

        raw_prod = r[p_idx] if 0 <= p_idx < len(r) else ""
        raw_cant = r[q_idx] if 0 <= q_idx < len(r) else ""
        raw_unit = r[u_idx] if 0 <= u_idx < len(r) else ""
        raw_desc = r[d_idx] if 0 <= d_idx < len(r) else ""

        if not raw_prod:
            continue

        p_name = normalize_product_name(raw_prod)
        if not p_name or is_header_or_footer(p_name):
            continue

        cant_val = parse_numeric(raw_cant)

        # Si la cantidad no está en la columna mapeada, buscar en otras celdas
        if cant_val <= 0:
            for alt_idx, cell in enumerate(r):
                if alt_idx != p_idx:
                    val = parse_numeric(cell)
                    if val > 0:
                        cant_val = val
                        break

        # FILTRAR productos con cantidad <= 0 (plantillas donde no se solicitó el producto)
        if cant_val <= 0:
            continue

        unit, desc = normalize_unit_and_description(raw_unit, raw_desc)

        productos_extraidos.append({
            "id": len(productos_extraidos) + 1,
            "producto": p_name,
            "cantidad": cant_val,
            "unidad": unit,
            "descripcion": desc,
            "kilos": cant_val,
            "valor_compra_total": 0.0,
            "porcentaje_utilidad": settings.DEFAULT_PROFIT_MARGIN,
        })

    # Observaciones limpias por defecto
    metadata["observaciones"] = ""

    metadata["productos"] = productos_extraidos
    return metadata


class GeminiOrderVisionEngine:
    """
    Motor multimodal de visión profunda vía Google Gemini API para extracción inteligente de órdenes y pedidos.
    Utiliza structured JSON y análisis multimodal directo:
    - Para imágenes (.png, .jpg, .jpeg, .webp, .bmp): Extrae metadatos y tabla de productos.
    - Para PDFs escaneados (documentos con imágenes o sin texto vectorial): Analiza el documento vía multimodal nativo o páginas renderizadas.
    - Soporta fallback en cascada a través de modelos disponibles: gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-flash, gemini-flash-lite-latest, gemini-3-flash-preview.
    """
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = (api_key or getattr(settings, "GEMINI_API_KEY", "")).strip()
        raw_model = (model_name or getattr(settings, "GEMINI_MODEL", "") or "gemini-2.5-flash").strip()
        if raw_model.startswith("models/"):
            raw_model = raw_model[len("models/"):]
        self.model_name = raw_model

    def is_available(self) -> bool:
        return bool(self.api_key and getattr(settings, "VISION_PROVIDER", "gemini").lower() == "gemini")

    def _call_gemini_api(self, media_parts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Llama a la API de Gemini con manejo de reintentos sobre modelos disponibles."""
        if not self.is_available() or not media_parts:
            return None

        prompt = (
            "Eres un auditor y transcriptor experto en recepción y digitalización de órdenes de compra, "
            "pedidos institucionales y remisiones de frutas, verduras, abarrotes y víveres para el mercado colombiano.\n"
            "Tu misión es extraer de forma exhaustiva y estructurada la totalidad de los productos solicitados y los metadatos de la cabecera.\n\n"
            "REGLAS:\n"
            "1. Extrae cada renglón de producto sin omitir ninguno: nombre limpio del producto ('producto'), cantidad numérica ('cantidad'), unidad ('unidad', ej: Kg, Und, Bolsa, Caja, Bulto), y especificaciones o detalles si los hay ('descripcion').\n"
            "2. Identifica la cabecera del documento: nombre o razón social del cliente ('cliente'), número de orden de compra o pedido ('numero_oc'), fecha de emisión ('fecha_emision'), fecha de entrega ('fecha_entrega') y observaciones generales ('observaciones').\n"
            "3. No incluyas totales, subtotales ni leyendas legales como productos.\n"
            "4. Devuelve exclusivamente un objeto JSON válido con las claves especificadas: 'cliente' (objeto con 'razon_social' y 'nit'), 'numero_oc', 'fecha_emision', 'fecha_entrega', 'observaciones', 'productos' (lista de objetos con 'producto', 'cantidad', 'unidad', 'descripcion')."
        )

        full_parts = [{"text": prompt}] + media_parts

        payload = {
            "contents": [
                {
                    "parts": full_parts
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        models_to_try = [self.model_name]
        for m in [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
        ]:
            if m not in models_to_try:
                models_to_try.append(m)

        for candidate_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={self.api_key}"
            try:
                with httpx.Client(timeout=35.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates") or []
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                text_res = parts[0].get("text", "")
                                clean_json = text_res.strip()
                                if clean_json.startswith("```"):
                                    clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
                                    clean_json = re.sub(r"\s*```$", "", clean_json)
                                parsed_data = json.loads(clean_json)
                                return self._format_gemini_response(parsed_data)
                    elif resp.status_code in (429, 503):
                        logger.warning(f"Gemini {candidate_model} ocupado ({resp.status_code}), probando siguiente modelo...")
                        continue
                    elif resp.status_code == 404:
                        continue
                    else:
                        logger.warning(f"Gemini error {resp.status_code} en modelo {candidate_model}")
                        continue
            except Exception as e_call:
                logger.warning(f"Fallo en llamada a Gemini ({candidate_model}): {e_call}")
                continue

        return None

    def extract_order_from_image(self, file_bytes: bytes, filename: str = "") -> Optional[Dict[str, Any]]:
        """Extrae datos de pedido a partir de una imagen utilizando Gemini Vision."""
        optimized_bytes = optimize_image_for_vision(file_bytes)
        b64_img = base64.b64encode(optimized_bytes).decode("utf-8")
        media_parts = [
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": b64_img
                }
            }
        ]
        return self._call_gemini_api(media_parts)

    def extract_order_from_pdf(self, file_bytes: bytes, filename: str = "") -> Optional[Dict[str, Any]]:
        """
        Extrae datos de pedido a partir de un PDF escaneado con imágenes.
        Intenta primero enviar el documento PDF directamente a Gemini (multimodal nativo application/pdf).
        Si no es admitido o falla, renderiza sus páginas a JPEG optimizado y las envía como partes de imagen.
        """
        # 1. Intentar envío directo del documento PDF a Gemini
        try:
            b64_pdf = base64.b64encode(file_bytes).decode("utf-8")
            pdf_parts = [
                {
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": b64_pdf
                    }
                }
            ]
            res = self._call_gemini_api(pdf_parts)
            if res and res.get("productos"):
                return res
        except Exception as e_pdf_direct:
            logger.debug(f"Envío de PDF nativo a Gemini omitido ({e_pdf_direct}), probando páginas renderizadas...")

        # 2. Renderizar páginas a imágenes y enviarlas a Gemini Vision
        page_images = render_pdf_pages_to_images(file_bytes, max_pages=5)
        if page_images:
            img_parts = [
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(img_b).decode("utf-8")
                    }
                }
                for img_b in page_images
            ]
            return self._call_gemini_api(img_parts)

        return None

    def _format_gemini_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza la salida devuelta por Gemini al contrato de datos estricto de Sistema Fruver."""
        raw_cliente = raw.get("cliente")
        if isinstance(raw_cliente, dict):
            cliente_data = {
                "razon_social": str(raw_cliente.get("razon_social") or raw_cliente.get("nombre") or "").strip(),
                "nit": str(raw_cliente.get("nit") or "").strip()
            }
        else:
            cliente_data = {
                "razon_social": str(raw_cliente or "").strip(),
                "nit": ""
            }

        raw_prods = raw.get("productos") or []
        formatted_prods = []
        for idx, p in enumerate(raw_prods, start=1):
            if not isinstance(p, dict):
                continue
            p_name = normalize_product_name(str(p.get("producto") or p.get("nombre") or ""))
            if not p_name or is_header_or_footer(p_name):
                continue
            cant_val = parse_numeric(p.get("cantidad") or 0)
            if cant_val <= 0:
                cant_val = 1.0
            raw_u = str(p.get("unidad") or "")
            raw_d = str(p.get("descripcion") or p.get("observaciones") or "")
            unit, desc = normalize_unit_and_description(raw_u, raw_d)

            formatted_prods.append({
                "id": idx,
                "producto": p_name,
                "cantidad": cant_val,
                "unidad": unit,
                "descripcion": desc,
                "kilos": cant_val,
                "valor_compra_total": 0.0,
                "porcentaje_utilidad": settings.DEFAULT_PROFIT_MARGIN,
            })

        return {
            "numero_oc": str(raw.get("numero_oc") or "").strip(),
            "fecha_emision": str(raw.get("fecha_emision") or "").strip(),
            "fecha_entrega": str(raw.get("fecha_entrega") or "").strip(),
            "observaciones": str(raw.get("observaciones") or "").strip(),
            "cliente": cliente_data,
            "productos": formatted_prods
        }


def extraer_datos_documento(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Punto de entrada síncrono para extracción estructurada sobre Excel (.xlsx, .xls), PDFs e Imágenes:
    1. EXCEL (.xlsx, .xls) -> Lectura nativa estructurada (openpyxl / xlrd).
    2. PDF DIGITAL -> Lectura nativa vectorial con pdfplumber y extracción de tablas y texto. No usa Gemini si el documento contiene texto digital.
    3. PDF ESCANEADO / CON IMÁGENES -> Extracción inteligente multimodal con Gemini Vision.
    4. IMÁGENES (.png, .jpg, .jpeg, .webp, .bmp) -> Extracción inteligente con Gemini Vision.
    """
    fn_lower = filename.lower() if filename else ""

    # 1. EXCEL: LECTURA 100% NATIVA (Sin Gemini ni OCR)
    if fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls"):
        return extract_data_from_excel(file_bytes, filename)

    # 2. PDF: PRIMERO INTENTAR LECTURA VECTORIAL NATIVA
    if fn_lower.endswith(".pdf"):
        extracted_text = ""
        all_tables = []
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    extracted_text += page_text + "\n"
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
        except Exception as e_pdf:
            logger.warning(f"Error al analizar PDF vectorial con pdfplumber: {e_pdf}")

        products = []
        if all_tables:
            products = extract_products_from_pdf_tables(all_tables)

        # Si el documento tiene texto vectorial suficiente (>= 50 caracteres) o se extrajeron productos nativamente
        if products or len(extracted_text.strip()) >= 50:
            metadata = extract_metadata_from_text(extracted_text)
            return {
                "numero_oc": metadata.get("numero_oc", ""),
                "fecha_emision": metadata.get("fecha_emision", ""),
                "fecha_entrega": metadata.get("fecha_entrega", ""),
                "observaciones": metadata.get("observaciones", ""),
                "cliente": metadata.get("cliente", {"razon_social": "", "nit": ""}),
                "productos": products
            }

        # 3. PDF ESCANEADO / IMAGEN EN PDF: Recurrir a Gemini Vision
        gemini_engine = GeminiOrderVisionEngine()
        if gemini_engine.is_available():
            try:
                gemini_res = gemini_engine.extract_order_from_pdf(file_bytes, filename)
                if gemini_res and gemini_res.get("productos"):
                    return gemini_res
            except Exception as e_gem:
                logger.warning(f"Error procesando PDF escaneado con Gemini Vision: {e_gem}")

        # Si Gemini no está configurado o no pudo extraer productos
        metadata = extract_metadata_from_text(extracted_text)
        return {
            "numero_oc": metadata.get("numero_oc", ""),
            "fecha_emision": metadata.get("fecha_emision", ""),
            "fecha_entrega": metadata.get("fecha_entrega", ""),
            "observaciones": "PDF escaneado o documento con imágenes. Configure GEMINI_API_KEY para digitalización automática con IA.",
            "cliente": metadata.get("cliente", {"razon_social": "", "nit": ""}),
            "productos": []
        }

    # 4. IMÁGENES (JPG, PNG, WebP, BMP): PROCESAMIENTO MULTIMODAL CON GEMINI VISION
    gemini_engine = GeminiOrderVisionEngine()
    if gemini_engine.is_available():
        try:
            gemini_res = gemini_engine.extract_order_from_image(file_bytes, filename)
            if gemini_res and gemini_res.get("productos"):
                return gemini_res
        except Exception as e_gem_img:
            logger.warning(f"Error procesando imagen con Gemini Vision: {e_gem_img}")

    return {
        "numero_oc": "",
        "fecha_emision": "",
        "fecha_entrega": "",
        "observaciones": "Imagen recibida. Se requiere GEMINI_API_KEY activa para procesar imágenes con Gemini Vision.",
        "cliente": {"razon_social": "", "nit": ""},
        "productos": []
    }


async def extraer_datos_documento_async(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Punto de entrada asíncrono no bloqueante.
    Ejecuta el procesamiento intensivo en un thread pool worker separado.
    """
    return await asyncio.to_thread(extraer_datos_documento, file_bytes, filename)