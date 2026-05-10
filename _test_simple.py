import subprocess, sys, os

code = "js('document.title')"

proc = subprocess.run(
    ['browser-harness', '-c', code],
    capture_output=True, text=False, timeout=15
)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print("RC:", proc.returncode)
print("OUT:", proc.stdout.decode('utf-8', errors='replace'))
print("ERR:", proc.stderr.decode('utf-8', errors='replace')[:500])
