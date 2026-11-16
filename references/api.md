# umooc.gdgm.cn 接口清单与踩坑

THEOL V8(优慕课)平台,学生侧。所有接口都要带 `/meol` 前缀(直接 `/hw/stu/...` 会 404)。

## 认证

| 项 | 值 |
|---|---|
| 登录页 | `GET /meol/index.do` |
| 登录 | `POST /meol/loginCheck.do`,字段 `logintoken`(登录页 hidden,13位毫秒时间戳)、`IPT_LOGINUSERNAME`、`IPT_LOGINPASSWORD` |
| 成功标志 | 302 到 `personal.do` |
| 会话探测 | `GET /meol/personal.do` — 已登录是 ~44KB 大页;未登录返回 782 字节"您尚未登录系统" |
| Cookie | `JSESSIONID`,domain `umooc.gdgm.cn`,path `/meol` |

**POST 必须用干净的 `/meol/loginCheck.do`**。登录页 HTML 里嵌的 action 带 `;jsessionid=<旧值>`,
沿用会把 Cookie 覆盖掉 → 服务端找不到会话 → 又跳登录页。首页 `index.do` 是 Nginx 缓存副本,
里面嵌的 jsessionid 永远是旧的。

**并发上限**:约 1–2 个会话。超限返回"该用户同时在线的数量已超过系统最大允许值",
且实测阻塞可持续数小时(9/24 那次约 4.5 小时)。`mobileLogin.do` 短信验证码也绕不开。
对策只有复用 cookie,别反复登。

## 作业(学生侧)

| 接口 | 方法 | 参数 | 返回 |
|---|---|---|---|
| `/meol/hw/stu/hwStuHwtList.do` | GET | `courseId` `hwType=blended_info` `page` `rows` | 作业列表 `datas.hwtList[]` |
| `/meol/hw/stu/hwTaskAnswerView.do` | GET | `courseId` `um` `hwtId` | 要求正文+草稿+`finishTime` |
| `/meol/hw/stu/hwStuSubmit.do` | GET | `courseId` `um` `hwtId` `actionType=update` | 提交表单+`hwaId`;**逾期作业返回错误** |
| `/meol/hw/stu/hwStuSubmitDo.do` | POST multipart | `courseId` `um` `hwtId` `answer`(富文本HTML),`hwaId` 仅改稿时带 | 提交结果 `{"message":"提交成功","status":1}` |
| `/meol/servlet/SerUpload` | POST multipart | `action=uploadimage` + `upfile`(文件) | **图片上传(可用!)** 返回 `{"state":"SUCCESS","url":"/meol/common/ckeditor/openfile.jsp?id=..."}` |
| `/meol/servlet/SerUpload` | POST multipart | `action=uploadfile` + `upfile`(文件) | **附件上传(zip/rar/tar,上限 2GB,2026-10-21 实测通过)** 返回同款 openfile.jsp URL |
| `/meol/hw/stu/hwShowScore.do` | GET | — | 成绩(未验证) |

### 图片上传(2026-10-20 实测通过, raid0/raid1 两份作业)

- **可用端点**:`POST /meol/servlet/SerUpload?action=uploadimage`,multipart 字段 `action=uploadimage`、`upfile`(文件),`Content-Type: multipart/form-data`
- 返回 UEditor 标准 JSON:`{"state":"SUCCESS","title":"xx.png","type":"png","url":"/meol/common/ckeditor/openfile.jsp?id=...","size":N}`
- 图片落地 URL 用 **GET** 直接出图(`Content-Type: image/png`);**HEAD 不行**,JSP 对 HEAD 返回 507 字节错误页
- ⚠️ **提交页 UEditor 自带的 `/meol/common/ueditor/jsp/controller.jsp` 已损坏**:服务器端 JSP 编译错误(`com.baidu.ueditor.ActionEnter cannot be resolved to a type`),走它的上传 100% 失败,必须用 SerUpload
- homework.js(3.7MB)里 SerUpload 的引用形态:`serverUrl: localStorage.getItem("rootUrl") + "/servlet/SerUpload"`(相对站点根,实际即 `/meol/servlet/SerUpload`)
- answer 里 img src 建议写全:`https://umooc.gdgm.cn` + 上传返回的相对路径

### 附件(zip)上传(2026-10-21 实测通过)

- **端点**:`POST /meol/servlet/SerUpload?action=uploadfile`,multipart 字段同样是 `action` + `upfile`,只是 action 值换成 `uploadfile`
- 允许 `.zip/.rar/.tar` 等,上限 2GB;返回同款 `{"state":"SUCCESS","url":"/meol/common/ckeditor/openfile.jsp?id=..."}`
- 附件在 answer 里以 openfile.jsp **下载链接**呈现(`<a href>`),与老师发的附件同形态
- `GET /meol/servlet/SerUpload?action=config` 可读平台 UEditor 配置(确认允许的扩展名/大小上限)

### 改稿/补码(已交且未截止的作业)

链路:`GET /meol/hw/stu/hwStuSubmit.do?courseId=..&um=..&hwtId=..&actionType=update` → 响应里拿 `hwaId`
→ `GET /meol/hw/stu/hwTaskAnswerView.do` 读旧 answer(hwaAnswer 字段)→ 追加新内容 → `hwStuSubmitDo.do` 带 `hwaId` 重交
平台对重复提交不拒绝,可反复覆盖。**逾期作业这条链路直接返回错误**(见下节)。

### hwtList 字段语义(重点)

| 字段 | 真实含义 |
|---|---|
| `submitStruts` | **提交窗口还开着**(截止日没过),**不是"已提交"** |
| `mark` | 分数。有值 = 已交且已批分 |
| `answerStatus` | 无区分度(已交的也是 false) |
| `showGrade` | 是否显示成绩 |
| `outStandingShow` | 优秀作业展示 |
| `finishTime`(在 AnswerView 里) | 有完成记录。**有 mark 或 finishTime 才算已交** |

### 逾期 = 硬关闭

`hwStuSubmit.do` 对已截止作业返回
`{"error":"作业未开始，或作业已结束，或作业已提交","status":-1}`
→ 迟交技术上无门,只能找老师后台开。对"已交且未截止"的作业返回 `status:1` + `hwaId`(可重复提交)。

## 课程

| 接口 | 说明 |
|---|---|
| `/meol/welcomepage/student/course_list_v8.jsp` | 课程列表(带 courseId)。**只返回挂了作业的课,不是全部在读课程** |
| `/meol/welcomepage/student/archive_course_list_v8.jsp` | 归档课程。**服务端超时,抓不到** |
| `/meol/welcomepage/student/interaction_reminder_v8.jsp` | "N 门课程有待提交作业"+课程名、"N 个系统通知未读"。**用来交叉校验漏课** |
| `/meol/welcomepage/common/schedules.jsp` | 日程日历(纯 HTML,无作业数据) |
| `POST /meol/course.do` | 公开课程目录搜索,参数 `deptId=0` `s_keywordrealation=0` `s_keyword=关键词`。共 253 页;**非公开课搜不到** |

课程页(学生视角):`/meol/jpk/course/layout/newpage/index.jsp?courseId=X`
栏目页:`/meol/jpk/course/course_column_preview_transfer.jsp?tagbug=client&columnId=Y`
作业模块入口:`/meol/common/hw/go_to_newhw.jsp?tagbug=&hwType=blended_info&hwtid=Z&strStyle=new03`
→ 该页写 localStorage(role/courseId/token/rootUrl)后跳 `/meol/common/homework.html`(Vue SPA,HTML 是空壳)

## 课程资料(文件/课件/教材,2026-11-15 实测)

### 解析链: 课程 → 栏目 → 资源 → 文件

| 步骤 | 端点 | 说明 |
|---|---|---|
| 1. 栏目树 | `GET /meol/jpk/course/layout/newpage/index.jsp?courseId=X` | 56KB HTML,从 `course_column_preview_transfer.jsp?...columnId=NNN"> <span>栏目名</span>` 正则提取。**同一 columnId 会出现多次**(不同分组下的别名,如 323001 既叫"课程练习题"又叫"理论练习题") |
| 2. 栏目跳转 | `GET /meol/jpk/course/course_column_preview_transfer.jsp?tagbug=client&columnId=NNN` | 28 字节空壳或跳转页。要顺着自身重定向看最终 URL,得到真实视图端点 |
| 3a. 资源文件夹 | 跳到 `/meol/buildless/colUrlStuView.do?columnId=NNN` → 内含 `<iframe src=".../resFolderViewList.do?folderid=..&lid=..&columnId=..">` | 多文件列表型(上课文档/练习题/章节) |
| 3b. 课程资源树 | 跳到 `/meol/common/script/courseResource.jsp?tagbug=client&folderid=0&lid=X&groupid=4` | 独立目录树,内部两个 iframe: `left.jsp`(目录树,JS 异步拉,静态 HTML 拿不到) + `listview.jsp?groupid=4&lid=X&folderid=N`(文件列表) |
| 4. 文件列表 | `GET /meol/buildless/resFolderViewList.do?folderid=F&lid=X&columnId=N` | 见下方"两种页面形态" |
| 5. 下载 | `GET /meol/common/script/download.jsp?fileid=FID&resid=RID&lid=X` | **唯一通用下载端点**,见下 |

### 两种文件列表页面形态(都要认)

**形态 A:多文件列表**(64KB 页,最常见)
```html
<img src="/meol/common/icons/pdf.gif">&nbsp;
<a href=" /meol/common/script/preview/download_preview.jsp?fileid=4759072&resid=292840&lid=19498&preview=preview ">课程成绩评定标准</a>
```
正则要用 `<a[^>]*href="\s*(...download_preview\.jsp...)"[^>]*>([^<]*)</a>` —— **href 前后带空格和换行**,不能用紧贴的 `href="`。

**形态 B:单文件详情页**(章节栏目一栏目挂一个资源)
```html
<h1>第1章 程序设计和C语言（含算法）</h1>
<h2>文件名:第1章 程序设计和C语言（含算法）.pdf <span>(3.0M)</span>
    <a class="icon32 lv-download" href="/meol/common/script/download.jsp?fileid=2182951&resid=169658">下载</a></h2>
```
没有图标列表,页内只有一个 `download.jsp` 链接。**若只按形态 A 解析会漏掉整门课** —— 程序设计基础(19808)就是这样,82 个栏目全靠形态 B 才抓到 10 章 PDF。

### 下载端点选择(关键)

| 端点 | PDF | Word/Excel/rar | 结论 |
|---|---|---|---|
| `/meol/common/script/download.jsp?fileid=..&resid=..&lid=..` | ⚠️ 返回 777 字节错误页 | ✅ 正常,`Content-Disposition` 带真名 | **统一用它** |
| `/meol/analytics/resPdfShow.do?resId=..&lid=..` | ✅ 114KB 真 PDF | ❌ **0 字节** | 别用于非 PDF |

- `download.jsp` 对 PDF 失败时,预览页里会额外给 `resPdfShow.do`;反过来不行。
- 文件名一律从 `Content-Disposition: attachment; filename="..."` 里取(URL 编码,要 `unquote`),比列表标题准(列表标题常没有扩展名)。
- 实测文件头校验:docx/xlsx = `504b0304`(ZIP),rar = `526172211a0700`(RAR5),PDF = `%PDF-1.5`。

### ⚠️ 错误页检测的坑(2026-11-16 踩过)

`download.jsp` 对某些 PDF 返回 777 字节的错误页(`<link href="/meol/styles/main/css/error.css">`)。
**这个错误页前面有几十个换行**,所以:

```python
body[:15].lstrip().startswith(b"<!DOCTYPE")   # ❌ 永远 False,lstrip 后是空串
(body or b"")[:400].lstrip().lower().startswith(b"<!doctype")   # ✅
```

判断错了的后果很隐蔽:**777 字节的 HTML 被当成 PDF 存下来**,目录里看着"成功"了,打开才是错的。
所以判 PDF 还要再看 `body[:4] == b"%PDF"`,对不上就走 `resPdfShow.do` 回退。

### 同名栏目会互相覆盖(2026-11-16 踩过)

`19498` 有**两个都叫"课堂练习题"**的栏目:`340728`(装 txt/zip)和 `328179`(装 docx)。
如果结果字典用栏目名当 key,后一个会把前一个覆盖掉,**静默丢 4 个文件**,而且不报错。
现在 key 用 `栏目名#columnId`,目录名只在真重名时才加 columnId 后缀。

反向的坑也要注意:同一 columnId 会有多个别名(323001 既叫"课程练习题"又叫"理论练习题"),
那种情况必须按 columnId 去重,否则重复下载。

### 图标 → 类型

`icons/pdf.gif` `word.gif` `excel.gif` `ppt.gif` `photo.gif` `text.gif` `zip.gif` `rar.gif` `video.gif`。
一门课的实测分布:`{rar:9, photo:8, word:93, pdf:101, text:50, zip:1, excel:2}`。

### 坑

- **同 columnId 别名会导致重复拉取**:不去重的话 `--column 323001` 会把 19 个文件下成 38 个(两个栏目名各一份)。必须先按 columnId 去重,文件再按 resid 去重。
- **栏目页请求很慢**:52 个栏目要 1 分多钟,82 个要 1.5 分钟。加 `UMOOC_GAP`(默认 1 秒)限速,别为求快并发。
- 没挂资料的课很常见(如 29477 路由与交换技术,8 个栏目全空),不是解析失败。
- 「课程资源」(courseResource.jsp)那套的目录树由 `left.jsp` 里 JS 异步拉,静态 HTML 拿不到目录结构;只能从 `listview.jsp` 的 `folderid=0` 起 BFS 爬子目录。

## 内容解析(双层编码)

`content` / `hwaAnswer` 的正文藏在:
```html
<input type='hidden' name='905_content' id='905_content' value='&lt;p&gt;题目...&lt;/p&gt;'>
```
即 **HTML 实体编码的 HTML**。提取步骤:正则取 `id='\d+_content'` 的 `value` → `html.unescape` →
去 script/style → `<img>` 替换成 `[图片]` → 去标签 → 再 `html.unescape` 一次 → 收行。
页面还插了 `VerwerImg` 之类混淆 JS,直接取 body.innerText 会拿到垃圾。

⚠️ **回读验证要 unescape 两次**:`hwTaskAnswerView.do` 返回的 `hwaAnswer` 里,提交时写的 HTML
(如 `<pre>` 代码块、含 `&lt;` 的行)会被平台**再转义一层**。只 unescape 一次时,代码行匹配不上
(表现为"明明交了却搜不到"),必须 `html.unescape(html.unescape(x))` 后才能逐行比对。

## 其他

- 作业系统是 Vue SPA,打包 JS 在 `/meol/static/js/homework.js`(约 3.7MB),接口定义都在里面,
  形如 `stu:{hwStuHwtList:function(e){return Object(u["a"])("/hw/stu/hwStuHwtList.do",e)}}`
- 教师侧接口在 `/hw/tea/*`(hwList/addHwTask/hwUpdateMark 等),本技能不用
- `urllib` 必须 `ProxyHandler({})`:系统代理会缓存页面拿到过期 token

## DNS 污染(2026-11-15)

本机把 `umooc.gdgm.cn` 解析成 `172.28.166.60`(Clash TUN 网段的假地址),症状:

| 现象 | 真实原因 |
|---|---|
| `Remote end closed connection without response` | 连到了不存在的机器,不是封号 |
| `session_alive()` 返回 False → 反复重登 | 误判会话过期 → 撞并发上限 |
| `curl` 直连 http=000 | DNS 指错,不是站点挂了 |

正确 IP 由 `223.5.5.5` / `119.29.29.29` 一致给出:**121.32.26.118**。
`curl --resolve umooc.gdgm.cn:443:121.32.26.118 https://umooc.gdgm.cn/meol/index.do` → **302**(正常)。
对照:`--resolve ...:172.28.166.60` → `000`(不通)。

`查作业.py` 的 `resolve_site()` 已做兜底(私网地址才替换,公网解析正常时不干预),
并支持 `UMOOC_HOSTIP` 环境变量强制指定。
