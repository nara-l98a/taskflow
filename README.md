# Taskflow

Taskflow 是一个**本地优先的日常项目计划 CLI**：把任务按项目归档，用截止日期生成今日/未来计划，并用状态和优先级控制执行节奏。它不是联网看板，也不上传数据。

## 功能与边界

- 项目与任务新增、查看、更新；任务优先级为 `low/medium/high/urgent`。
- 截止日期、状态流转（`todo`、`in_progress`、`blocked`、`done`）。`task done` 是日常收尾快捷操作。
- 按项目、状态、优先级筛选；`overdue` 查看参考日之前仍未完成的任务。
- `plan` 将一个日期区间内未完成任务按截止日期排序；同一天按 `urgent`、`high`、`medium`、`low` 优先级排列，适合作为每日计划。
- 数据只保存到用户指定的 JSON 文件；写入采用同目录临时文件、flush/fsync、`os.replace` 原子替换。
- **边界**：单用户本地工具，不提供多人协作、提醒通知、重复任务、依赖关系、日历同步、加密或云备份；同一数据文件不建议多进程同时写入。

## 要求与安装

需要 Python **3.10 或更高版本**，运行依赖仅 Python 标准库。开发安装：

```bash
python -m pip install -e .
# 或不安装：PYTHONPATH=src python -m taskflow --help
```

所有命令均支持全局 `--data PATH`（别名 `--db`），也可用 `TASKFLOW_DATA` 指定路径；默认是 `~/.taskflow.json`。建议项目初始化使用专属路径：

```bash
taskflow --data ./work.json project add release "版本发布" --description "本周期上线工作"
taskflow --data ./work.json task add checklist release "核对发布清单" --priority high --due 2026-12-15
taskflow --data ./work.json task update checklist --status in_progress
taskflow --data ./work.json plan --on 2026-12-15
taskflow --data ./work.json task done checklist
```

示例输出：

```text
已创建任务：checklist
计划区间：2026-12-15 至 2026-12-15
checklist | in_progress | high | 2026-12-15 | 版本发布 | 核对发布清单
```

## 完整命令与参数

全局：`--data PATH` / `--db PATH`。

- `project add ID NAME [--description TEXT]`
- `project list`
- `project show ID`（同时列出该项目任务）
- `task add ID PROJECT TITLE [--priority {low,medium,high,urgent}] [--due YYYY-MM-DD] [--notes TEXT]`
- `task list [--project ID] [--status {todo,in_progress,blocked,done}] [--priority {low,medium,high,urgent}]`
- `task show ID`
- `task update ID [--title TEXT] [--priority ...] [--due YYYY-MM-DD] [--status ...] [--notes TEXT]`；`--due ""` 清除截止日期。
- `task done ID`
- `overdue [--on YYYY-MM-DD]`：默认以今天为参考日，仅显示未完成任务。
- `plan [--on YYYY-MM-DD] [--days N]`：默认今天、1 天；N 范围 1–366。

ID 不能为空且不能含空格；项目必须先创建；日期严格为 ISO `YYYY-MM-DD`；重复 ID、未知项目/任务、非法状态或优先级都会清晰报错并以非零状态退出。项目名称和任务标题不能为空。

每次启动都会校验 JSON 中的项目/任务关联、状态、优先级和日期；若文件被手工改坏，会在任何读写前明确报错，避免基于不完整数据继续操作。

## 数据格式、隐私与安全

JSON 顶层包含 `version`、`projects`、`tasks` 两个对象。项目记录含 `id/name/description/created_at`；任务记录含 `id/project_id/title/notes/priority/due/status/created_at/updated_at`。可复制 `examples/sample.json` 作为无个人数据的起点。

文件可能包含你输入的任务标题、备注和工作安排，属于本地敏感信息，请自行设置文件权限并纳入备份策略。Taskflow 不读取网络、不调用外部服务、不收集凭据、不内置密码或 Token。原子替换可避免常见半写文件，但无法防止磁盘损坏、恶意本地用户或同时写入造成的竞态；请在写入时避免多个进程共享同一文件。

## 开发与测试

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

测试使用 `tempfile` 隔离数据库，不触碰真实用户文件。CI 在 GitHub Actions 上使用 Python 3.10、3.11、3.12 运行同一测试命令。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
