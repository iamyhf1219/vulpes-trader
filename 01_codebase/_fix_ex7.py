"""修复 ExchangeConnector fetch_open_orders — 传空 params"""
path = r"C:\Users\young\.openclaw\workspace\01_codebase\vulpes_trader\execution\exchange_connector.py"
with open(path, encoding="utf-8") as f:
    c = f.read()

# fix fetch_open_orders
c = c.replace(
    'async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:\n        return await self._call_with_retry("fetch_open_orders", symbol)',
    'async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:\n        return await self._call_with_retry("fetch_open_orders", symbol, {})',
    1,
)

with open(path, "w", encoding="utf-8") as f:
    f.write(c)
print("Done")
