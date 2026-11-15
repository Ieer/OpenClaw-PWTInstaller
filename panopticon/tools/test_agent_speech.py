import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import error, request

from agent_speech import ASR_URL, LEGACY_ASR_URL, MAX_BYTES, TTS_BASE_URL, TTS_VOICE, agent_speech_batch, authenticate_speech, create_server, prepare_agents, prepare_credentials, prepare_tts_config, speech_input, speech_principals, transcribe_file


class AgentSpeechTests(unittest.TestCase):
    def test_shared_name_and_legacy_client_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, url in enumerate((ASR_URL, LEGACY_ASR_URL)):
                client = root / f"client-{index}.json"
                destination = root / f"batch-{index}.json"
                client.write_text(json.dumps({"url": url, "token": "t" * 40}))
                prepare_tts_config(client, destination)
                self.assertEqual(json.loads(destination.read_text())[1]["value"]["baseUrl"], TTS_BASE_URL)
        config = {"gateway": {"trustedProxies": ["172.21.0.16"]}}
        batch = agent_speech_batch(config, "t" * 40, "172.21.0.16")
        self.assertEqual(batch[0]["value"][0]["args"][0], "/home/node/.openclaw/voice/agent_speech.py")

    def test_role_preparation_preserves_owners_and_issues_only_local_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "homes" / "growth"
            home.mkdir(parents=True)
            config = {"agents": {"entries": {"growth": {}, "growth-heavy": {}, "growth-light": {}}},
                      "gateway": {"trustedProxies": ["172.21.0.15"]}}
            (home / "openclaw.json").write_text(json.dumps(config))
            service = root / "server.json"
            service.write_text(json.dumps({"token": "p" * 40, "api_key": "private-provider"}))
            report = prepare_agents(service, root / "homes", ["growth"], "172.21.0.16", "123")
            self.assertEqual(report[0]["agent"], "growth")
            self.assertEqual(json.loads((home / "openclaw.json").read_text()), config)
            client = json.loads((home / "voice/speech-client.json").read_text())
            self.assertNotIn("api_key", client)
            self.assertNotEqual(client["token"], "p" * 40)
            self.assertEqual(json.loads(service.read_text())["token"], "p" * 40)
            batch = json.loads((home / "voice/speech-batch-123.json").read_text())
            self.assertTrue(all(not item["path"].startswith(("agents", "models", "channels", "plugins")) for item in batch))

    def test_existing_custom_speech_or_proxy_is_not_overwritten(self):
        for config in ({"tts": {"provider": "custom"}}, {"gateway": {"trustedProxies": ["10.0.0.2"]}}):
            with self.assertRaises(ValueError):
                agent_speech_batch(config, "t" * 40, "172.21.0.16")

    def test_eight_roles_use_distinct_tokens_and_legacy_personal_is_preserved(self):
        agents = ["nox", "metrics", "growth", "email", "writing", "health", "trades"]
        credentials = {"token": "personal-" + "a" * 40,
                       "tokens": {agent: agent + "-" + "b" * 40 for agent in agents}}
        principals = speech_principals(credentials)
        self.assertEqual(len(principals), 8)
        for agent, token in principals.items():
            self.assertEqual(authenticate_speech("Bearer " + token, principals), agent)
        self.assertIsNone(authenticate_speech("Bearer unknown", principals))
        with self.assertRaises(ValueError):
            speech_principals({"token": "a" * 40, "tokens": {"health": "a" * 40}})
        with self.assertRaises(ValueError):
            speech_principals({"token": "a" * 40, "tokens": {"unknown": "b" * 40}})

    def test_native_tts_config_targets_only_internal_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = root / "client.json"
            destination = root / "batch.json"
            client.write_text(json.dumps({"url": ASR_URL, "token": "t" * 40}))
            prepare_tts_config(client, destination)
            operations = json.loads(destination.read_text())
            self.assertEqual([item["path"] for item in operations],
                             ["tts.provider", "tts.providers.openai", "tts.providers.microsoft.enabled"])
            self.assertEqual(operations[1]["value"]["baseUrl"], TTS_BASE_URL)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_tts_contract_rejects_unbounded_or_unknown_outputs(self):
        body = {"model": "local-edge", "voice": TTS_VOICE, "input": "fixed text", "response_format": "mp3"}
        self.assertEqual(speech_input(body), "fixed text")
        for change in ({"input": "x" * 1001}, {"voice": "other"}, {"model": "other"}, {"response_format": "wav"}):
            with self.assertRaises(ValueError):
                speech_input({**body, **change})

    def test_tts_endpoint_requires_token_and_returns_audio(self):
        calls = []
        credentials = {"token": "test-" + "a" * 40, "api_key": "test-only"}
        def fake_synthesizer(text):
            calls.append(text)
            return b"fixed-mp3"
        server = create_server(credentials, host="127.0.0.1", port=0, synthesizer=fake_synthesizer)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/v1/audio/speech"
        body = json.dumps({"model": "local-edge", "voice": TTS_VOICE, "input": "fixed text"}).encode()
        try:
            with self.assertRaises(error.HTTPError) as denied:
                request.urlopen(request.Request(url, data=body))
            self.assertEqual(denied.exception.code, 403)
            with request.urlopen(request.Request(url, data=body, headers={"Authorization": "Bearer " + credentials["token"]})) as response:
                self.assertEqual(response.headers["Content-Type"], "audio/mpeg")
                self.assertEqual(response.read(), b"fixed-mp3")
            self.assertEqual(calls, ["fixed text"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_private_projection_does_not_expose_provider_key_to_client(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.yaml"
            source.write_text("tongyi_api_key: test-provider-key\noline_asr_model: paraformer-realtime-8k-v2\n")
            destination = root / "server.json"
            client = root / "client.json"
            prepare_credentials(source, destination, client)
            server_value = json.loads(destination.read_text())
            client_value = json.loads(client.read_text())
            self.assertEqual(server_value["token"], client_value["token"])
            self.assertNotIn("api_key", client_value)
            self.assertEqual(client.stat().st_mode & 0o777, 0o600)
            prepare_credentials(source, destination, client)
            self.assertEqual(json.loads(client.read_text())["token"], client_value["token"])

    def test_credential_scope_input_budget_and_single_transcription(self):
        calls = []
        credentials = {"token": "test-" + "a" * 40, "api_key": "test-only", "model": "paraformer-realtime-8k-v2"}
        def fake_recognizer(audio, config):
            calls.append(audio)
            return "fixed test"
        server = create_server(credentials, host="127.0.0.1", port=0, recognizer=fake_recognizer)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/asr"
        try:
            with self.assertRaises(error.HTTPError) as rejected:
                request.urlopen(request.Request(url, data=b"audio"))
            self.assertEqual(rejected.exception.code, 403)
            with tempfile.TemporaryDirectory() as directory:
                audio = Path(directory) / "test.audio"
                audio.write_bytes(b"fixed audio")
                self.assertEqual(transcribe_file(audio, {"url": url, "token": credentials["token"]}), "fixed test")
                audio.write_bytes(b"x" * (MAX_BYTES + 1))
                with self.assertRaises(ValueError):
                    transcribe_file(audio, {"url": url, "token": credentials["token"]})
            self.assertEqual(calls, [b"fixed audio"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_cli_does_not_send_audio_to_arbitrary_url(self):
        with self.assertRaises(ValueError):
            transcribe_file(Path("/not-read"), {"url": "https://other.example/asr", "token": "not-sent"})


if __name__ == "__main__":
    unittest.main()