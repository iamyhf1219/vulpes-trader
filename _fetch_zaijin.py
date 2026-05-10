import subprocess, sys

code = '''
new_tab("https://x.com/zaijin338191/status/2048769757571375110")
wait_for_load(15000)
js("window.scrollTo(0, 200)")
wait_for_load(3000)
tweets = js('Array.from(document.querySelectorAll("[data-testid=tweetText]")).map((t,i)=>i+": "+t.innerText).join("\\n---\\n")')
if tweets and len(tweets) > 0:
    print("TWEETS:", tweets[:5000])
else:
    print("NO_TWEETS")
print("TITLE:", js("document.title"))
'''

proc = subprocess.run(
    ['browser-harness', '-c', code],
    capture_output=True, text=False, timeout=30
)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(proc.stdout.decode('utf-8', errors='replace')[:6000])
