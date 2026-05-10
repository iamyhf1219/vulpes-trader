import subprocess, json

code = 'info = page_info(); print(str(info))'
result = subprocess.run(['browser-harness', '-c', code], capture_output=True, text=False, timeout=15)
stdout = result.stdout.decode('utf-8', errors='replace')
print(stdout)
