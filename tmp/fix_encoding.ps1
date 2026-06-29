$file = 'E:\MiroFish\backend\app\services\simulation_config_generator.py'
$text = [System.IO.File]::ReadAllText($file, [System.Text.Encoding]::UTF8)

$replacements = @{
    [char]0xFF1A = ':'   # ：
    [char]0xFF1B = ';'   # ；
    [char]0xFF01 = '!'   # ！
    [char]0xFF1F = '?'   # ？
    [char]0x3002 = '.'   # 。
    [char]0xFF08 = '('   # （
    [char]0xFF09 = ')'   # ）
    [char]0xFF0C = ','   # ，
    [char]0x3001 = ','   # 、
    [char]0x2018 = "'"   # '
    [char]0x2019 = "'"   # '
    [char]0x201C = '"'   # "
    [char]0x201D = '"'   # "
    [char]0x2014 = '--'  # —
}

$count = 0
foreach ($kvp in $replacements.GetEnumerator()) {
    $orig = $kvp.Key
    $new = $kvp.Value
    $c = 0
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $text.ToCharArray()) {
        if ($ch -eq $orig) {
            $null = $sb.Append($new)
            $c++
        } else {
            $null = $sb.Append($ch)
        }
    }
    if ($c -gt 0) {
        $text = $sb.ToString()
        $count += $c
        Write-Host "Replaced $c of '$orig' (0x$('{0:X4}' -f ([int]$orig)))"
    }
}

[System.IO.File]::WriteAllText($file, $text, [System.Text.Encoding]::UTF8)
Write-Host "Total: $count replacements"
