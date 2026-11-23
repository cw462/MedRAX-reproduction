$ErrorActionPreference = "Continue"
$work = "D:\Documents\deepseek-harness\default-workspace\_gh_push"
$env:GIT_TERMINAL_PROMPT = "0"
$env:GIT_SSH_COMMAND = 'ssh -i "C:\Users\' + $env:USERNAME + '\.ssh\medrax_deploy_key" -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o BatchMode=yes -p 2222'

if (Test-Path $work) { Remove-Item -LiteralPath $work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $work | Out-Null
git -C $work init -q 2>&1 | Out-Null
git -C $work remote add origin ssh://git@127.0.0.1:2222/cw462/MedRAX-reproduction.git

foreach ($b in @("reports/m5-rrsi-acc-ttl-v4-preliminary-20261120",
                 "reports/m5-rrsi-s10-val100-20261120",
                 "reports/m5-rsi-data8-development-aggregate-20261118")) {
    Write-Output "=== $b ==="
    git -C $work fetch -q --depth 1 origin $b 2>&1 | Select-Object -First 3
    $files = git -C $work ls-tree -r --name-only FETCH_HEAD 2>&1
    Write-Output ("files: " + ($files | Measure-Object).Count)
    $files | Select-Object -First 25
    Write-Output ""
}
