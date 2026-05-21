$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\apps\backend"
python -m compileall app
pytest
Pop-Location

Push-Location "$PSScriptRoot\..\apps\frontend"
npm run lint
npm test
npm run build
Pop-Location

docker compose config --quiet

