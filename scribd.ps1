# Scribd PDF downloader — wrapper de PowerShell
#
# Uso en $PROFILE:
#   . "C:\ruta\a\script-scribd\scribd.ps1"
#
# Luego:
#   scribd "https://www.scribd.com/document/..."
#   scribd "https://..." -NoCrop

$script:ScribdBase = $PSScriptRoot

function scribd {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        # -NoCrop: descarga sin recortar margenes (por defecto SI recorta).
        [switch]$NoCrop
    )

    $scriptPath = Join-Path $script:ScribdBase "scribd_dl.py"
    $cropPath   = Join-Path $script:ScribdBase "recortar_margenes.py"

    if (-not (Test-Path $scriptPath)) {
        Write-Host "[ERROR] Script principal no encontrado en: $scriptPath" -ForegroundColor Red
        return
    }

    # Decodificar la salida de Python como UTF-8 para no romper acentos/ñ en los
    # titulos (si no, las rutas con tildes no coinciden y falla el recorte).
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    # Ejecuta python, pinta la barra de progreso nativa desde los marcadores
    # @@P@@ y devuelve solo las lineas normales (sin las de progreso).
    function Invoke-PyProgress($activity, $argList) {
        $lines = New-Object System.Collections.Generic.List[string]
        & python @argList 2>&1 | ForEach-Object {
            $line = [string]$_
            if ($line -match '^@@P@@\s+(\d+)\s*(.*)$') {
                Write-Progress -Activity $activity -Status $matches[2] -PercentComplete ([int]$matches[1])
            }
            elseif ($line.Trim()) {
                $lines.Add($line)
            }
        }
        Write-Progress -Activity $activity -Completed
        return $lines
    }

    try {
        Write-Host "[INFO] Descargando: $Url" -ForegroundColor Cyan
        $lineas = Invoke-PyProgress "Descargando de Scribd" @($scriptPath, $Url)

        if ($LASTEXITCODE -ne 0) {
            Write-Host "[AVISO] El script termino con codigo ${LASTEXITCODE}:" -ForegroundColor Yellow
            $lineas | ForEach-Object { Write-Host "    $_" }
            return
        }

        $titulo = ($lineas | Where-Object { $_ -match '^Titulo:\s*(.+)$' } |
            ForEach-Object { $Matches[1].Trim() } | Select-Object -Last 1)
        if ($titulo) { Write-Host "[OK] Titulo: $titulo" -ForegroundColor Green }

        $esImagen = $lineas | Where-Object { $_ -match 'Documento de imagenes' } | Select-Object -First 1
        $pdf = $lineas | Where-Object { $_ -match 'saved successfully to:\s*(.+)$' } |
            ForEach-Object { $Matches[1].Trim() } | Select-Object -Last 1

        # Los documentos de imagen ya salen ajustados (imagen = pagina) -> sin recorte.
        if ((-not $NoCrop) -and (-not $esImagen)) {
            if ($pdf -and (Test-Path $pdf)) {
                Write-Host "[INFO] Recortando margenes..." -ForegroundColor Cyan
                $null = Invoke-PyProgress "Recortando margenes" @($cropPath, $pdf, "--reemplazar")
            }
            else {
                Write-Host "[AVISO] No se pudo localizar el PDF para recortar." -ForegroundColor Yellow
            }
        }
        elseif ($esImagen) {
            Write-Host "[OK] Documento de imagenes: ya viene ajustado, sin recorte." -ForegroundColor Green
        }

        if ($pdf) { Write-Host "[LISTO] $pdf" -ForegroundColor Green }
    }
    catch {
        Write-Host "[ERROR] Fallo al ejecutar Scribd Downloader:" -ForegroundColor Red
        Write-Host $_.Exception.Message
    }
}
