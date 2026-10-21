# umooc-gdgm

优慕课，学生侧自动化技能。
查未交作业、读作业要求与草稿、重抓课程列表；提交链路已完整逆向并实测通过（默认需人工确认后才用）。

原本作为 WorkBuddy / AI 助手技能（`SKILL.md`）开发，脚本本身零第三方依赖（纯 Python 标准库），可独立使用。

## 功能

| 能力 | 状态 |
|---|---|
| 列出当前学期真·未交作业（带剩余/逾期天数） | ✅ 实测 |
| 读某次作业的要求、起止时间、我的草稿 | ✅ 实测 |
| 重抓课程列表 + 首页待交组件交叉校验（防漏课） | ✅ 实测 |
| 图片上传 → 富文本提交 → 回读逐字节验证 | ✅ 实测（多份作业） |
| zip 附件上传（整站压缩包类作业） | ✅ 实测 |
| 改稿/补码（已交且未截止的作业追加内容） | ✅ 实测 |
| 成绩查询 `hwShowScore.do` | ⚠️ 未验证 |

## 快速开始

```bash
# 1. 配置账号（复制模板后填真实值）
cp config.example.json config.json

# 2. 查未交作业
python scripts/查作业.py

# 3. 读某次作业要求（courseId/hwtId 在上一步输出里）
python scripts/查作业.py <courseId> <hwtId>

# 4. （可选）提交前先回读验证已交内容
python scripts/提交作业.py --verify <courseId> <hwtId>

# 5. （可选）提交：图片 + zip 附件
python scripts/提交作业.py <courseId> <hwtId> "标题" shot1.png shot2.png --zip 作品.zip
```

凭据也可以走环境变量 `UMOOC_USER` / `UMOOC_PASS`，不落盘。

首次使用先跑 `python scripts/查作业.py --courses` 生成你自己的课程表（`COURSES` 字典），
平台只给"挂了作业的课"的列表，新增课程要手动补一行。

## 三条铁律（踩过的坑）

1. **`submitStruts` 不是"已提交"**，是"提交窗口还开着"。拿它过滤会把历史存量全算成未交。
   正确的已交判定 = 有 `mark`（分数）或有 `finishTime`（`hwTaskAnswerView.do` 返回）。
2. **平台并发登录上限约 1–2 个会话**。超限返回"该用户同时在线的数量已超过系统最大允许值"，
   且实测阻塞可持续数小时。要么全用脚本、要么全用浏览器，别混用；登录失败就停手等，别重试。
3. **正文是双层 HTML 实体编码**，藏在 hidden input 里，页面还插了混淆 JS。
   提取/回读验证都要 `html.unescape`，验证代码内容时要 **unescape 两次**。

更多接口细节、参数、踩坑记录见 [`references/api.md`](references/api.md)。

## 目录结构

```
├── SKILL.md                  # 技能说明（AI 助手可直接加载）
├── config.example.json       # 账号配置模板（复制为 config.json）
├── scripts/
│   ├── 查作业.py             # 作业查询主工具（零第三方依赖）
│   └── 提交作业.py           # 图片/附件上传 + 提交 + 回读验证
├── references/
│   └── api.md                # 平台接口清单与踩坑记录
├── LICENSE                   # MIT
└── .gitignore                # 已排除 config.json / session.json
```

## 隐私

- **本仓库不含任何真实凭据**。账号密码放本机 `config.json`，已被 `.gitignore` 排除；
  `scripts/session.json`（会话 cookie）同样不入库。
- 上传/提交前请自行检查脚本没有把你本机的路径、学号等个人信息写进答案里。

## 免责声明

- 本项目仅用于学习交流，接口知识来自对**自己账号**的抓包分析。
- 请遵守你所在学校的网络使用规定；**不要**用于代提交、刷分、攻击平台等用途。
- 逾期作业平台硬关闭（提交接口返回"作业未开始/已结束"），迟交请找老师，技术上无门。
- 平台接口可能随版本变化而失效，本仓库按 THEOL V8（2026-10）实测。

## License

MIT
