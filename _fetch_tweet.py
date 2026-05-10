import subprocess, sys

code = '''
new_tab("https://x.com/crypto_pumpman/status/2048686836126790003")
wait_for_load(10000)
js("window.scrollTo(0, 300)")
wait_for_load(3000)
info = page_info()
print("URL:", info.get("url"))
print("TITLE:", info.get("title"))
tweets = js("Array.from(document.querySelectorAll('[data-testid=tweetText]')).map((t,i)=>'TWEET '+(i+1)+': '+t.innerText).join('\\n---\\n')")
print(tweets[:5000] if tweets else "NO TWEETS")
'''

proc = subprocess.Popen(
    ['browser-harness', '-c', code],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
stdout, stderr = proc.communicate(timeout=30)
out = stdout.decode('utf-8', errors='replace')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(out[:5000])
if stderr:
    err = stderr.decode('utf-8', errors='replace')
    print('ERR:', err[:300])
