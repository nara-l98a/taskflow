import json, tempfile, unittest
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from taskflow.app import TaskflowError, main, parse_day

class TaskflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/"data.json"
    def tearDown(self): self.tmp.cleanup()
    def call(self,*args):
        out=StringIO()
        with redirect_stdout(out): main(["--data",str(self.db),*args])
        return out.getvalue()
    def test_project_and_task_persist(self):
        self.call("project","add","focus","专注工作")
        self.call("task","add","t1","focus","写计划","--priority","high","--due","2026-04-01")
        data=json.loads(self.db.read_text())
        self.assertEqual(data["tasks"]["t1"]["priority"],"high")
        self.assertIn("t1",self.call("task","list","--project","focus"))
    def test_status_transition_and_done_hidden_from_overdue(self):
        self.call("project","add","p","项目")
        self.call("task","add","old","p","旧任务","--due","2020-01-01")
        self.assertIn("old",self.call("overdue","--on","2020-02-01"))
        self.call("task","done","old")
        self.assertIn("没有符合条件",self.call("overdue","--on","2020-02-01"))
    def test_filters_and_daily_plan(self):
        self.call("project","add","p","项目")
        self.call("task","add","today","p","今天","--due","2026-06-10")
        self.call("task","add","later","p","以后","--due","2026-06-12")
        self.assertIn("today",self.call("plan","--on","2026-06-10"))
        self.assertNotIn("later",self.call("plan","--on","2026-06-10"))
        self.assertIn("todo",self.call("task","list","--status","todo"))
    def test_update_and_clear_due(self):
        self.call("project","add","p","项目")
        self.call("task","add","t","p","初稿","--due","2026-01-01")
        self.call("task","update","t","--title","终稿","--status","in_progress","--due","")
        raw=json.loads(self.db.read_text())["tasks"]["t"]
        self.assertEqual(raw["title"],"终稿"); self.assertEqual(raw["status"],"in_progress"); self.assertIsNone(raw["due"])

    def test_dates_require_canonical_iso_format(self):
        self.assertEqual(parse_day("2026-04-01"), "2026-04-01")
        for value in ("20260401", "2026-W14-3", "2026-4-1"):
            with self.subTest(value=value), self.assertRaises(TaskflowError):
                parse_day(value)

    def test_invalid_existing_data_is_rejected(self):
        self.db.write_text(json.dumps({"projects": {}, "tasks": {
            "orphan": {"id": "orphan", "project_id": "missing", "status": "todo", "priority": "low"}
        }}))
        with self.assertRaisesRegex(SystemExit, "所属项目不存在"):
            self.call("task", "list")

    def test_blank_titles_are_rejected(self):
        with self.assertRaisesRegex(SystemExit, "项目名称"):
            self.call("project", "add", "p", "   ")
        self.call("project", "add", "p", "项目")
        with self.assertRaisesRegex(SystemExit, "任务标题"):
            self.call("task", "add", "t", "p", "")

    def test_plan_orders_urgent_before_low(self):
        self.call("project", "add", "p", "项目")
        self.call("task", "add", "low", "p", "低", "--priority", "low", "--due", "2026-06-10")
        self.call("task", "add", "urgent", "p", "急", "--priority", "urgent", "--due", "2026-06-10")
        output = self.call("plan", "--on", "2026-06-10")
        self.assertLess(output.index("urgent"), output.index("low"))

if __name__ == "__main__": unittest.main()
