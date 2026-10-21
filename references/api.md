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
