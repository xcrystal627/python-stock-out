
# argment
Param(
    [parameter(mandatory=$true)][ValidateSet("yshop", "rakuten", "au")][String]$ArgMall,
    [parameter(mandatory=$true)][ValidateSet("producer", "consumer")][String]$ArgTaskType,
    [parameter(mandatory=$true)][Int]$ArgTaskNo
)
Write-Host $ArgMall
Write-Host $ArgTaskType
Write-Host $ArgTaskNo

# get directory of my file
$CurrentDir = Split-Path $MyInvocation.MyCommand.Path

# ディレクトリに移動
cd $CurrentDir

# venv activate
$VenvActivate = Join-Path $CurrentDir ".venv" | Join-Path -ChildPath "Scripts" | Join-Path -ChildPath "Activate.ps1"
Invoke-Expression $venvActivate

# pythonファイルまでディレクトリ移動
$PyDir = Join-Path $CurrentDir "app"
cd $PyDir

# python実行
$execFile = "stockout_${ArgMall}_${ArgTaskType}.py"
python $execFile --task_no $ArgTaskNo

deactivate
cd $CurrentDir