"""The public demo's head: Vercel Web Analytics, Speed Insights and the link preview. Only there: the README promises a copy
you run has no analytics."""
from pathlib import Path

DEMO_ONLY = ("/_vercel/insights/script.js", "/_vercel/speed-insights/script.js", 'property="og:image"')


def test_the_tags_are_only_on_the_vercel_demo(client, monkeypatch):
    for env, expected in (({}, False), ({"VERCEL": "1"}, False), ({"DEMO": "1"}, False), ({"VERCEL": "1", "DEMO": "1"}, True)):
        for key in ("VERCEL", "DEMO"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        html = client.get("/").get_data(as_text=True)
        assert all((tag in html) is expected for tag in DEMO_ONLY), env


def test_the_preview_image_ships_with_the_static_files():
    assert (Path(__file__).parent.parent / "static" / "og-demo.png").is_file()
