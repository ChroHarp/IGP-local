param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$OutputDirectory = $env:TEMP,

    [string]$LibreOfficePath = "C:\Program Files\LibreOffice\program\soffice.com"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $LibreOfficePath -PathType Leaf)) {
    $command = Get-Command soffice.com -ErrorAction SilentlyContinue
    if (-not $command) {
        $command = Get-Command soffice.exe -ErrorAction SilentlyContinue
    }
    if (-not $command) {
        throw "LibreOffice was not found. Pass soffice.com or soffice.exe with -LibreOfficePath."
    }
    $LibreOfficePath = $command.Source
}

$resolvedInput = (Resolve-Path -LiteralPath $InputPath).Path
if ([IO.Path]::GetExtension($resolvedInput) -ne ".docx") {
    throw "The input file must be a .docx file: $resolvedInput"
}

if (-not (Test-Path -LiteralPath $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
}
$resolvedOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path

# LibreOffice expects a file URI here. A raw Windows path such as C:\Temp\profile
# becomes an invalid file://C:\... value and may surface as a damaged bootstrap.ini.
$profilePath = Join-Path $env:TEMP ("igp-libreoffice-" + [guid]::NewGuid().ToString("N"))
$profileUri = ([System.Uri]::new(($profilePath + [IO.Path]::DirectorySeparatorChar))).AbsoluteUri.TrimEnd("/")

try {
    & $LibreOfficePath `
        --headless `
        --nologo `
        --nodefault `
        --nolockcheck `
        --norestore `
        "-env:UserInstallation=$profileUri" `
        --convert-to pdf `
        --outdir $resolvedOutput `
        $resolvedInput

    if ($LASTEXITCODE -ne 0) {
        throw "LibreOffice conversion failed with exit code $LASTEXITCODE."
    }

    $pdfName = [IO.Path]::GetFileNameWithoutExtension($resolvedInput) + ".pdf"
    $pdfPath = Join-Path $resolvedOutput $pdfName
    if (-not (Test-Path -LiteralPath $pdfPath -PathType Leaf)) {
        throw "LibreOffice did not create the expected PDF: $pdfPath"
    }

    Get-Item -LiteralPath $pdfPath
}
finally {
    if (Test-Path -LiteralPath $profilePath) {
        Remove-Item -LiteralPath $profilePath -Recurse -Force
    }
}
