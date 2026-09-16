param([string]$ProjectDir)

if (-not $ProjectDir) { $ProjectDir = Split-Path -Parent $PSScriptRoot }
$target = Join-Path $ProjectDir '.env'
if (Test-Path -LiteralPath $target) { return }

$defaults = @{
    YINGDAO_API_BASE_URL = 'https://api.yingdao.com'
    CODEX_CLI_PATH = 'codex'
    CODEX_MODEL = 'gpt-5.6-luna'
}
$names = @(
    'YINGDAO_API_BASE_URL','YINGDAO_ACCESS_KEY_ID','YINGDAO_ACCESS_KEY_SECRET',
    'CODEX_CLI_PATH','CODEX_SESSION_ID','CODEX_MODEL',
    'LARK_CLI_PS1','YINGDAO_ROSTER_CALENDAR_ID','PYTASKGANTT_API_URL','DATABASE_URL'
)
$lines = @('# 自动生成的本机配置；不要提交到 Git。')
foreach ($name in $names) {
    $value = [Environment]::GetEnvironmentVariable($name, 'User')
    if ([string]::IsNullOrWhiteSpace($value) -and $defaults.ContainsKey($name)) { $value = $defaults[$name] }
    if ($null -eq $value) { $value = '' }
    $lines += "$name=$value"
}
[IO.File]::WriteAllLines($target, $lines, (New-Object Text.UTF8Encoding($true)))
