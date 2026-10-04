"""Taskflow command line application; standard library only."""
from __future__ import annotations
import argparse, json, os, tempfile, uuid
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

STATUSES = ("todo", "in_progress", "blocked", "done")
PRIORITIES = ("low", "medium", "high", "urgent")
PRIORITY_RANK = {priority: -rank for rank, priority in enumerate(PRIORITIES)}

class TaskflowError(Exception):
    pass

class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.data = self._load()
    def _load(self):
        if not self.path.exists():
            return {"version": 1, "projects": {}, "tasks": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TaskflowError(f"无法读取数据文件：{exc}") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("projects", {}), dict) or not isinstance(raw.get("tasks", {}), dict):
            raise TaskflowError("数据文件格式无效：projects/tasks 必须是对象")
        raw.setdefault("version", 1)
        self._validate(raw)
        return raw
    @staticmethod
    def _validate(data):
        """Reject malformed hand-edited files before commands use them."""
        projects, tasks = data["projects"], data["tasks"]
        for project_id, project in projects.items():
            if not isinstance(project, dict) or project.get("id") != project_id:
                raise TaskflowError(f"数据文件格式无效：项目 {project_id} 记录不完整")
            if not isinstance(project.get("name"), str):
                raise TaskflowError(f"数据文件格式无效：项目 {project_id} 名称无效")
        for task_id, task in tasks.items():
            if not isinstance(task, dict) or task.get("id") != task_id:
                raise TaskflowError(f"数据文件格式无效：任务 {task_id} 记录不完整")
            if task.get("project_id") not in projects:
                raise TaskflowError(f"数据文件格式无效：任务 {task_id} 所属项目不存在")
            if task.get("status") not in STATUSES or task.get("priority") not in PRIORITIES:
                raise TaskflowError(f"数据文件格式无效：任务 {task_id} 状态或优先级无效")
            if task.get("due") is not None:
                parse_day(task["due"])
    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
                fh.flush(); os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except Exception:
            try: os.unlink(tmp)
            except OSError: pass
            raise

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def parse_day(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("日期必须严格使用 YYYY-MM-DD")
        return value
    except ValueError as exc: raise TaskflowError(f"日期必须为 YYYY-MM-DD：{value}") from exc

def ident(value: str, label: str):
    if not value or any(c.isspace() for c in value): raise TaskflowError(f"{label} ID 不能为空且不能含空格")
    return value

def text(value: str, label: str):
    if not value or not value.strip():
        raise TaskflowError(f"{label} 不能为空")
    return value

def project_or_error(store, project_id):
    if project_id not in store.data["projects"]: raise TaskflowError(f"项目不存在：{project_id}")
    return store.data["projects"][project_id]

def task_or_error(store, task_id):
    if task_id not in store.data["tasks"]: raise TaskflowError(f"任务不存在：{task_id}")
    return store.data["tasks"][task_id]

def print_tasks(tasks, store):
    if not tasks: print("没有符合条件的任务"); return
    for t in tasks:
        project = store.data["projects"].get(t["project_id"], {}).get("name", t["project_id"])
        due = t.get("due") or "无截止日期"
        print(f"{t['id']} | {t['status']} | {t['priority']} | {due} | {project} | {t['title']}")

def build_parser():
    p = argparse.ArgumentParser(prog="taskflow", description="本地优先的项目与日常任务计划工具")
    p.add_argument("--data", "--db", default=os.environ.get("TASKFLOW_DATA", "~/.taskflow.json"), help="JSON 数据文件路径")
    sub = p.add_subparsers(dest="command", required=True)
    pp = sub.add_parser("project", help="管理项目"); ps = pp.add_subparsers(dest="action", required=True)
    a=ps.add_parser("add"); a.add_argument("id"); a.add_argument("name"); a.add_argument("--description", default="")
    ps.add_parser("list")
    a=ps.add_parser("show"); a.add_argument("id")
    tp = sub.add_parser("task", help="管理任务"); ts = tp.add_subparsers(dest="action", required=True)
    a=ts.add_parser("add"); a.add_argument("id"); a.add_argument("project"); a.add_argument("title"); a.add_argument("--priority", choices=PRIORITIES, default="medium"); a.add_argument("--due"); a.add_argument("--notes", default="")
    a=ts.add_parser("list"); a.add_argument("--project"); a.add_argument("--status", choices=STATUSES); a.add_argument("--priority", choices=PRIORITIES)
    a=ts.add_parser("show"); a.add_argument("id")
    a=ts.add_parser("update"); a.add_argument("id"); a.add_argument("--title"); a.add_argument("--priority", choices=PRIORITIES); a.add_argument("--due"); a.add_argument("--status", choices=STATUSES); a.add_argument("--notes")
    a=ts.add_parser("done"); a.add_argument("id")
    a=sub.add_parser("overdue", help="查看截至今天逾期且未完成的任务"); a.add_argument("--on", help="测试或指定参考日期 YYYY-MM-DD")
    a=sub.add_parser("plan", help="按截止日期生成今日/未来日计划"); a.add_argument("--on", help="起始日期 YYYY-MM-DD"); a.add_argument("--days", type=int, default=1)
    return p

def run(args):
    store=Store(args.data); changed=False
    if args.command == "project":
        if args.action == "add":
            ident(args.id,"项目");
            text(args.name, "项目名称")
            if args.id in store.data["projects"]: raise TaskflowError(f"项目已存在：{args.id}")
            store.data["projects"][args.id]={"id":args.id,"name":args.name,"description":args.description,"created_at":now()}; changed=True; print(f"已创建项目：{args.id}")
        elif args.action == "list":
            for p in store.data["projects"].values(): print(f"{p['id']} | {p['name']} | {p.get('description','')}")
        else:
            p=project_or_error(store,args.id); print(json.dumps(p,ensure_ascii=False,indent=2));
            tasks=[t for t in store.data["tasks"].values() if t["project_id"]==args.id]; print_tasks(tasks,store)
    elif args.command == "task":
        if args.action == "add":
            ident(args.id,"任务"); project_or_error(store,args.project); text(args.title, "任务标题")
            if args.id in store.data["tasks"]: raise TaskflowError(f"任务已存在：{args.id}")
            due=parse_day(args.due) if args.due else None; stamp=now()
            store.data["tasks"][args.id]={"id":args.id,"project_id":args.project,"title":args.title,"notes":args.notes,"priority":args.priority,"due":due,"status":"todo","created_at":stamp,"updated_at":stamp}; changed=True; print(f"已创建任务：{args.id}")
        elif args.action == "list":
            tasks=list(store.data["tasks"].values());
            if args.project: project_or_error(store,args.project); tasks=[t for t in tasks if t["project_id"]==args.project]
            if args.status: tasks=[t for t in tasks if t["status"]==args.status]
            if args.priority: tasks=[t for t in tasks if t["priority"]==args.priority]
            print_tasks(sorted(tasks,key=lambda t:(t.get("due") or "9999-99-99", PRIORITY_RANK[t["priority"]], t["id"])),store)
        elif args.action == "show": print(json.dumps(task_or_error(store,args.id),ensure_ascii=False,indent=2))
        else:
            t=task_or_error(store,args.id)
            if args.action == "done": t["status"]="done"
            else:
                for key in ("title","priority","status","notes"):
                    value=getattr(args,key)
                    if value is not None:
                        if key == "title": text(value, "任务标题")
                        t[key]=value
                if args.due is not None: t["due"]=parse_day(args.due) if args.due else None
            t["updated_at"]=now(); changed=True; print(f"已更新任务：{args.id}")
    else:
        ref=parse_day(args.on) if getattr(args,"on",None) else date.today().isoformat()
        tasks=[t for t in store.data["tasks"].values() if t.get("due") and t["due"]<ref and t["status"]!="done"] if args.command=="overdue" else []
        if args.command=="overdue": print_tasks(sorted(tasks,key=lambda t:t["due"]),store)
        else:
            if args.days<1 or args.days>366: raise TaskflowError("--days 必须在 1 到 366 之间")
            start=date.fromisoformat(ref); end=start+timedelta(days=args.days-1)
            tasks=[t for t in store.data["tasks"].values() if t.get("due") and start.isoformat()<=t["due"]<=end.isoformat() and t["status"]!="done"]
            print(f"计划区间：{start.isoformat()} 至 {end.isoformat()}"); print_tasks(sorted(tasks,key=lambda t:(t["due"], PRIORITY_RANK[t["priority"]], t["id"])),store)
    if changed: store.save()

def main(argv=None):
    try: run(build_parser().parse_args(argv))
    except TaskflowError as exc: raise SystemExit(f"错误：{exc}")
    except ValueError as exc: raise SystemExit(f"错误：日期或参数无效：{exc}")

if __name__ == "__main__": main()
