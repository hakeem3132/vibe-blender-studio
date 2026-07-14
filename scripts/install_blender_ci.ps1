$ErrorActionPreference = "Stop"
$Version = "4.2.15"
$Archive = "blender-$Version-windows-x64.zip"
$Sha256 = "e17c122edb011159bb825e2fba2118e232ba61e47ba610e116e743d5a7798d42"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Cache = if ($env:VIBE_BLENDER_CACHE) { $env:VIBE_BLENDER_CACHE } else { Join-Path $Root ".runtime\blender" }
$Url = "https://download.blender.org/release/Blender4.2/$Archive"
New-Item -ItemType Directory -Force -Path $Cache | Out-Null
$ArchivePath = Join-Path $Cache $Archive
if (-not (Test-Path $ArchivePath)) { Invoke-WebRequest -Uri $Url -OutFile $ArchivePath }
if ((Get-FileHash -Algorithm SHA256 $ArchivePath).Hash.ToLowerInvariant() -ne $Sha256) { throw "Blender checksum mismatch" }
$Destination = Join-Path $Cache "blender-$Version-windows-x64"
if (-not (Test-Path (Join-Path $Destination "blender.exe"))) { Expand-Archive -Path $ArchivePath -DestinationPath $Cache -Force }
Write-Output (Join-Path $Destination "blender.exe")
