import subprocess, sys

code = '''
new_tab("https://x.com/crypto_pumpman/status/2048686836126790003")
wait_for_load(10000)
js("window.scrollTo(0, 500)")
wait_for_load(3000)
tweets = js('Array.from(document.querySelectorAll("[data-testid=tweetText]")).map((t,i)=>t.innerText).join("\\n---\\n")')
if tweets:
    print(tweets[:5000])
else:
    print("NO TWEETS")
print("TITLE:", js("document.title"))
'''

proc = subprocess.Popen(
    ['browser-harness', '-c', code],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
stdout, stderr = proc.communicate(timeout=30)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(stdout.decode('utf-8', errors='replace')[:5000])
