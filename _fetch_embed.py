import subprocess, sys

code = '''
ensure_real_tab()
new_tab("https://platform.twitter.com/embed/Tweet.html?id=2048686836126790003")
wait_for_load(8000)
body = js("document.body.innerText")
print("BODY:", body[:5000])
'''

proc = subprocess.run(
    ['browser-harness', '-c', code],
    capture_output=True, text=False, timeout=20
)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(proc.stdout.decode('utf-8', errors='replace')[:6000])
