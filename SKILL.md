---
name: umooc-gdgm
description: 优慕课(广东工贸 THEOL,umooc.gdgm.cn)自动化——查未交作业、读作业要求与草稿、抓课程列表。当用户提到优慕课/umooc/THEOL、作业没交/待提交/补交、查课程作业、或要操作 umooc.gdgm.cn 时使用。内含会话复用、并发上限规避、提交判定等踩坑经验。
---

# 优慕课(广东工贸 THEOL)自动化

## Overview

对 `umooc.gdgm.cn`(THEOL V8 在线教育平台)做学生侧自动化:查哪些作业没交、读某次作业的要求和已存草稿、重抓课程列表。**提交接口已逆向通但默认不自动提交**(见下)。

## Quick Start

```bash
python scripts/查作业.py                    # 当前学期真·未交(默认)
python scripts/查作业.py --history          # 连上学期及更早的存量
python scripts/查作业.py --all              # 全部(含已交,带分数)
python scripts/查作业.py --courses          # 重抓课程列表(加新课时)
python scripts/查作业.py <courseId> <hwtId> # 读某次作业要求+草稿
```

凭据在 `config.json`(技能根目录,只存本机);会话缓存在 `scripts/session.json`,过期才自动登录。

## 三条铁律(踩过坑,别重犯)

1. **`submitStruts` 不是"已提交",是"提交窗口还开着"** —— 截止日没过的才 `true`。拿它过滤"未交"会把已关闭的历史作业全算成未交(我曾因此报出 38 个未交的乌龙,实际只有 1 个)。
   **正确的"已交"判定 = 有 `mark`(已批分) 或 有 `finishTime`(`hwTaskAnswerView.do` 返回,有完成记录)。**
2. **并发登录上限极窄(约 1–2 个会话)**。脚本会话活着时再登(浏览器/另一脚本)直接返回"该用户同时在线的数量已超过系统最大允许值",且反复重试会拖长封锁。**要么全用脚本,要么全用浏览器,别混用;登录失败就停手等,别重试。**
3. **`content`/`hwaAnswer` 是双层编码** —— 正文藏在 `<input type='hidden' id='NNN_content' value='...'>` 里,要先 `html.unescape` 再去标签;页面还插了混淆 JS 防爬,直接取 body 会拿到垃圾。脚本里的 `text_of()` 已处理。

## 交叉校验(防漏课)

`course_list_v8.jsp` **只返回挂了作业的课,不是全部在读课程**。所以脚本每次都会拉首页组件
`/meol/welcomepage/student/interaction_reminder_v8.jsp`("N 门课程有待提交作业 + 课程名")对账:
平台说的待交课程数 > 本地数出来的 → 打印警告,提示跑 `--courses` 或手补 `COURSES`。

## 任务指引

### 查未交作业
直接跑默认模式。输出分「当前学期真未交(带剩余天数/逾期天数)」和「历史存量(折叠)」。
用户问"有什么作业没交/要交什么" → 就是这个。

### 读某次作业的要求
默认模式每行都带 `[读要求: 查作业.py <courseId> <hwtId>]`,照着跑即可。
作业要求、满分、起止时间、我的草稿(图片数/文字)都能读出来。
**注意:逾期作业平台硬关闭,提交接口对它们返回"作业未开始,或作业已结束,或作业已提交"** —— 所以迟交只能找老师,别承诺能自动补交。

### 抓课程/资料(另一个用途)
本技能只管作业侧。课程资料(课件 PDF 等)抓取的接口知识同样在 `references/api.md`,可照着重写。

### 提交作业(已实测通过,默认不用)
链路(2026-10-20/21 全流程实测,多份作业成功提交并验证):
1. **图片上传**: `POST /meol/servlet/SerUpload?action=uploadimage`(multipart,字段 `action=uploadimage` + `upfile`=文件)
   返回 `{"state":"SUCCESS","url":"/meol/common/ckeditor/openfile.jsp?id=..."}`;GET 该 URL 直接出图(HEAD 不行,JSP 返回错误页)
   ⚠️ **别用提交页 UEditor 自带的 `/meol/common/ueditor/jsp/controller.jsp`——服务器端 JSP 编译损坏(`ActionEnter cannot be resolved to a type`),上传必失败**
2. **附件(zip 等)上传**: `POST /meol/servlet/SerUpload?action=uploadfile`(同字段 `upfile`,允许 .zip/.rar/.tar 等,上限 2GB)。老师布置"整站压缩包上传"类作业时用这条;附件在 answer 里以 openfile.jsp 链接呈现
   (`GET ?action=config` 可读平台 UEditor 配置确认允许的扩展名)
3. **提交**: `POST /meol/hw/stu/hwStuSubmitDo.do`(multipart,字段 `courseId/um/hwtId/answer`,hwaId 首次提交不带;answer 是富文本 HTML,img 的 src 用 `https://umooc.gdgm.cn` + 上传返回的相对路径)
   成功返回 `{"message":"提交成功","status":1}`
4. **改稿/补码**(已交且未截止的作业): `GET /meol/hw/stu/hwStuSubmit.do?...&actionType=update` 拿 `hwaId` → 旧 answer 读出来(`hwTaskAnswerView.do`)+ 追加内容 → `hwStuSubmitDo.do` 带 `hwaId` 重交。平台对重复提交不拒绝,可反复覆盖
5. **验证**: `hwTaskAnswerView.do` 看 `finishTime`;hwaAnswer 是双层编码,`html.unescape` **两次**后才数得到 img/代码行(一次只够看纯文本)

一键脚本:`python scripts/提交作业.py <courseId> <hwtId> <标题> <图片1> [图片2 ...] [--zip 包.zip]`;验证已交:`python scripts/提交作业.py --verify <courseId> <hwtId>`
**用前仍必须得到用户明确同意** —— 这是动他学业记录的外部动作,且逾期作业平台硬关闭(`hwStuSubmitDo` 返回"作业未开始,或作业已结束")。

## 环境备忘

- `um` = 学号在平台内的用户ID(每账号不同,存在 config.json),来自 `viewstudent_info.jsp?SID=` 或课程详情页 `uid=`
- 接口必须带 `/meol` 前缀,`/hw/stu/...` 是 404
- `new_opener()` 里的 `ProxyHandler({})` 是必须的:系统代理会缓存页面,导致拿到过期 token
- 新生初始密码规则 `gM@身份证后6位`(字母分大小写);密码改了就改 `config.json`
- 首页 `index.do` 被 Nginx 缓存(34KB 固定副本),加时间戳/no-cache 头都绕不过;小组件数据全走 JS

## Resources

### scripts/
- `查作业.py` — 作业查询主工具(零第三方依赖,标准库)
- `提交作业.py` — 图片上传+作业提交+验证(需用户明确授权后才用;`--verify` 只读验证)

### references/
- `api.md` — 平台接口清单与参数、踩坑记录

### 配置
- `config.json`(技能根目录)— 账号密码;`scripts/session.json` — 会话 cookie(运行时生成)
