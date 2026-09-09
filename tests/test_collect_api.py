import importlib.util
import io
import json
import os
import tempfile
import unittest
from unittest import mock


MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills",
    "paoding",
    "scripts",
    "collect_api.py",
)
SPEC = importlib.util.spec_from_file_location("paoding_collect_api", MODULE_PATH)
collect_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect_api)


class FakeTikHubClient:
    def __init__(self):
        self.detail_calls = 0
        self.comment_calls = 0

    def search_users(self, _keyword):
        return {
            "data": {
                "data": {
                    "items": [
                        {"user_info": {"id": "1234567890abcdef12345678", "name": "测试博主"}}
                    ]
                }
            }
        }

    def fetch_user_info(self, _user_id):
        return {"data": {"data": {"user": {"nickname": "测试博主", "fans": 100}}}}

    def fetch_user_notes(self, _user_id, cursor=None):
        self.last_cursor = cursor
        return {
            "data": {
                "data": {
                    "notes": [
                        {
                            "note_card": {
                                "note_id": "note-1",
                                "type": "video",
                                "display_title": "先看结果再讲方法",
                                "time": 123,
                            }
                        }
                    ],
                    "has_more": False,
                    "cursor": "",
                }
            }
        }

    def fetch_note_detail(self, note_id, video=False):
        self.detail_calls += 1
        self.last_detail = (note_id, video)
        return {
            "data": {
                "data": {
                    "note": {
                        "note_id": note_id,
                        "type": "video",
                        "title": "先看结果再讲方法",
                        "desc": "完整口播正文",
                        "liked_count": "1.2万",
                        "collected_count": 321,
                        "comments_count": 45,
                        "video_info_v2": {
                            "media": {
                                "stream": {
                                    "h264": [{"master_url": "https://cdn.example/video.mp4"}]
                                }
                            }
                        },
                    }
                }
            }
        }

    def fetch_note_comments(self, _note_id, cursor=None):
        self.comment_calls += 1
        return {
            "data": {
                "data": {
                    "comments": [
                        {"content": "终于讲明白了", "like_count": 9},
                        {"content": "求下一期", "like_count": 3},
                    ]
                }
            }
        }


class CollectApiTests(unittest.TestCase):
    def test_tikhub_has_no_artificial_request_cap(self):
        client = collect_api.TikHubClient("secret", min_interval=0)
        for _ in range(5000):
            client._record_request()
        self.assertEqual(client.requests_made, 5000)
        self.assertIsNone(client.hard_cap_usd)

    def test_balance_output_never_prints_account_fields(self):
        output = io.StringIO()
        payload = {
            "code": 200,
            "user_data": {
                "email": "private@example.com",
                "api_token": "secret",
                "balance": 18.0,
            },
        }
        with mock.patch("sys.stdout", output):
            collect_api._display_balance(payload)
        rendered = output.getvalue()
        self.assertIn("$18.0000", rendered)
        self.assertNotIn("private@example.com", rendered)
        self.assertNotIn("secret", rendered)

    def test_app_v2_video_url_is_extracted(self):
        payload = {
            "data": {
                "data": {
                    "note": {
                        "video_info_v2": {
                            "media": {
                                "stream": {
                                    "h264": [{"master_url": "https://cdn.example/video.mp4"}]
                                }
                            }
                        }
                    }
                }
            }
        }
        self.assertEqual(
            collect_api.extract_xhs_video_url(payload),
            "https://cdn.example/video.mp4",
        )

    def test_xhs_collection_normalizes_and_resumes(self):
        client = FakeTikHubClient()
        with tempfile.TemporaryDirectory() as outdir:
            total = collect_api.collect_xhs(client, "测试博主", 1, outdir)
            self.assertEqual(total, 1)
            self.assertEqual(client.last_detail, ("note-1", True))
            sample_dirs = [name for name in os.listdir(outdir) if name.startswith("S01-")]
            self.assertEqual(len(sample_dirs), 1)
            sample_dir = os.path.join(outdir, sample_dirs[0])
            with open(os.path.join(sample_dir, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
            self.assertEqual(meta["likes"], 12000)
            with open(os.path.join(sample_dir, "content.txt"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "完整口播正文")
            with open(os.path.join(sample_dir, "comments.txt"), encoding="utf-8") as f:
                comments = f.read()
            self.assertIn("[赞9] 终于讲明白了", comments)

            total = collect_api.collect_xhs(client, "测试博主", 1, outdir)
            self.assertEqual(total, 1)
            self.assertEqual(client.detail_calls, 1)
            self.assertEqual(client.comment_calls, 1)

    def test_checkpoint_deduplicates_changed_note_id_by_content_fingerprint(self):
        with tempfile.TemporaryDirectory() as outdir:
            meta = {
                "platform": "xhs",
                "id": "old-id",
                "title": "同一条内容",
                "date": 123,
            }
            collect_api.write_sample(outdir, 1, meta, "正文", [])
            ids, fingerprints, max_index = collect_api._load_checkpoint(outdir, "xhs")
            changed_id = dict(meta, id="new-id")
            self.assertIn("old-id", ids)
            self.assertIn(collect_api._fingerprint(changed_id), fingerprints)
            self.assertEqual(max_index, 1)

    def test_transcript_mode_backfills_existing_video_sample(self):
        client = FakeTikHubClient()
        with tempfile.TemporaryDirectory() as outdir:
            meta = {
                "platform": "xhs",
                "id": "note-1",
                "title": "先看结果再讲方法",
                "date": 123,
                "type": "video",
            }
            sample_dir = collect_api.write_sample(outdir, 1, meta, "正文", [])
            with mock.patch.object(collect_api, "transcribe_video", return_value="ok") as transcribe:
                completed = collect_api._backfill_transcripts(
                    client,
                    outdir,
                    "xhs",
                    "small",
                    False,
                )
            self.assertEqual(completed, 1)
            self.assertEqual(client.detail_calls, 1)
            transcribe.assert_called_once_with(
                "https://cdn.example/video.mp4",
                sample_dir,
                model="small",
                keep_media=False,
            )
            with open(os.path.join(sample_dir, "meta.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["transcript_status"], "ok")


if __name__ == "__main__":
    unittest.main()
