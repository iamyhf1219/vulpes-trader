import subprocess, sys

code = '''
ensure_real_tab()
new_tab("https://x.com/crypto_pumpman")
wait_for_load(10000)
info = page_info()
print("URL:", info.get("url"))
print("TITLE:", info.get("title", ""))
'''

proc = subprocess.run(
    ['browser-harness', '-c', code],
    capture_output=True, text=False, timeout=30
)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(proc.stdout.decode('utf-8', errors='replace'))
