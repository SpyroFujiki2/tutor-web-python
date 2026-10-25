import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings, parse_cors_origins
from app.main import create_app


class SettingsTests(unittest.TestCase):
    def test_cors_origins_are_trimmed_and_deduplicated(self):
        self.assertEqual(
            parse_cors_origins(" http://localhost:5173/, ,http://localhost:5173 "),
            ("http://localhost:5173",),
        )

    def test_invalid_cors_origins_are_rejected(self):
        for value in (
            "*", "localhost:5173", "ftp://example.com", "https://example.com/api",
            "https://user:password@example.com", "https://example.com?query=1",
            "https://example.com#fragment", "https://example.com:99999",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_cors_origins(value)

    @patch("app.core.config.dotenv_values", return_value={"CORS_ORIGINS": "https://file.example"})
    @patch.dict("os.environ", {"CORS_ORIGINS": "https://process.example"}, clear=True)
    def test_process_environment_overrides_dotenv(self, _dotenv):
        self.assertEqual(get_settings().cors_origins, ("https://process.example",))

    @patch("app.core.config.dotenv_values", return_value={"CORS_ORIGINS": "https://file.example"})
    @patch.dict("os.environ", {}, clear=True)
    def test_dotenv_is_used_without_process_override(self, _dotenv):
        self.assertEqual(get_settings().cors_origins, ("https://file.example",))

    @patch("app.core.config.dotenv_values", return_value={})
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_configuration_allows_local_development(self, _dotenv):
        self.assertEqual(
            get_settings().cors_origins,
            ("http://localhost:5173", "http://127.0.0.1:5173"),
        )

    @patch("app.core.config.dotenv_values", return_value={})
    @patch.dict("os.environ", {"CORS_ORIGINS": ""}, clear=True)
    def test_empty_configuration_disables_cross_origin_access(self, _dotenv):
        self.assertEqual(get_settings().cors_origins, ())


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(Settings(cors_origins=("http://localhost:5173",))))
        self.addCleanup(self.client.close)

    def test_health_contract(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "message": "FastAPI đang hoạt động"})

    def test_openapi_exposes_health_response_schema(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/health", schema["paths"])
        self.assertIn("HealthResponse", schema["components"]["schemas"])

    def test_allowed_origin_gets_cors_header(self):
        response = self.client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_unlisted_origin_gets_no_cors_header(self):
        response = self.client.get("/api/health", headers={"Origin": "https://unlisted.example"})
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_preflight_accepts_allowed_origin_and_method(self):
        response = self.client.options("/api/health", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_preflight_rejects_unlisted_origin(self):
        response = self.client.options("/api/health", headers={
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "GET",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
