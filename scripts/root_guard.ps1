#!/usr/bin/env pwsh
# root_guard.ps1
# R240-0D: Enforce the single valid development root.
# Exit codes: 0 = ROOT_OK, 1 = FORBIDDEN/WRONG_ROOT

$ErrorActionPreference = "Stop"

$EXPECTED_ROOT = "E:\OpenClaw-Base\deerflow"

# Build the Chinese directory name from Unicode codepoints so the script remains
# stable when Windows PowerShell reads this file without a UTF-8 BOM.
$OLD_ROOT_NAME = "openclaw" + `
    [string][char]0x8D85 + `
    [string][char]0x7EA7 + `
    [string][char]0x5DE5 + `
    [string][char]0x7A0B + `
    [string][char]0x9879 + `
    [string][char]0x76EE

$FORBIDDEN_ROOT_PREFIX = Join-Path "E:\OpenClaw-Base" $OLD_ROOT_NAME
$FORBIDDEN_MIGRATED_PREFIX = $FORBIDDEN_ROOT_PREFIX + "__MIGRATED_DO_NOT_USE"

function Normalize-RootPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
        $fullPath = $resolved.ProviderPath
    } catch {
        $fullPath = [System.IO.Path]::GetFullPath($Path)
    }

    return $fullPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}

function Test-IsSameOrChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$CurrentPath,
        [Parameter(Mandatory = $true)][string]$RootPath
    )

    $comparison = [System.StringComparison]::OrdinalIgnoreCase
    if ([string]::Equals($CurrentPath, $RootPath, $comparison)) {
        return $true
    }

    $rootWithSeparator = $RootPath + [System.IO.Path]::DirectorySeparatorChar
    return $CurrentPath.StartsWith($rootWithSeparator, $comparison)
}

$CURRENT_DIR = Normalize-RootPath -Path $PWD.Path
$EXPECTED_ROOT_NORM = Normalize-RootPath -Path $EXPECTED_ROOT
$FORBIDDEN_ROOT_NORM = Normalize-RootPath -Path $FORBIDDEN_ROOT_PREFIX
$FORBIDDEN_MIGRATED_NORM = Normalize-RootPath -Path $FORBIDDEN_MIGRATED_PREFIX

if ((Test-IsSameOrChildPath -CurrentPath $CURRENT_DIR -RootPath $FORBIDDEN_ROOT_NORM) -or
    (Test-IsSameOrChildPath -CurrentPath $CURRENT_DIR -RootPath $FORBIDDEN_MIGRATED_NORM)) {
    Write-Host "[RootGuard] FORBIDDEN"
    Write-Host "[RootGuard] Current: $CURRENT_DIR"
    Write-Host "[RootGuard] Expected root: $EXPECTED_ROOT_NORM"
    Write-Host "[RootGuard] Please open: $EXPECTED_ROOT_NORM\OpenClaw-DeerFlow.code-workspace"
    exit 1
}

if (-not (Test-IsSameOrChildPath -CurrentPath $CURRENT_DIR -RootPath $EXPECTED_ROOT_NORM)) {
    Write-Host "[RootGuard] WRONG_ROOT"
    Write-Host "[RootGuard] Current: $CURRENT_DIR"
    Write-Host "[RootGuard] Expected root: $EXPECTED_ROOT_NORM"
    exit 1
}

Write-Host "[RootGuard] ROOT_OK"
Write-Host "[RootGuard] Root: $EXPECTED_ROOT_NORM"
exit 0
