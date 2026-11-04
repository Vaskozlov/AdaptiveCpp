@echo off
setlocal
if defined ACPP_PYTHON (
  "%ACPP_PYTHON%" "%~dp0acpp" %*
) else (
  python "%~dp0acpp" %*
)
exit /b %errorlevel%
