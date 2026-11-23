$ErrorActionPreference = "Stop"
$r = "D:\Documents\deepseek-harness\default-workspace\radiology_rag"
$work = "D:\Documents\deepseek-harness\default-workspace\_gh_push"
$py = "D:\Program Files\Python312\python.exe"

# 1. fetch the archive from the instance
& $py "$r\tools\rsh.py" get /dev/shm/rrsi_code_results_20261119_20261121.tar.gz "$r\results\rrsi_code_results_20261119_20261121.tar.gz"

# 2. clone fresh through the tunnel
$env:GIT_SSH_COMMAND = 'ssh -i "C:\Users\' + $env:USERNAME + '\.ssh\medrax_deploy_key" -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -p 2222'
if (Test-Path $work) { Remove-Item -LiteralPath $work -Recurse -Force }
git clone --depth 1 ssh://git@127.0.0.1:2222/cw462/MedRAX-reproduction.git $work 2>&1 | Select-Object -Last 5
Write-Output "=== clone head ==="
git -C $work log --oneline -2
git -C $work ls-files | Measure-Object | Select-Object -ExpandProperty Count
