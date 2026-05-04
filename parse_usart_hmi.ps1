param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [string]$ExtractDir
)

$ErrorActionPreference = 'Stop'

function Get-AsciiPreview {
    param(
        [byte[]]$Bytes
    )

    return ([Text.Encoding]::ASCII.GetString($Bytes)).Trim([char]0)
}

function Get-HexString {
    param(
        [byte[]]$Bytes
    )

    return ($Bytes | ForEach-Object { $_.ToString('X2') }) -join ' '
}

function Get-SafeFileName {
    param(
        [string]$Name,
        [int]$Index
    )

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return "entry_$Index.bin"
    }

    $chars = foreach ($c in $Name.ToCharArray()) {
        if (($c -ge '0' -and $c -le '9') -or
            ($c -ge 'A' -and $c -le 'Z') -or
            ($c -ge 'a' -and $c -le 'z') -or
            $c -in '.', '_', '-') {
            $c
        } else {
            '_'
        }
    }

    $safe = (-join $chars).Trim('_')
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return "entry_$Index.bin"
    }

    return $safe
}

$fullPath = (Resolve-Path -LiteralPath $Path).Path
$bytes = [IO.File]::ReadAllBytes($fullPath)
$count = [BitConverter]::ToUInt32($bytes, 0)

$entries = @()
for ($i = 0; $i -lt $count; $i++) {
    $base = 4 + (28 * $i)
    $nameBytes = $bytes[$base..($base + 15)]
    $offset = [BitConverter]::ToUInt32($bytes, $base + 16)
    $length = [BitConverter]::ToUInt32($bytes, $base + 20)
    $field3 = [BitConverter]::ToUInt32($bytes, $base + 24)

    $entries += [pscustomobject]@{
        Index = $i
        DirOffset = ('0x{0:X}' -f $base)
        Name = Get-AsciiPreview -Bytes $nameBytes
        NameHex = Get-HexString -Bytes $nameBytes
        DataOffset = $offset
        DataOffsetHex = ('0x{0:X8}' -f $offset)
        Length = $length
        Field3 = ('0x{0:X8}' -f $field3)
        InFile = (($offset + $length) -le $bytes.Length)
    }
}

$entries | Format-Table Index, DirOffset, Name, DataOffsetHex, Length, Field3, InFile -AutoSize

if ($ExtractDir) {
    $resolvedExtractDir = [IO.Path]::GetFullPath($ExtractDir)
    [IO.Directory]::CreateDirectory($resolvedExtractDir) | Out-Null

    foreach ($entry in $entries) {
        if (-not $entry.InFile -or $entry.Length -eq 0) {
            continue
        }

        $safeName = Get-SafeFileName -Name $entry.Name -Index $entry.Index

        $data = $bytes[$entry.DataOffset..($entry.DataOffset + $entry.Length - 1)]
        $outPath = Join-Path $resolvedExtractDir $safeName

        if ($safeName -like '*.s' -or $safeName -like '*.txt' -or $safeName -like '*.pa') {
            [IO.File]::WriteAllBytes($outPath, $data)
        } else {
            [IO.File]::WriteAllBytes($outPath, $data)
        }

        if ($safeName -eq 'Program.s') {
            $utf8Path = Join-Path $resolvedExtractDir 'Program_utf8.txt'
            [IO.File]::WriteAllText($utf8Path, [Text.Encoding]::UTF8.GetString($data), [Text.Encoding]::UTF8)
        }
    }

    Write-Host ""
    Write-Host "Extracted to: $resolvedExtractDir"
}
