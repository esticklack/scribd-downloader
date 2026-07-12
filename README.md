# script-scribd

Herramienta CLI para descargar documentos públicos de [Scribd](https://www.scribd.com) como PDF. Usa Chrome (Selenium) para renderizar el embed del documento, soporta documentos de texto e imágenes, y puede recortar márgenes de impresión automáticamente en Windows.

## Qué hace

- Convierte una URL de Scribd (`/document/...`, `/doc/...`) en PDF.
- **Documentos de texto:** renderiza el embed en Chrome headless y exporta vía Chrome DevTools Protocol (texto vectorial).
- **Documentos escaneados / de imagen:** descarga los JPG originales y los une sin recomprimir.
- **Post-proceso opcional:** elimina el blanco extra que deja la impresión de Chrome.
- **Wrapper de PowerShell:** comando `scribd` con barra de progreso nativa.

## Requisitos

Antes de empezar, necesitas:

1. **Python 3.10 o superior**
2. **[Google Chrome](https://www.google.com/chrome/)** instalado
3. **PowerShell 5+** (solo si quieres usar el wrapper `scribd` en Windows)

Comprueba Python:

```powershell
python --version
```

## Instalación paso a paso

### 1. Clonar o descargar el proyecto

```bash
git clone https://github.com/esticklack/script-scribd.git
cd script-scribd
```

### 2. Crear un entorno virtual (recomendado)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux o macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

Dependencias instaladas:

| Paquete   | Uso                                      |
|-----------|------------------------------------------|
| selenium  | Controlar Chrome y exportar el PDF       |
| requests  | Descargar imágenes de páginas escaneadas |
| img2pdf   | Unir imágenes en un PDF                  |
| PyMuPDF   | Recortar márgenes de impresión           |

### 4. (Opcional) Configurar el comando `scribd` en PowerShell

Para usar el script desde cualquier terminal con un solo comando:

1. Abre tu perfil de PowerShell:

   ```powershell
   notepad $PROFILE
   ```

   Si el archivo no existe, créalo cuando PowerShell lo pregunte.

2. Añade esta línea al final, apuntando a donde clonaste el repositorio:

   ```powershell
   . "C:\ruta\a\script-scribd\scribd.ps1"
   ```

3. Guarda el archivo y recarga el perfil:

   ```powershell
   . $PROFILE
   ```

## Uso paso a paso

### Opción A — PowerShell (recomendado en Windows)

**1.** Copia la URL del documento en Scribd. Debe ser una URL pública, por ejemplo:

```
https://www.scribd.com/document/123456789/Titulo-del-documento
```

**2.** Ejecuta:

```powershell
scribd "https://www.scribd.com/document/123456789/Titulo-del-documento"
```

**3.** Espera a que termine. Verás:

- Barra de progreso durante la descarga y el recorte
- El título detectado del documento
- La ruta final del PDF

**4.** El PDF quedará en tu carpeta de Descargas (`~/Downloads`), con el título del documento como nombre de archivo.

#### Opciones del comando `scribd`

| Comando | Descripción |
|---------|-------------|
| `scribd "URL"` | Descarga y recorta márgenes (documentos de texto) |
| `scribd "URL" -NoCrop` | Descarga sin recortar márgenes |

> Los documentos de imagen ya salen ajustados (imagen = página), así que el recorte se omite automáticamente.

---

### Opción B — Python directo

**1.** Activa el entorno virtual si lo usas.

**2.** Ejecuta el descargador con la URL:

```bash
python scribd_dl.py "https://www.scribd.com/document/123456789/Titulo-del-documento"
```

**3.** Si no pasas URL, el script la pedirá por teclado:

```bash
python scribd_dl.py
```

**4.** El PDF se guarda en `~/Downloads` con el título del documento como nombre de archivo.

#### Recortar márgenes manualmente

Solo necesario para PDFs de texto generados por Chrome (no para documentos de imagen):

```bash
# Crea una copia con sufijo _sinmargen
python recortar_margenes.py ~/Downloads/documento.pdf

# Sobrescribe el PDF original
python recortar_margenes.py ~/Downloads/documento.pdf --reemplazar

# Opciones adicionales
python recortar_margenes.py documento.pdf --margen 4 --salida limpio.pdf
python recortar_margenes.py documento.pdf --uniforme --reemplazar
```

| Argumento | Descripción |
|-----------|-------------|
| `--reemplazar`, `-r` | Sobrescribe el PDF de entrada |
| `--salida`, `-o` | Ruta del PDF de salida |
| `--margen`, `-m` | Margen extra alrededor del contenido (puntos, default: 2) |
| `--uniforme` | Recorta todas las páginas al mismo tamaño |

## Cómo funciona

```
URL de Scribd
     │
     ▼
Convierte a URL embed (/embeds/{id}/content)
     │
     ▼
Abre Chrome headless y hace scroll por todas las páginas
     │
     ├── Documento de IMAGEN ──► Descarga JPG originales ──► PDF con img2pdf
     │
     └── Documento de TEXTO ───► Exporta vía CDP (printToPDF)
                                      │
                                      ▼
                              recortar_margenes.py (opcional)
```

## Variables de entorno

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `SCRIBD_HEADLESS` | `1` | Pon `0` para abrir Chrome visible (útil para depurar) |
| `SCRIBD_SCROLL_DELAY` | `0.15` | Segundos entre scroll de páginas |
| `SCRIBD_RENDER_SETTLE_TIMEOUT` | `30` | Espera máxima para que el render se estabilice |
| `SCRIBD_CDP_TIMEOUT` | `600` | Timeout de ChromeDriver para PDFs grandes |
| `SCRIBD_PDF_STREAM_CHUNK_SIZE` | `1048576` | Tamaño del chunk al transferir PDFs grandes |

Ejemplo en PowerShell:

```powershell
$env:SCRIBD_HEADLESS = "0"
scribd "https://www.scribd.com/document/..."
```

## Solución de problemas

| Problema | Qué probar |
|----------|------------|
| `python` no se reconoce | Instala Python y marca la opción "Add to PATH" en el instalador |
| Error de Chrome / ChromeDriver | Actualiza Google Chrome a la última versión |
| El PDF no se recorta | Comprueba que la ruta del PDF no tenga caracteres corruptos; el wrapper fuerza UTF-8 |
| Documento muy largo falla | Aumenta `SCRIBD_CDP_TIMEOUT` (p. ej. `900`) |
| Páginas incompletas | Aumenta `SCRIBD_SCROLL_DELAY` o `SCRIBD_RENDER_SETTLE_TIMEOUT` |
| `scribd` no se reconoce | Verifica que cargaste `scribd.ps1` en `$PROFILE` y recargaste el perfil |

## Estructura del proyecto

```
script-scribd/
├── scribd_dl.py          # Descargador principal
├── recortar_margenes.py  # Post-proceso de márgenes
├── scribd.ps1            # Wrapper PowerShell con barra de progreso
├── requirements.txt
├── LICENSE
└── README.md
```

## Aviso legal

Esta herramienta es solo para **uso personal y educativo**. Úsala únicamente con documentos que tengas derecho a descargar (propios, de dominio público o con permiso explícito del autor).

Descargar contenido protegido por derechos de autor o saltar restricciones de acceso puede violar los [Términos de Servicio de Scribd](https://support.scribd.com/hc/en-us/articles/210129166) y la legislación aplicable. Los autores de este proyecto no se hacen responsables del uso que terceros hagan del software.

## Licencia

[MIT](LICENSE)
