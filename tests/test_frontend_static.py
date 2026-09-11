# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT


def test_frontend_workspace_and_modules(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200
    html = response.text
    assert '<main id="chatMain"' in html
    assert '<aside id="sidebar"' in html
    assert '<aside id="canvas"' in html
    assert 'type="module" src="/js/app.js"' in html
    assert 'role="tablist"' in html
    assert '<dialog id="sideDialog"' in html


def test_frontend_assets_are_served(auth_client):
    for path in ("/css/app.css", "/js/app.js", "/js/state.js", "/js/source.js"):
        response = auth_client.get(path)
        assert response.status_code == 200
        assert response.text


def test_frontend_avoids_unsafe_and_direct_upload_paths(auth_client):
    app = auth_client.get("/js/app.js").text
    canvas = auth_client.get("/js/canvas.js").text
    api = auth_client.get("/js/api.js").text
    combined = app + canvas + api
    assert "innerHTML" not in combined
    assert "/uploads" not in combined
    assert 'credentials: "include"' in api
    assert '"peng:auth-expired"' in api
