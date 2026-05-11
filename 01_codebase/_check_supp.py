"""Fix supplementary — wrap sync ccxt calls in to_thread"""
path = r"C:\Users\young\.openclaw\workspace\01_codebase\vulpes_trader\data\supplementary.py"
with open(path, encoding="utf-8") as f:
    c = f.read()

# Show the current fetch_open_interest method
idx = c.find("async def fetch_open_interest")
print("=== fetch_open_interest ===")
print(c[idx:idx+400])

print("\n=== fetch_funding_rate ===")
idx2 = c.find("async def fetch_funding_rate")
print(c[idx2:idx2+400])
