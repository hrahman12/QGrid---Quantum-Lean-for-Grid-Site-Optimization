# Usage: .\run.ps1 setup|validate|test|pipeline [site.json]|demo
param([Parameter(Mandatory)][ValidateSet('setup','validate','test','pipeline','demo')][string]$Target, [string]$Site)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
switch ($Target) {
  'setup'    { python -m venv .venv; & $py -m pip install -r requirements.txt }
  'validate' { & $py scripts/validate.py }
  'test'     { & $py -m pytest -q }
  'pipeline' { if ($Site) { & $py pipeline.py $Site } else { & $py pipeline.py } }
  'demo'     {
    $env:QSITE_OFFLINE = '1'; $env:PYTHONUTF8 = '1'
    foreach ($cmd in 'pipeline.py', 'scenarios/edge_alviso.py', 'scenarios/growth_alviso.py', 'report/summary.py') {
      & $py $cmd; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
  }
}
exit $LASTEXITCODE
