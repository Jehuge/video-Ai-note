import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import openai_client


class OpenAIClientTests(unittest.TestCase):
    def test_http_client_disables_environment_proxy_without_proxy_argument(self):
        with mock.patch.object(openai_client.httpx, "Client") as fake_client:
            openai_client.create_openai_http_client(timeout=30)

        kwargs = fake_client.call_args.kwargs
        self.assertEqual(kwargs["trust_env"], False)
        self.assertNotIn("proxy", kwargs)
        self.assertNotIn("proxies", kwargs)

    def test_openai_client_uses_shared_http_client(self):
        fake_http_client = object()
        with mock.patch.object(openai_client, "create_openai_http_client", return_value=fake_http_client), \
                mock.patch.object(openai_client, "OpenAI") as fake_openai:
            openai_client.create_openai_client(
                api_key="sk-test",
                base_url="https://api.example.test/v1",
                timeout=12,
            )

        self.assertEqual(fake_openai.call_args.kwargs["api_key"], "sk-test")
        self.assertEqual(fake_openai.call_args.kwargs["base_url"], "https://api.example.test/v1")
        self.assertIs(fake_openai.call_args.kwargs["http_client"], fake_http_client)


if __name__ == "__main__":
    unittest.main()
