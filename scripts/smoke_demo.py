"""End-to-end smoke check against the local Docker demo, using a real cookie jar."""

import http.cookiejar
import re
import urllib.parse
import urllib.request

base = "http://127.0.0.1:5000"
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
with client.open(base + "/readyz", timeout=10) as response:
    assert response.status == 200
with client.open(base + "/login", timeout=10) as response:
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.read().decode()).group(1)
data = urllib.parse.urlencode({"email": "demo@example.com", "password": "Demo@12345", "csrf_token": token}).encode()
with client.open(base + "/login", data=data, timeout=30) as response:
    assert response.url.endswith("/dashboard"), "Demo authentication failed"
for path in [
    "/dashboard",
    "/perfil",
    "/configuracoes",
    "/categorias",
    "/contas",
    "/movimentacoes",
    "/previsoes",
    "/cartoes",
    "/dividas",
    "/caixinhas",
]:
    with client.open(base + path, timeout=30) as response:
        assert response.status == 200 and "/login" not in response.url, path
print("Demo authentication, readiness and 10 populated pages passed.")
