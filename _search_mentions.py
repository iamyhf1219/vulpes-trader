import subprocess, sys

bh_code = '''
ensure_real_tab()
new_tab("https://x.com/lanaaielsa")
wait_for_load(10000)
info = page_info()
print("URL:", info.get("url"))
print("TITLE:", info.get("title"))
count = js("document.querySelectorAll('[data-testid=tweetText]').length")
print("COUNT:", count)
# Try getting all articles
articles = js("Array.from(document.querySelectorAll('article')).map(a=>a.innerText.substring(0,300)).join('\\n===\\n')")
if count > 0:
    tweets = js("Array.from(document.querySelectorAll('[data-testid=tweetText]')).slice(0,10).map((t,i)=>'TWEET_'+(i+1)+': '+t.innerText.substring(0,500)).join('\\n---\\n')")
    print(tweets[:5000])
elif articles:
    print("ARTICLES:", articles[:3000])
else:
    print("BODY:", js("document.body.innerText")[:2000])
'''

proc = subprocess.Popen(
    ['browser-harness', '-c', bh_code],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
stdout, stderr = proc.communicate(timeout=30)
out = stdout.decode('utf-8', errors='replace')
err = stderr.decode('utf-8', errors='replace') if stderr else ''
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print('OUTPUT:', out[:5000])
print('RC:', proc.returncode)
if err:
    print('STDERR:', err[:500])
