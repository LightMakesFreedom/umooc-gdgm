---
name: umooc-gdgm
description: 优慕课(广东工贸 THEOL,umooc.gdgm.cn)自动化——查未交作业、读作业要求与草稿、程序化查看/批量下载课程公开资料(课件PDF/Word/练习题/rar压缩包)、图片/zip附件提交与回读验证。当用户提到优慕课/umooc/THEOL、作业没交/待提交/补交/改稿、查课程作业、课程资料/课件/教材下载、或要操作 umooc.gdgm.cn 时使用。内含会话复用、并发上限规避、提交判定等踩坑经验。
---

# 优慕课(广东工贸 THEOL)自动化

## Overview

对 `umooc.gdgm.cn`(THEOL V8 在线教育平台)做学生侧自动化:查哪些作业没交、读某次作业的要求和已存草稿、重抓课程列表、**列课程资料并批量下载**。**提交接口已逆向通但默认不自动提交**(见下)。

## Quick Start

**查作业**
```bash
python scripts/查作业.py                    # 当前学期真·未交(默认)
python scripts/查作业.py --history          # 连上学期及更早的存量
python scripts/查作业.py --all              # 全部(含已交,带分数)
python scripts/查作业.py --courses          # 重抓课程列表(加新课时)
python scripts/查作业.py <courseId> <hwtId> # 读某次作业要求+草稿
```

**查资料 / 下载**
```bash
python scripts/查资料.py <courseId>                       # 列出全部栏目的资料
python scripts/查资料.py <courseId> --tree                # 只看栏目结构(最快,不拉文件)
python scripts/查资料.py <courseId> --column <columnId>   # 只看某个栏目
python scripts/查资料.py <courseId> --download D:\课件     # 全部下载
python scripts/查资料.py <courseId> --download D:\课件 --column <columnId>  # 只下一个栏目
python scripts/查资料.py --courses                        # 看课程 ID
```

凭据在 `config.json`(技能根目录,只存本机);会话缓存在 `scripts/session.json`,过期才自动登录。

**课表放在 `config.json` 的 `courses` 字段里**(`{"19808": "程序设计基础", ...}`),不写在脚本里 —— 这样 `git pull` 更新技能时不会被远程的占位示例覆盖。`config.json` 已在 `.gitignore` 里,不会上传。

## 更新技能

本目录是 git 仓库,跟踪 `LightMakesFreedom/umooc-gdgm`:

```bash
git -C ~/.workbuddy/skills/umooc-gdgm pull
```

`config.json` 与 `scripts/session.json` 被 gitignore,拉取不会动它们。

## 四条铁律(踩过坑,别重犯)

1. **`submitStruts` 不是"已提交",是"提交窗口还开着"** —— 截止日没过的才 `true`。拿它过滤"未交"会把已关闭的历史作业全算成未交(我曾因此报出 38 个未交的乌龙,实际只有 1 个)。
   **正确的"已交"判定 = 有 `mark`(已批分) 或 有 `finishTime`(`hwTaskAnswerView.do` 返回,有完成记录)。**
2. **并发登录上限极窄(约 1–2 个会话)**。脚本会话活着时再登(浏览器/另一脚本)直接返回"该用户同时在线的数量已超过系统最大允许值",且反复重试会拖长封锁。**要么全用脚本,要么全用浏览器,别混用;登录失败就停手等,别重试。**
3. **`content`/`hwaAnswer` 是双层编码** —— 正文藏在 `<input type='hidden' id='NNN_content' value='...'>` 里,要先 `html.unescape` 再去标签;页面还插了混淆 JS 防爬,直接取 body 会拿到垃圾。脚本里的 `text_of()` 已处理。
4. **网络异常 ≠ 会话过期**。`session_alive()` 曾把超时/连接被掐当成"过期",于是每次网络抖动都白登一次,直接撞上面那条并发上限,被封几小时。现在它返回三态:`True` 活的 / `False` 确实过期 / `None` 网络有问题 → **报错退出,绝不重登**。改这块时别退回布尔值。

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

### 查课程资料 / 下载课件

用户问"这门课有什么资料/课件/教材"、"把资料下下来" → 用 `查资料.py`。

- `--tree` 只列栏目结构(最快,1 次请求),先看有哪些分组
- 不戴参数则逐栏目抓文件列表(52 个栏目约 1 分钟,82 个约 1.5 分钟)
- `--column` 只查一个栏目,省时间
- `--download` 按 `栏目名/文件名` 落盘;「课程资源」那套会多一层目录名
- 脚本已做两级去重(columnId 别名、resid 重复),不会重复下载

**两种栏目形态都支持**(见 `references/api.md` 的「两种文件列表页面形态」):
- 多文件列表(上课文档/练习题):图标 + 文件链接,一门课能上百个
- 单文件详情页(章节栏目):一栏目一个文件,如程序设计基础 10 章 PDF

**下载端点别选错**:统一用 `/meol/common/script/download.jsp`,它的 `Content-Disposition` 给真实文件名。
`/meol/analytics/resPdfShow.do` 只对 PDF 有效,对 Word **返回 0 字节**。

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

- **DNS 污染(2026-11-15 踩过,最容易误判成"封号")**:本机 DNS 曾把 `umooc.gdgm.cn` 解析成 `172.28.166.60`(Clash TUN 假地址),连进去报 `Remote end closed connection`,看着像并发封禁,实际是连错了机器。公共 DNS(223.5.5.5 / 119.29.29.29)一直给的是 `121.32.26.118`。
  脚本已内置兜底:`resolve_site()` 发现系统解析出私网地址就去问公共 DNS,然后只把**连接层**指向真 IP。启动会打印 `[i] DNS 兜底: ...`。显式指定用 `UMOOC_HOSTIP=1.2.3.4`。
  **实现细节(别再走弯路)**:Python 3.14 的 `HTTPSConnection` **不接受 `server_hostname` 参数**(传了直接 TypeError);而这个站**不吃 SNI**(SNI 填 IP 照样 302),唯一必须的是 `Host` 头保持域名。所以正确写法就是"连 IP、Host 交给 urllib 按原 URL 带",别去伪造 SNI。
  **判断方法**:`nslookup umooc.gdgm.cn 223.5.5.5` 看真 IP;`curl --resolve umooc.gdgm.cn:443:<真IP> https://umooc.gdgm.cn/meol/index.do` 返回 302 就说明是 DNS 问题不是封号。
- `um` = 学号在平台内的用户ID(每账号不同,存在 config.json),来自 `viewstudent_info.jsp?SID=` 或课程详情页 `uid=`
- 接口必须带 `/meol` 前缀,`/hw/stu/...` 是 404
- `new_opener()` 里的 `ProxyHandler({})` 是必须的:系统代理会缓存页面,导致拿到过期 token
- 新生初始密码规则 `gM@身份证后6位`(字母分大小写);密码改了就改 `config.json`
- 首页 `index.do` 被 Nginx 缓存(34KB 固定副本),加时间戳/no-cache 头都绕不过;小组件数据全走 JS
- 资料抓取限速:`UMOOC_GAP` 环境变量控制请求间隔(默认 1 秒)。别为求快并发 —— 这个平台的并发上限是硬墙

## Resources

### scripts/
- `查作业.py` — 作业查询主工具(零第三方依赖,标准库)
- `查资料.py` — 课程资料查看+批量下载(复用查作业的会话层)
- `提交作业.py` — 图片上传+作业提交+验证(需用户明确授权后才用;`--verify` 只读验证)
- `_offline_test.py` — 资料解析的离线单测(拿真实 HTML 片段跑,不联网)

### references/
- `api.md` — 平台接口清单与参数、踩坑记录

### 配置
- `config.json`(技能根目录,gitignored)— 账号密码 + `courses` 课表 + `um`
- `scripts/session.json`(运行时生成,gitignored)— 会话 cookie
- `config.example.json` — 模板,新机器照它填
