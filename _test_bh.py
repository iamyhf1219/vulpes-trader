import subprocess, sys

# Test basic browser-harness functionality
bh_code = 'print("HELLO FROM BH")'
print(f"Running: browser-harness -c '{bh_code[:50]}...'")
sys.stdout.flush()

proc = subprocess.Popen(
    ['browser-harness', '-c', bh_code],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
stdout, stderr = proc.communicate(timeout=15)
out = stdout.decode('utf-8', errors='replace')
err = stderr.decode('utf-8', errors='replace') if stderr else ''
print("STDOUT:", repr(out))
print("STDERR:", repr(err[:200]))
print("RC:", proc.returncode)
