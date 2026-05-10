import subprocess, sys

code = '''
new_tab("https://dogdoing.ai/")
wait_for_load(10000)
js("window.scrollTo(0, 300)")
wait_for_load(3000)
print(js("document.body.innerText.substring(0, 6000)"))
'''

proc = subprocess.Popen(
    ['browser-harness', '-c', code],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
stdout, stderr = proc.communicate(timeout=30)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print(stdout.decode('utf-8', errors='replace'))
