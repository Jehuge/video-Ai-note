import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import model
from app.services import model_provider


class ModelProviderTests(unittest.TestCase):
    def test_normalize_provider_type_accepts_instance_id_and_provider_type(self):
        self.assertEqual(model_provider.normalize_provider_type("instance-1", "deepseek"), "deepseek")
        self.assertEqual(model_provider.normalize_provider_type("ollama", "openai"), "ollama")

    def test_ollama_base_url_adds_openai_v1_path(self):
        self.assertEqual(
            model_provider.normalize_base_url("ollama", "http://127.0.0.1:11434"),
            "http://127.0.0.1:11434/v1",
        )

    def test_openai_compatible_root_base_url_adds_v1_path(self):
        self.assertEqual(
            model_provider.normalize_base_url("custom", "https://guodongapi.site"),
            "https://guodongapi.site/v1",
        )
        self.assertEqual(
            model_provider.normalize_base_url("openai", "https://guodongapi.site/"),
            "https://guodongapi.site/v1",
        )
        self.assertEqual(
            model_provider.normalize_base_url("deepseek", ""),
            "https://api.deepseek.com/v1",
        )

    def test_openai_compatible_base_url_with_existing_path_is_unchanged(self):
        self.assertEqual(
            model_provider.normalize_base_url("custom", "https://guodongapi.site/v1"),
            "https://guodongapi.site/v1",
        )
        self.assertEqual(
            model_provider.normalize_base_url("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(
            model_provider.normalize_base_url("volcengine", ""),
            "https://ark.cn-beijing.volces.com/api/v3",
        )

    def test_model_list_returns_error_when_provider_request_fails(self):
        with mock.patch.object(model, "create_openai_client", side_effect=RuntimeError("network down")):
            with self.assertRaises(model.HTTPException) as ctx:
                model.get_openai_compatible_models(
                    provider_type="deepseek",
                    api_key="sk-test",
                    base_url="https://api.deepseek.com",
                    provider_instance_id="instance-1",
                )

        self.assertIn("获取模型列表失败", ctx.exception.detail)
        self.assertNotIn("deepseek-chat", ctx.exception.detail)

    def test_model_list_returns_exact_remote_models_without_provider_keyword_filter(self):
        fake_client = mock.Mock()
        fake_client.models.list.return_value.data = [
            mock.Mock(id="provider-new-live-model"),
            mock.Mock(id="another-real-model"),
        ]

        with mock.patch.object(model, "create_openai_client", return_value=fake_client):
            response = model.get_openai_compatible_models(
                provider_type="deepseek",
                api_key="sk-test",
                base_url="https://api.deepseek.com",
                provider_instance_id="instance-1",
            )

        self.assertEqual(response["code"], 200)
        ids = [item["id"] for item in response["data"]]
        self.assertEqual(ids, ["provider-new-live-model", "another-real-model"])
        self.assertEqual(response["data"][0]["provider"], "instance-1")

    def test_model_list_uses_normalized_openai_compatible_base_url(self):
        fake_client = mock.Mock()
        fake_client.models.list.return_value.data = [mock.Mock(id="gpt-5.5")]

        with mock.patch.object(model, "create_openai_client", return_value=fake_client) as create_client:
            response = model.get_openai_compatible_models(
                provider_type="custom",
                api_key="sk-test",
                base_url="https://guodongapi.site",
                provider_instance_id="instance-1",
            )

        self.assertEqual(response["code"], 200)
        create_client.assert_called_once_with(api_key="sk-test", base_url="https://guodongapi.site/v1")


if __name__ == "__main__":
    unittest.main()
