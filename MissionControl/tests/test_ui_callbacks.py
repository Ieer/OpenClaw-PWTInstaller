import importlib.util
import gzip
import json
import sys
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from dash import no_update


spec = importlib.util.spec_from_file_location("mission_control_ui_test_app", Path(__file__).parents[1] / "app.py")
ui = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ui
with patch("threading.Thread.start"):
    spec.loader.exec_module(ui)


class UICallbackTests(unittest.TestCase):
    def setUp(self):
        cache = patch.dict(ui._DASHBOARD_AUX_CACHE, {}, clear=True)
        cache.start()
        self.addCleanup(cache.stop)

    def test_event_coalescing_retains_pending_revision_until_success(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=100, last_attempt_epoch=100,
                     last_data_revision=4, api_online=True, ws_connected=True)
        ws = {"connected": True, "data_revision": 5, "revision": 6,
              "last_event_type": "task.updated", "last_event_id": "new"}
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value=ws
        ), patch.object(ui, "MISSION_CONTROL_EVENT_COALESCE_SECONDS", 2), patch.object(
            ui, "_get_agent_catalog", return_value=[]
        ), patch.object(ui, "_cached_dashboard_json", return_value=None), patch.object(
            ui, "api_get_json", side_effect=lambda path: {"columns": []} if path == "/v1/boards/default" else []
        ) as get:
            with patch.object(ui.time, "time", return_value=101):
                deferred = ui.refresh_data(0, 1, {}, {}, state)
            get.assert_not_called()
            self.assertEqual(deferred[16]["last_data_revision"], 4)
            with patch.object(ui.time, "time", return_value=102):
                refreshed = ui.refresh_data(0, 2, {}, {}, deferred[16])
            self.assertEqual(refreshed[16]["last_data_revision"], 5)
            self.assertEqual(get.call_count, 2)
            with patch.object(ui.time, "time", return_value=103):
                ui.refresh_data(0, 3, {}, {}, refreshed[16])
            self.assertEqual(get.call_count, 2)

    def test_ping_does_not_hide_unconsumed_business_event(self):
        with patch.dict(ui.WS_STATE, {"connected": True, "revision": 0, "data_revision": 0}, clear=True):
            ui._on_ws_message(json.dumps({"type": "task.updated", "id": "task-event"}))
            ui._on_ws_message(json.dumps({"type": "ping"}))
            ws = ui._get_ws_state()
            self.assertEqual(ws["data_revision"], 1)
            self.assertTrue(ui._should_refresh_from_ws({}, ws))
            deferred = ui._sync_state_with_ws({}, ws)
            self.assertTrue(ui._should_refresh_from_ws(deferred, ws))
            refreshed = ui._sync_state_with_ws(deferred, ws, data_refreshed=True)
            ui._on_ws_message(json.dumps({"type": "ping"}))
            self.assertFalse(ui._should_refresh_from_ws(refreshed, ui._get_ws_state()))

    def test_event_burst_reduces_reads_without_losing_final_update(self):
        for window, expected_reads in ((0, 200), (2, 10)):
            state = ui._sync_state_default()
            state.update(last_success="12:00:00", last_success_epoch=100, last_attempt_epoch=100,
                         api_online=True, ws_connected=True)
            ws = {"connected": True}
            with self.subTest(window=window), patch.object(
                ui, "ctx", SimpleNamespace(triggered_id="ws-tick")
            ), patch.object(ui, "_get_ws_state", return_value=ws), patch.object(
                ui, "MISSION_CONTROL_EVENT_COALESCE_SECONDS", window
            ), patch.object(ui, "_get_agent_catalog", return_value=[]), patch.object(
                ui, "_cached_dashboard_json", return_value=None
            ), patch.object(ui, "api_get_json", side_effect=lambda path: {"columns": []} if path == "/v1/boards/default" else []) as get:
                for revision in range(1, 101):
                    ws.update(data_revision=revision, revision=revision, last_event_id=str(revision))
                    with patch.object(ui.time, "time", return_value=100 + revision / 10):
                        result = ui.refresh_data(0, revision, {}, {}, state)
                    state = result[16] if result[16] is not no_update else state
                self.assertEqual(get.call_count, expected_reads)
                self.assertEqual(state["last_data_revision"], 100)

    def test_failed_event_refresh_does_not_retry_for_every_new_event(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=90, last_attempt_epoch=90,
                     api_online=True, ws_connected=True)
        ws = {"connected": True, "data_revision": 1}
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value=ws
        ), patch.object(ui, "api_get_json", side_effect=RuntimeError("offline")) as get:
            with patch.object(ui.time, "time", return_value=100):
                failed = ui.refresh_data(0, 1, {}, {}, state)
            self.assertEqual(failed[16]["last_data_revision"], 0)
            ws["data_revision"] = 2
            with patch.object(ui.time, "time", return_value=101):
                ui.refresh_data(0, 2, {}, {}, failed[16])
            self.assertEqual(get.call_count, 1)
            with patch.object(ui.time, "time", return_value=105):
                ui.refresh_data(0, 3, {}, {}, failed[16])
            self.assertEqual(get.call_count, 2)

    def test_task_actions_and_disabled_coalescing_refresh_immediately(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=100, api_online=True)
        for trigger, window in (("task-refresh-signal", 2), ("ws-tick", 0)):
            with self.subTest(trigger=trigger), patch.object(
                ui, "ctx", SimpleNamespace(triggered_id=trigger)
            ), patch.object(ui, "_get_ws_state", return_value={"connected": True, "data_revision": 1}), patch.object(
                ui.time, "time", return_value=100.1
            ), patch.object(ui, "MISSION_CONTROL_EVENT_COALESCE_SECONDS", window), patch.object(
                ui, "_get_agent_catalog", return_value=[]
            ), patch.object(ui, "_cached_dashboard_json", return_value=None), patch.object(
                ui, "api_get_json", side_effect=lambda path: {"columns": []} if path == "/v1/boards/default" else []
            ) as get:
                refreshed = ui.refresh_data(0, 1, {}, {}, state)
                self.assertEqual(get.call_count, 2)
                self.assertEqual(refreshed[16]["last_data_revision"], 1)

    def test_auxiliary_cache_expires_from_completion_and_recovers_after_failure(self):
        path = "/v1/observability/container-health"
        with patch.object(ui, "MISSION_CONTROL_AUX_CACHE_SECONDS", 15), patch.object(
            ui.time, "monotonic", side_effect=[100, 114, 115, 120, 134, 135, 140]
        ), patch.object(ui, "api_get_json", side_effect=[{"overall_ok": 8}, RuntimeError("offline"), {"overall_ok": 7}]) as get:
            self.assertEqual(ui._cached_dashboard_json(path), {"overall_ok": 8})
            self.assertEqual(ui._cached_dashboard_json(path), {"overall_ok": 8})
            self.assertIsNone(ui._cached_dashboard_json(path))
            self.assertIsNone(ui._cached_dashboard_json(path))
            self.assertEqual(ui._cached_dashboard_json(path), {"overall_ok": 7})
            self.assertEqual(get.call_count, 3)

    def test_auxiliary_cache_combines_concurrent_reads(self):
        started = threading.Event()
        release = threading.Event()

        def get(path, **kwargs):
            started.set()
            if not release.wait(2):
                raise RuntimeError("test release timed out")
            return {"overall_ok": 8}

        with patch.object(ui, "api_get_json", side_effect=get) as fetch, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(ui._cached_dashboard_json, "/v1/observability/container-health")
            try:
                self.assertTrue(started.wait(2))
                second = pool.submit(ui._cached_dashboard_json, "/v1/observability/container-health")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2), {"overall_ok": 8})
            self.assertEqual(second.result(timeout=2), {"overall_ok": 8})
            fetch.assert_called_once()

    def test_auxiliary_cache_can_be_disabled_and_does_not_cache_business_reads(self):
        with patch.object(ui, "api_get_json", return_value={}) as get:
            with patch.object(ui, "MISSION_CONTROL_AUX_CACHE_SECONDS", 0):
                ui._cached_dashboard_json("/v1/observability/container-health")
                ui._cached_dashboard_json("/v1/observability/container-health")
            ui._cached_dashboard_json("/v1/boards/default")
            ui._cached_dashboard_json("/v1/boards/default")
            self.assertEqual(get.call_count, 4)

    def test_live_refresh_keeps_task_search_and_full_snapshot(self):
        board = {"columns": [{"title": "INBOX", "count": 2,
                              "cards": [{"id": "first", "title": "First", "assignee": "nox"},
                                        {"id": "second", "title": "Second", "assignee": "writing"}]}]}

        def get(path):
            if path == "/v1/boards/default":
                return board
            if path.startswith("/v1/feed") or path.startswith("/v1/usage"):
                return []
            return {}

        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="task-refresh-signal")), patch.object(
            ui, "_get_ws_state", return_value={}
        ), patch.object(ui, "api_get_json", side_effect=get), patch.object(ui, "_get_agent_catalog", return_value=[]), patch.object(
            ui, "column", side_effect=lambda item: item
        ):
            result = ui.refresh_data(0, 0, {"task_query": "nox"}, {}, {})
        self.assertEqual(result[1][0]["count"], 1)
        self.assertEqual(result[1][0]["cards"][0]["id"], "first")
        self.assertEqual(result[4], "2")
        self.assertEqual(len(result[17][0]["cards"]), 2)
        self.assertNotIn("total_count", result[17][0])

    def test_search_url_restore_clear_and_other_filters_preserve_query(self):
        state = {"board_filter": "all", "feed_filter": "all", "task_query": ""}

        def update(trigger, url="", query="", current=None):
            with patch.object(ui, "ctx", SimpleNamespace(triggered_id=trigger)):
                return ui.update_ui_state(url, 0, 0, 0, 0, 0, 0, 0, 0, query,
                                          state if current is None else current)

        searched, url, field = update("task-search", query="知识库 & nox")
        self.assertEqual(searched["task_query"], "知识库 & nox")
        self.assertIs(field, no_update)
        restored, untouched_url, query = update("url", url=url)
        self.assertEqual(restored, searched)
        self.assertIs(untouched_url, no_update)
        self.assertEqual(query, "知识库 & nox")
        filtered, filtered_url, _ = update("feed-filter-comments", url, query, searched)
        self.assertEqual(filtered["task_query"], query)
        self.assertEqual(filtered["feed_filter"], "comments")
        cleared, clear_url, clear_query = update("clear-filters", filtered_url, query, filtered)
        self.assertEqual(cleared, state)
        self.assertEqual(clear_url, "")
        self.assertEqual(clear_query, "")
        self.assertTrue(all(value is no_update for value in update("url", url, query, searched)))
        legacy, _, field = update("url", "?board=tasks&feed=system", "old", searched)
        self.assertEqual(legacy["task_query"], "")
        self.assertEqual(field, "")

    def test_search_controls_report_loaded_matches_and_reset_availability(self):
        columns = [{"title": "INBOX", "count": 2,
                    "cards": [{"title": "First", "assignee": "nox"}, {"title": "Second"}]}]
        sync_state = {"last_success": "12:00:00"}
        self.assertEqual(ui.sync_task_search_controls({}, columns, sync_state), (True, "2 / 2 loaded tasks"))
        self.assertEqual(ui.sync_task_search_controls({"task_query": "nox"}, columns, sync_state),
                         (False, "1 / 2 loaded tasks"))
        self.assertEqual(ui.sync_task_search_controls({"task_query": "missing"}, columns, sync_state),
                         (False, "0 / 2 loaded tasks"))
        self.assertEqual(ui.sync_task_search_controls({"feed_filter": "comments"}, columns, sync_state),
                         (False, "2 / 2 loaded tasks"))
        self.assertEqual(ui.sync_task_search_controls({"task_query": "nox"}, columns, {}),
                         (False, "Tasks not loaded"))

    def test_local_task_search_does_not_read_api_or_change_feed(self):
        columns = [{"title": "INBOX", "count": 2,
                    "cards": [{"title": "First", "assignee": "nox"}, {"title": "Second"}]}]
        feed = [{"category": "comments"}]
        state = {"task_query": "nox", "feed_filter": "all"}
        with patch.object(ui, "api_get_json") as get, patch.object(ui, "column", side_effect=lambda item: item), patch.object(
            ui, "feed_item", side_effect=lambda item: item
        ), patch.object(ui, "ctx", SimpleNamespace(triggered_id="ui-state")), patch.object(
            ui, "_get_ws_state", return_value={}
        ):
            result = ui.render_local_filters(state, {"last_success": "12:00:00"}, columns, feed)
            refreshed = ui.refresh_data(0, 0, state, {}, {"last_success": "12:00:00"})
        get.assert_not_called()
        self.assertEqual(result[0][0]["count"], 1)
        self.assertEqual(result[1], feed)
        self.assertTrue(all(value is no_update for value in refreshed))

    def test_task_search_matches_title_id_and_assignee_without_mutating_snapshot(self):
        cards = [{"id": "ABC-123456789", "short_id": "ABC-1234", "title": "Quarterly report",
                  "assignee": "nox"},
                 {"id": "DEF-987654321", "short_id": "DEF-9876", "title": "知识库整理",
                  "assignee": "writing"}]
        columns = [{"title": "INBOX", "count": 2, "cards": cards},
                   {"title": "DONE", "count": 0, "cards": []}]
        for query, expected in ((" REPORT ", cards[0]), ("abc-123456789", cards[0]),
                                ("#abc-1234", cards[0]), ("NOX", cards[0]),
                                ("知识库", cards[1]), ("writing", cards[1])):
            with self.subTest(query=query):
                result = ui._filter_board(columns, "all", query)
                self.assertEqual([item["title"] for item in result], ["INBOX", "DONE"])
                self.assertEqual(result[0]["cards"], [expected])
                self.assertIs(result[0]["cards"][0], expected)
                self.assertEqual(result[0]["count"], 1)
                self.assertEqual(result[0]["total_count"], 2)
                self.assertEqual(columns[0]["cards"], cards)
                self.assertEqual(columns[0]["count"], 2)
                self.assertNotIn("total_count", columns[0])
        for empty in (None, "", "  "):
            self.assertIs(ui._filter_board(columns, "tasks", empty), columns)
        unmatched = ui._filter_board(columns, "all", "not-a-task")
        self.assertTrue(all(item["count"] == 0 and not item["cards"] for item in unmatched))

    def test_initial_layout_identifies_loading_and_announces_connection(self):
        layout = ui.app.server.test_client().get("/_dash-layout").get_json()
        components = {}

        def collect(component):
            if isinstance(component, dict):
                props = component.get("props", {})
                if isinstance(props.get("id"), str):
                    components[props["id"]] = props
                collect(props.get("children"))
            elif isinstance(component, list):
                for child in component:
                    collect(child)

        collect(layout)
        self.assertEqual(components["api-status"]["children"], "Connecting...")
        self.assertEqual(components["api-status"]["role"], "status")
        self.assertEqual(components["api-status"]["aria-live"], "polite")
        for component_id, expected in (("agents", "Loading agents..."), ("board", "Loading tasks..."),
                                       ("feed", "Loading activity...")):
            self.assertEqual(components[component_id]["children"][0]["props"]["children"], expected)

    def test_api_failure_identifies_cached_data_and_preserves_snapshot(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=100)
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="initial")), patch.object(
            ui, "_get_ws_state", return_value={}
        ), patch.object(ui, "api_get_json", side_effect=RuntimeError("unavailable")):
            result = ui.refresh_data(0, 0, {}, {}, state)
        self.assertTrue(all(value is no_update for value in result[:14]))
        self.assertIn("showing cached data", result[14])
        self.assertIn("last sync 12:00:00", result[14])
        self.assertIn("retry in 5s", result[14])
        self.assertTrue(all(value is no_update for value in result[17:]))
        with patch.object(ui, "_get_ws_state", return_value={}):
            self.assertIn("no data loaded", ui._format_api_status(False))
            self.assertNotIn("cached", ui._format_api_status(True, "12:01:00"))

    def test_voice_latency_distinguishes_disabled_empty_and_measured(self):
        metrics = {"samples_count": 2, "p50_ms": 200, "p95_ms": 300}
        with patch.object(ui, "MISSION_CONTROL_VOICE_OVERLAY_ENABLED", False):
            self.assertEqual(ui.render_voice_latency_pill(metrics),
                             ("Overlay disabled", "status-pill status-unknown"))
        with patch.object(ui, "MISSION_CONTROL_VOICE_OVERLAY_ENABLED", True):
            for empty in (None, {}, {"samples_count": 0}):
                self.assertEqual(ui.render_voice_latency_pill(empty),
                                 ("Overlay: no samples", "status-pill status-unknown"))
            self.assertEqual(ui.render_voice_latency_pill(metrics),
                             ("Overlay p50 200ms · p95 300ms", "status-pill status-online"))

    def test_agent_status_is_visible_without_color(self):
        for status, expected, css_status in (
            ("RECENT", "Recently active", "recent"),
            (" idle ", "Idle", "idle"),
            (None, "Unknown", "unknown"),
            ("", "Unknown", "unknown"),
            ("OFFLINE", "Unknown", "unknown"),
        ):
            with self.subTest(status=status):
                card = ui.agent_card({"name": "nox", "badge": "AGENT", "role": "Manifest agent",
                                      "status": status, "usage_text": "Usage unavailable"})
                avatar, meta = card.children
                self.assertEqual(avatar.className, f"agent-avatar status-{css_status}")
                self.assertEqual(avatar.to_plotly_json()["props"]["aria-hidden"], "true")
                label = next(child for child in meta.children
                             if getattr(child, "className", "").startswith("agent-status "))
                self.assertEqual(label.children, expected)
                self.assertEqual(label.className, f"agent-status status-{css_status}")
                self.assertIn(expected, label.to_plotly_json()["props"]["aria-label"])
                if css_status == "idle":
                    self.assertIn("not necessarily offline", label.title)
                self.assertEqual(meta.children[-1].children, "Usage unavailable")

    def test_filter_pressed_state_matches_visual_selection(self):
        for state in (None, {}, {"board_filter": "tasks", "feed_filter": "comments"},
                      {"board_filter": "ALL", "feed_filter": "SYSTEM"}):
            with self.subTest(state=state):
                classes = ui.sync_filter_chip_classes(state)
                pressed = ui.sync_filter_chip_pressed(state)
                self.assertEqual(len(pressed), 7)
                self.assertEqual(pressed, tuple("true" if "active" in item.split() else "false"
                                                for item in classes))
                self.assertEqual(pressed[:2].count("true"), 1)
                self.assertEqual(pressed[2:].count("true"), 1)
                self.assertEqual(ui.sync_filter_chip_controls(state), (*classes, *pressed))

    def test_form_fields_have_associated_labels(self):
        layout = ui.app.server.test_client().get("/_dash-layout").get_json()
        components = []

        def collect(component):
            if isinstance(component, dict):
                components.append(component)
                collect(component.get("props", {}).get("children"))
            elif isinstance(component, list):
                for child in component:
                    collect(child)

        collect(layout)
        targets = {item.get("props", {}).get("htmlFor") for item in components
                   if item.get("type") == "Label"}
        self.assertTrue({"task-search", "task-comment-author", "task-comment-body", "create-task-title",
                         "create-task-tags", "settings-threshold-24h-warn",
                         "settings-threshold-7d-warn", "settings-threshold-24h-close",
                         "settings-threshold-7d-close"}.issubset(targets))

    def test_dashboard_auxiliary_reads_overlap_and_fail_independently(self):
        barrier = threading.Barrier(4)

        def get(path, **kwargs):
            if path == "/v1/boards/default":
                return {"columns": []}
            if path == "/v1/feed-lite?limit=80":
                return []
            barrier.wait(timeout=2)
            if path == "/v1/usage/agents?days=7":
                raise RuntimeError("usage unavailable")
            if path == "/v1/observability/container-health":
                return {"overall_ok": 3, "overall_total": 4, "overall_ratio": 0.75}
            return {}

        def catalog(**kwargs):
            barrier.wait(timeout=2)
            return []

        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="initial")), patch.object(
            ui, "_get_ws_state", return_value={}
        ), patch.object(ui, "api_get_json", side_effect=get) as reads, patch.object(
            ui, "_get_agent_catalog", side_effect=catalog
        ):
            result = ui.refresh_data(0, 0, {}, {}, {})
        self.assertEqual(result[15], "status-pill status-online")
        self.assertEqual(result[8], "3/4 · 75%")
        self.assertEqual(reads.call_count, 5)

    def test_text_compression_and_negotiation(self):
        client = ui.app.server.test_client()
        for path in ("/", "/_dash-layout"):
            with self.subTest(path=path):
                plain = client.get(path, headers={"Accept-Encoding": "identity"})
                compressed = client.get(path, headers={"Accept-Encoding": "gzip"})
                self.assertEqual(compressed.status_code, 200)
                self.assertEqual(compressed.headers.get("Content-Encoding"), "gzip")
                self.assertIn("Accept-Encoding", compressed.headers.get("Vary", ""))
                self.assertEqual(gzip.decompress(compressed.data), plain.data)
                self.assertLess(len(compressed.data), len(plain.data) // 2)
                rejected = client.get(path, headers={"Accept-Encoding": "gzip;q=0, identity;q=1"})
                self.assertNotIn("Content-Encoding", rejected.headers)
        self.assertIn("no-store", compressed.headers["Cache-Control"])

    def test_fingerprinted_scripts_keep_cache_headers(self):
        with ui.app.server.test_request_context("/_dash-component-suites/dash/test.v1_0_0m1.js"):
            response = ui.Response("script", headers={"Cache-Control": "public, max-age=31536000"})
            self.assertEqual(ui.add_dash_runtime_cache_headers(response).headers["Cache-Control"],
                             "public, max-age=31536000")
        for path in ("/", "/_dash-layout", "/_dash-dependencies", "/_dash-update-component"):
            with self.subTest(path=path), ui.app.server.test_request_context(path):
                response = ui.add_dash_runtime_cache_headers(ui.Response("runtime"))
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_idle_ws_tick_returns_no_changes(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=ui.time.time(), api_online=True, ws_connected=True)
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value={"connected": True}
        ), patch.object(ui, "api_get_json") as get:
            result = ui.refresh_data(1, 1, {}, {}, state)
        get.assert_not_called()
        self.assertTrue(all(value is no_update for value in result))

    def test_disabled_voice_tick_returns_empty_http_response(self):
        state = ui._voice_overlay_default()
        state["enabled"] = False
        payload = {
            "output": "voice-ui.data",
            "outputs": {"id": "voice-ui", "property": "data"},
            "inputs": [
                {"id": "ws-tick", "property": "n_intervals", "value": 1},
                {"id": "voice-overlay-close", "property": "n_clicks", "value": 0},
            ],
            "state": [{"id": "voice-ui", "property": "data", "value": state}],
            "changedPropIds": ["ws-tick.n_intervals"],
        }
        with patch.object(ui, "api_get_json") as get, patch.object(ui, "_get_ws_state") as ws:
            response = ui.app.server.test_client().post(
                "/_dash-update-component", json=payload, headers={"Accept-Encoding": "gzip"}
            )
        get.assert_not_called()
        ws.assert_not_called()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertNotIn("Content-Encoding", response.headers)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_idle_tick_preserves_failed_api_status(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=ui.time.time(),
                 last_attempt_epoch=ui.time.time(), api_online=False, ws_connected=True)
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value={"connected": True}
        ):
            result = ui.refresh_data(1, 1, {}, {}, state)
        self.assertTrue(all(value is no_update for value in result))

    def test_ws_disconnect_updates_status_without_business_reads(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=ui.time.time(),
                 last_attempt_epoch=ui.time.time(), api_online=True, ws_connected=True)
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value={"connected": False}
        ), patch.object(ui, "api_get_json") as get:
            result = ui.refresh_data(1, 1, {}, {}, state)
        get.assert_not_called()
        self.assertIn("fallback polling", result[14])
        self.assertFalse(result[16]["ws_connected"])

    def test_refresh_pauses_timers_until_response_completes(self):
        callback = next(item for item in ui.app._callback_list if "sync-state.data" in item["output"])
        self.assertEqual([state["id"] for state in callback["state"]], ["sync-state"])
        self.assertTrue(callback["running"]["running"]["ws-tick.disabled"])
        self.assertTrue(callback["running"]["running"]["refresh.disabled"])
        self.assertFalse(callback["running"]["runningOff"]["ws-tick.disabled"])
        self.assertFalse(callback["running"]["runningOff"]["refresh.disabled"])

    def test_ws_tick_bootstraps_without_business_event(self):
        payloads = [{"columns": []}, [], [], {}, {}]
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value={"connected": True}
        ), patch.object(ui, "api_get_json", side_effect=payloads), patch.object(ui, "_get_agent_catalog", return_value=[]):
            result = ui.refresh_data(0, 1, {}, {}, {})
        self.assertEqual(result[15], "status-pill status-online")

    def test_ws_tick_runs_safety_calibration_without_refresh_timer(self):
        state = ui._sync_state_default()
        state.update(last_success="12:00:00", last_success_epoch=100, last_attempt_epoch=100)
        payloads = [{"columns": []}, [], [], {}, {}]
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value={"connected": True}
        ), patch.object(ui.time, "time", return_value=100 + ui.MISSION_CONTROL_WS_LIVE_POLL_SECONDS), patch.object(
            ui, "api_get_json", side_effect=payloads
        ), patch.object(ui, "_get_agent_catalog", return_value=[]):
            result = ui.refresh_data(0, 1, {}, {}, state)
        self.assertEqual(result[15], "status-pill status-online")

    def test_failed_bootstrap_waits_five_seconds_before_retry(self):
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ws-tick")), patch.object(
            ui, "_get_ws_state", return_value={"connected": True}
        ), patch.object(ui, "api_get_json", side_effect=RuntimeError("offline")) as get:
            with patch.object(ui.time, "time", return_value=100):
                failed = ui.refresh_data(0, 1, {}, {}, {})
            self.assertFalse(failed[16]["api_online"])
            with patch.object(ui.time, "time", return_value=104):
                self.assertTrue(all(value is no_update for value in ui.refresh_data(0, 2, {}, {}, failed[16])))
            self.assertEqual(get.call_count, 1)
            with patch.object(ui.time, "time", return_value=105):
                ui.refresh_data(0, 3, {}, {}, failed[16])
            self.assertEqual(get.call_count, 2)

    def test_initial_refresh_returns_full_snapshot(self):
        payloads = [{"columns": []}, [], [], {}, {}]
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="initial")), patch.object(
            ui, "_get_ws_state", return_value={}
        ), patch.object(ui, "api_get_json", side_effect=payloads), patch.object(ui, "_get_agent_catalog", return_value=[]):
            result = ui.refresh_data(0, 0, {}, {}, {})
        self.assertEqual(len(result), 19)
        self.assertEqual(result[15], "status-pill status-online")
        self.assertEqual(result[17:19], ([], []))

    def test_selection_rejects_replayed_click_after_close(self):
        trigger = {"type": "task-card", "task_id": "A", "status": "INBOX"}
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id=trigger, triggered=[{"value": 1000}])):
            selected = ui.select_task_card([1000], {})
            self.assertTrue(selected["drawer_open"])
            selected["drawer_open"] = False
            self.assertIs(ui.select_task_card([1000], selected), no_update)
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id=trigger, triggered=[{"value": 1001}])):
            self.assertTrue(ui.select_task_card([1001], selected)["drawer_open"])

    def test_skills_search_uses_snapshot_without_api_calls(self):
        payloads = [[{"slug": "research", "description": "Research"}], [{"agent_slug": "nox"}], {}, {}]
        with patch.object(ui, "api_get_json", side_effect=payloads) as get:
            snapshot = ui.load_skills_data({"open": True, "revision": 1}, None)
            self.assertEqual(get.call_count, 4)
            self.assertIs(ui.load_skills_data({"open": True, "revision": 1}, snapshot), no_update)
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="skills-global-search")), patch.object(
            ui, "api_get_json"
        ) as get:
            for query in ("r", "re", "research"):
                result = ui.render_skills_modal({"open": True}, query, "", "nox", snapshot, [], [])
                self.assertEqual(len(result), 17)
                self.assertEqual(result[1][0]["value"], "research")
                self.assertTrue(all(value is no_update for value in result[10:13]))
        get.assert_not_called()

    def test_skills_failed_refresh_retains_snapshot(self):
        previous = {"revision": 1, "global_skills": [{"slug": "research"}]}
        with patch.object(ui, "api_get_json", side_effect=RuntimeError("offline")):
            snapshot = ui.load_skills_data({"open": True, "revision": 2}, previous)
        self.assertEqual(snapshot["global_skills"], previous["global_skills"])
        self.assertIn("offline", snapshot["error"])
        self.assertIs(ui.load_skills_data({"open": False}, snapshot), no_update)

    def test_closed_chat_does_not_load_catalog(self):
        with patch.object(ui, "_get_agent_catalog") as catalog:
            for tick in range(6):
                self.assertEqual(len(ui.render_chat_modal(tick, {"open": False})), 11)
            with patch.object(ui, "ctx", SimpleNamespace(triggered_id="close-chat")):
                self.assertFalse(ui.update_chat_ui(0, 1, 0, 0, None, {"open": True})["open"])
        catalog.assert_not_called()

    def test_local_feed_filter_does_not_refetch_data(self):
        feed = [{"category": "tasks"}, {"category": "comments"}]
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="ui-state")), patch.object(
            ui, "_get_ws_state", return_value={}
        ), patch.object(ui, "api_get_json") as get, patch.object(ui, "feed_item", side_effect=lambda item: item):
            result = ui.render_local_filters({"feed_filter": "comments"}, {"last_success": "12:00:00"}, [], feed)
            refresh_result = ui.refresh_data(0, 0, {"feed_filter": "comments"}, {}, {"last_success": "12:00:00"})
        get.assert_not_called()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1], [{"category": "comments"}])
        self.assertTrue(all(value is no_update for value in refresh_result))

    def test_drafts_are_isolated_and_restored_by_task(self):
        original = ["author", "comment A", "summary A", "artifact A", "notes A", "review A"]
        stored = ui.sync_task_drafts({"selected_task_id": "A"}, *original, {"task_id": "A", "drafts": {}})[0]
        switched = ui.sync_task_drafts({"selected_task_id": "B"}, *original, stored)
        self.assertEqual(switched[1:], ("", "", "", "", "", ""))
        restored = ui.sync_task_drafts({"selected_task_id": "A"}, "", "comment B", "", "", "", "", switched[0])
        self.assertEqual(list(restored[1:]), original)
        self.assertEqual(restored[0]["drafts"]["B"][1], "comment B")

    def test_cleared_comment_does_not_clear_other_drafts(self):
        fields = ["author", "", "summary", "artifact", "notes", "review"]
        result = ui.sync_task_drafts({"selected_task_id": "A"}, *fields, {"task_id": "A", "drafts": {}})
        self.assertEqual(result[0]["drafts"]["A"], fields)
        self.assertTrue(all(value is no_update for value in result[1:]))

    def test_settings_refresh_preserves_edits(self):
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="refresh")), patch.object(
            ui, "api_get_json", return_value=[]
        ), patch.object(ui, "_get_agent_catalog", return_value=[]):
            for opened in (False, True):
                result = ui.render_settings_modal(1, {"open": opened})
                self.assertEqual(len(result), 9)
                self.assertTrue(all(value is no_update for value in result[1:5]))
            with patch.object(ui, "api_get_json", side_effect=RuntimeError("offline")):
                result = ui.render_settings_modal(1, {"open": True})
                self.assertTrue(all(value is no_update for value in result[1:5]))

    def test_settings_state_initializes_values(self):
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="settings-ui")):
            self.assertEqual(ui.render_settings_modal(1, {"warn_24h": 123})[1], 123)

    def preview(self, assignee=None):
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="preview-create-task-route")), patch.object(
            ui, "api_post_json", return_value={"suggested_assignee": "nox"}
        ):
            return ui.preview_create_task_route(1, "Task A", assignee, "research", {})

    def test_preview_auto_fill_does_not_invalidate_itself(self):
        state, assignee = self.preview()
        self.assertEqual(assignee, "nox")
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="create-task-assignee")):
            result = ui.preview_create_task_route(1, "Task A", "nox", "research", state)
        self.assertTrue(all(value is no_update for value in result))

    def test_changed_title_clears_automatic_route(self):
        state, _ = self.preview()
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="create-task-title")):
            updated, assignee = ui.preview_create_task_route(1, "Task B", "nox", "research", state)
        self.assertIsNone(updated["route_preview"])
        self.assertIsNone(assignee)

    def test_changed_fields_preserve_manual_assignee(self):
        state, _ = self.preview("email")
        with patch.object(ui, "ctx", SimpleNamespace(triggered_id="create-task-tags")):
            updated, assignee = ui.preview_create_task_route(1, "Task A", "email", "new-tag", state)
        self.assertIsNone(updated["route_preview"])
        self.assertIs(assignee, no_update)

    def test_create_does_not_submit_a_stale_automatic_assignee(self):
        state, _ = self.preview()
        with patch.object(ui, "api_post_json", side_effect=RuntimeError("offline")) as post:
            result = ui.submit_create_task(1, "Task B", "nox", "research", state, {}, {})
        self.assertIsNone(post.call_args.args[1]["assignee"])
        self.assertTrue(all(value is no_update for value in result[1:]))


if __name__ == "__main__":
    unittest.main()