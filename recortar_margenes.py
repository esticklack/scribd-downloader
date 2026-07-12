"""
Recorta los margenes de impresion de un PDF de Scribd.
=======================================================

Quita SOLO el blanco extra que añade la impresion (el reescalado de Chrome),
respetando lo que debe quedar segun el tipo de pagina:

  * Pagina de IMAGEN (p. ej. un libro para colorear): recorta pegado al dibujo.
  * Pagina de TEXTO: recorta al MARCO de la pagina original, conservando los
    margenes de diseno del documento (que NO son basura, son parte de la pagina).

Uso:
    python recortar_margenes.py "documento.pdf"
    python recortar_margenes.py "documento.pdf" --reemplazar
    python recortar_margenes.py "documento.pdf" --margen 4 --salida "limpio.pdf"

Por defecto recorta CADA pagina a su propio contenido. Con --uniforme recorta
todas al mismo tamano (la union del contenido de todas).
"""

import argparse
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import fitz  # PyMuPDF


def progress(percent, message=""):
    """Emite progreso para la barra de PowerShell: @@P@@ <0-100> <mensaje>."""
    print(f"@@P@@ {int(percent)} {message}", flush=True)

# Margen extra a dejar alrededor del contenido detectado (en puntos).
DEFAULT_MARGIN = 2
# Una pagina se considera "de imagen" si una imagen cubre al menos este % del papel.
IMAGE_PAGE_RATIO = 0.40
# Un dibujo se considera "marco de pagina" si su area esta en este rango del papel.
FRAME_MIN_RATIO = 0.15
FRAME_MAX_RATIO = 0.95
# Respaldo por pixeles.
DETECT_SCALE = 2.0
WHITE_THRESHOLD = 245


def _union(rects):
    u = None
    for r in rects:
        if r is None or r.is_empty:
            continue
        u = fitz.Rect(r) if u is None else (u | r)
    return u


def _marco_de_pagina(page, contiene):
    """
    Busca el dibujo que actua de marco/fondo de la pagina y que envuelve la
    caja `contiene` (el texto). Devuelve el marco mas ajustado, o None.
    """
    rect = page.rect
    page_area = max(1.0, rect.width * rect.height)
    mejor = None
    mejor_area = None
    try:
        dibujos = page.get_drawings()
    except Exception:
        return None
    for d in dibujos:
        r = fitz.Rect(d["rect"])
        if r.is_empty:
            continue
        area = r.width * r.height
        if area >= FRAME_MAX_RATIO * page_area:   # fondo a sangre: lo ignoramos
            continue
        if area < FRAME_MIN_RATIO * page_area:    # demasiado pequeno para ser marco
            continue
        # Debe contener el texto (con 2pt de tolerancia).
        if (r.x0 <= contiene.x0 + 2 and r.y0 <= contiene.y0 + 2 and
                r.x1 >= contiene.x1 - 2 and r.y1 >= contiene.y1 - 2):
            if mejor is None or area < mejor_area:
                mejor, mejor_area = r, area
    return mejor


def _bbox_por_contenido(page):
    """
    Devuelve (caja, tipo) para recortar la pagina:
      - ("image") imagen dominante -> la imagen (ajustado, sin margen)
      - ("frame") texto -> el marco de pagina (ya trae sus margenes, sin extra)
      - ("text")  texto sin marco -> el texto (se le deja un margen configurable)
    """
    rect = page.rect
    page_area = max(1.0, rect.width * rect.height)

    # Imagenes
    img_rects = []
    for im in page.get_images(full=True):
        try:
            img_rects += [fitz.Rect(r) for r in page.get_image_rects(im[0])]
        except Exception:
            pass
    img_bbox = _union(img_rects)
    img_area = (img_bbox.width * img_bbox.height) if img_bbox else 0.0

    # Texto
    text_rects = []
    for b in page.get_text("blocks"):
        if b[4] and b[4].strip():
            text_rects.append(fitz.Rect(b[0], b[1], b[2], b[3]))
    text_bbox = _union(text_rects)
    text_area = (text_bbox.width * text_bbox.height) if text_bbox else 0.0

    # PAGINA DE IMAGEN: recorte ajustado a la imagen.
    if img_bbox and img_area >= IMAGE_PAGE_RATIO * page_area and img_area >= text_area:
        return (img_bbox & rect, "image")

    # PAGINA DE TEXTO: conservar los margenes de la pagina original.
    if text_bbox:
        marco = _marco_de_pagina(page, text_bbox)
        if marco is not None:
            return (marco & rect, "frame")
        return (text_bbox & rect, "text")  # sin marco -> ajustado al texto

    # Resto: lo que haya.
    if img_bbox:
        return (img_bbox & rect, "image")
    return (None, None)


def _bbox_por_pixeles(page, scale=DETECT_SCALE, threshold=WHITE_THRESHOLD):
    """Respaldo: detecta tinta por pixeles."""
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    w, h, s, data = pix.width, pix.height, pix.stride, pix.samples
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row = data[y * s: y * s + w]
        left = next((x for x in range(w) if row[x] < threshold), None)
        if left is None:
            continue
        right = next((x for x in range(w - 1, -1, -1) if row[x] < threshold), w - 1)
        min_x = min(min_x, left); max_x = max(max_x, right)
        min_y = min(min_y, y); max_y = max(max_y, y)
    if max_x < 0:
        return None
    r = page.rect
    return fitz.Rect(r.x0 + min_x / scale, r.y0 + min_y / scale,
                     r.x0 + (max_x + 1) / scale, r.y0 + (max_y + 1) / scale)


def content_bbox(page):
    """
    Devuelve (caja, tipo) de recorte de la pagina; si no se detecta contenido,
    recurre a la deteccion por pixeles.
    """
    bb, kind = _bbox_por_contenido(page)
    if bb is None or bb.is_empty or bb.width < 2 or bb.height < 2:
        bb = _bbox_por_pixeles(page)
        kind = "pixel"
    return bb, kind


def recortar(input_path, output_path=None, margen=DEFAULT_MARGIN,
             uniforme=False, reemplazar=False):
    if not os.path.isfile(input_path):
        print(f"[ERROR] No existe el archivo: {input_path}")
        return None

    if reemplazar:
        fd, output_path = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(input_path) or ".")
        os.close(fd)
    elif output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_sinmargen{ext}"

    doc = fitz.open(input_path)
    print(f"Analizando {doc.page_count} paginas...")

    bboxes = []
    kinds = []
    n = doc.page_count
    for i, page in enumerate(doc):
        bb, kind = content_bbox(page)
        bboxes.append(bb)
        kinds.append(kind)
        progress(90 * (i + 1) / n, f"Analizando pagina {i + 1}/{n}")
        if (i + 1) % 10 == 0 or i + 1 == n:
            print(f"  Analizadas {i + 1}/{n}")

    union = _union(bboxes)
    if union is None:
        print("[AVISO] No se detecto contenido; no se recorto nada.")
        doc.close()
        return None

    recortadas = 0
    for i, page in enumerate(doc):
        if uniforme:
            box = union
        else:
            box = bboxes[i] if bboxes[i] is not None else union
        # Imagen y marco ya vienen ajustados (la imagen es la pagina; el marco ya
        # trae los margenes de diseno) -> sin margen extra. Solo el texto suelto
        # recibe el margen configurable para no quedar apretado.
        m = 0 if kinds[i] in ("image", "frame") else margen
        box = box + (-m, -m, m, m)
        box = box & page.rect
        if box.is_empty or box.width < 1 or box.height < 1:
            continue
        page.set_cropbox(box)
        recortadas += 1

    progress(95, "Guardando")
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()

    if reemplazar:
        os.replace(output_path, input_path)
        final = input_path
    else:
        final = output_path

    progress(100, "Listo")
    print(f"\n[OK] {recortadas} paginas recortadas.")
    print(f"Guardado en: {os.path.abspath(final)}")
    return final


def main():
    parser = argparse.ArgumentParser(description="Recorta los margenes de impresion de un PDF.")
    parser.add_argument("pdf", help="Ruta del PDF de entrada")
    parser.add_argument("--salida", "-o", default=None, help="Ruta del PDF de salida")
    parser.add_argument("--reemplazar", "-r", action="store_true",
                        help="Sobrescribe el PDF original con la version recortada")
    parser.add_argument("--margen", "-m", type=float, default=DEFAULT_MARGIN,
                        help=f"Margen alrededor del contenido en puntos (def. {DEFAULT_MARGIN})")
    parser.add_argument("--uniforme", action="store_true",
                        help="Recorta todas las paginas al mismo tamano (en vez de cada una a su contenido)")
    args = parser.parse_args()

    result = recortar(args.pdf, args.salida, args.margen, args.uniforme, args.reemplazar)
    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
