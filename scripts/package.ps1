$ErrorActionPreference = "Stop"

$root = Resolve-Path "$PSScriptRoot\.."
$zip = Join-Path $root "logiq-platform-production.zip"
$staging = Join-Path $env:TEMP ("logiq-package-" + [guid]::NewGuid().ToString("N"))

if (Test-Path $zip) {
  Remove-Item $zip -Force
}

$exclude = @(
  "\.git$",
  "\\node_modules($|\\)",
  "\\.next($|\\)",
  "\\__pycache__($|\\)",
  "\\.pytest_cache($|\\)",
  "\\.ruff_cache($|\\)",
  "\\coverage($|\\)",
  "\\playwright-report($|\\)",
  "\\test-results($|\\)",
  "logiq-platform-production\.zip$"
)

New-Item -ItemType Directory -Path $staging | Out-Null
Get-ChildItem -Path $root -Recurse -Force | ForEach-Object {
  $relative = $_.FullName.Substring($root.Path.Length).TrimStart("\")
  $skip = $false
  foreach ($pattern in $exclude) {
    if ($_.FullName -match $pattern) {
      $skip = $true
      break
    }
  }
  if (-not $skip) {
    $target = Join-Path $staging $relative
    if ($_.PSIsContainer) {
      New-Item -ItemType Directory -Path $target -Force | Out-Null
    } else {
      New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
      Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
  }
}

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zip -Force
Remove-Item $staging -Recurse -Force
Write-Output $zip
