import subprocess, os, sys

bh_code = '''
js("window.scrollTo(0, 300)")
wait_for_load(3000)
tweets = js("Array.from(document.querySelectorAll('[data-testid=tweetText]')).slice(0,10).map((t,i)=>'TWEET '+(i+1)+': '+t.innerText.substring(0,500)).join('\\\\n---\\\\n')")
print(tweets)
'''

proc = subprocess.Popen(
    ['browser-harness', '-c', bh_code],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
stdout, stderr = proc.communicate(timeout=30)
out = stdout.decode('utf-8', errors='replace')
err = stderr.decode('utf-8', errors='replace') if stderr else ''
print(out)
if err:
    print('STDERR:', err[:500])
