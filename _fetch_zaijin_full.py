import subprocess, sys, json

code = r'''
new_tab("https://x.com/zaijin338191/status/2048769757571375110")
wait_for_load(10000)
js("window.scrollTo(0, 400)")
wait_for_load(3000)
tweets = js("Array.from(document.querySelectorAll('[data-testid=tweetText]')).map((t,i)=>'T'+i+': '+t.innerText).join('\n===\n')")
print("TWEETS:", tweets[:5000] if tweets else "NONE")
'''

proc = subprocess.run(['browser-harness', '-c', code], capture_output=True, text=False, timeout=30)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(proc.stdout.decode('utf-8', errors='replace')[:6000])
