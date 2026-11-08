# Usage: .\run.ps1 setup|validate|test|pipeline [site.json]
param([Parameter(Mandatory)][ValidateSet('setup','validate','test','pipeline')][string]$Target, [string]$Site)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
switch ($Target) {
  'setup'    { python -m venv .venv; & $py -m pip install -r requirements.txt }
  'validate' { & $py scripts/validate.py }
  'test'     { & $py -m pytest -q }
  'pipeline' { if ($Site) { & $py pipeline.py $Site } else { & $py pipeline.py } }
}
exit $LASTEXITCODE
