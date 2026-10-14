def test_authenticated_main_pages_render(authenticated_client):
    paths = [
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
    ]

    for path in paths:
        response = authenticated_client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_anonymous_user_is_redirected_from_dashboard(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
