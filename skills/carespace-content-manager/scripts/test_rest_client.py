import json, os, unittest
import rest_client
from rest_client import RestClient, ConfigError

class FakeTransport:
    def __init__(self, pages):        # list of (status, body_str) in request order
        self.pages = list(pages); self.urls = []
    def __call__(self, method, url, headers):
        self.urls.append(url)
        return self.pages.pop(0)

def page(data, page_no, page_count):
    return 200, json.dumps({"data": data,
        "meta": {"pagination": {"page": page_no, "pageCount": page_count}}})

class TestConfig(unittest.TestCase):
    def test_resolves_from_env(self):
        os.environ["STRAPI_HOST"]="https://h"; os.environ["STRAPI_READ_TOKEN"]="T"
        c = rest_client.resolve_config()
        self.assertEqual(c, {"host":"https://h","token":"T"})
    def test_missing_raises(self):
        for k in ("STRAPI_HOST", "STRAPI_URL", "STRAPI_API_TOKEN"):
            os.environ.pop(k, None)
        with self.assertRaises(ConfigError):
            rest_client.resolve_config()
    def test_resolves_from_maestro_secret_names(self):
        saved = {k: os.environ.pop(k, None) for k in ("STRAPI_HOST", "STRAPI_READ_TOKEN")}
        try:
            os.environ["STRAPI_URL"] = "https://m/"; os.environ["STRAPI_API_TOKEN"] = "RO"
            self.assertEqual(rest_client.resolve_config(), {"host": "https://m", "token": "RO"})
        finally:
            for k in ("STRAPI_URL", "STRAPI_API_TOKEN"):
                os.environ.pop(k, None)
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

class TestGetAll(unittest.TestCase):
    def test_walks_all_pages_with_populate(self):
        ft = FakeTransport([page([{"id":1}], 1, 2), page([{"id":2}], 2, 2)])
        c = RestClient("https://h", "T", transport=ft)
        rows = c.get_all("exercises")
        self.assertEqual([r["id"] for r in rows], [1, 2])
        self.assertIn("populate", ft.urls[0])
        self.assertIn("pagination[page]=1", ft.urls[0])
        self.assertIn("pagination[page]=2", ft.urls[1])

    def test_get_one(self):
        ft = FakeTransport([(200, json.dumps({"data":{"documentId":"d1","name":"X"}}))])
        c = RestClient("https://h", "T", transport=ft)
        self.assertEqual(c.get_one("exercises","d1")["name"], "X")

    def test_structured_populate_suppresses_bare_star(self):
        ft = FakeTransport([page([{"id":1}], 1, 1)])
        c = RestClient("https://h", "T", transport=ft)
        key = "populate[exercises][populate][strapiExerciseId][fields][0]"
        c.get_all("program-templates", {key: "name"})
        url = ft.urls[0]
        self.assertIn(key, url)
        self.assertNotIn("populate=%2A", url)
        self.assertNotIn("populate=*", url)
