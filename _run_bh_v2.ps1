$code = @"
new_tab("https://x.com/search?q=lana%20trading%20agent%20design&src=typed_query&f=live")
wait_for_load(8000)
tweets = js('Array.from(document.querySelectorAll("[data-testid=tweetText]")).slice(0,10).map(t=>t.innerText).join("\n---\n")')
if len(tweets) > 3000:
    print(tweets[:3000])
else:
    print(tweets)
"@

# Encode code as base64 to avoid quote issues
$bytes = [System.Text.Encoding]::UTF8.GetBytes($code)
$b64 = [Convert]::ToBase64String($bytes)

# Use a python wrapper that decodes and passes to browser-harness
python -c @"
import base64, subprocess, sys
code = base64.b64decode("$b64").decode()
result = subprocess.run(['browser-harness', '-c', code], capture_output=True, text=True, timeout=60)
print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
if result.stderr:
    print('STDERR:', result.stderr[-1000:])
"@
