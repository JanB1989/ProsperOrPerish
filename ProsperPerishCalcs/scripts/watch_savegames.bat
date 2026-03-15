@echo off
cd /d "%~dp0.."
uv run python -m analysis.savegame
pause
