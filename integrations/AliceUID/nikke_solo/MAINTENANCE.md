# 个人突袭推荐（实验性）

命令：nk个人突袭推荐[刷新] [亮色/暗色/随机]，框架权限pm=6，仍受Core与AliceUID名单限制。仅本人当前绑定，发送前持绑定锁复核。查询前明确第三方来源；不记录Cookie、Token、分享URL、openid或原始响应。

官方端使用现有NikkeClient进行带Cookie的本人GetSavedRoleInfo与GetUserInfoNew读取。分享标识来自本人认证响应，不把登录openid直接当分享openid。DILDORO上下文全新、非持久、禁用service worker，不注入官方Cookie；缓存未命中或显式刷新时重新导入，结束即关闭。单进程最多一个网站计算，同一发起者重复请求提示在途；含排队总等待最多720秒，浏览器阶段最多600秒，不自动重发执行。

公开参考：2026-10-21的首页、app.js、profileconv.js、i18n.js，原件/哈希仅保存在开发.references/dildoro，不随插件安装。/account为页面而非公开API承诺。网址输入可读取openid参数；导入后按share_openid+area精确选择资料，绝不使用固定值默认账号。

DOM契约：url-in/url-go → profile-pick → mode-solo/code → fast-toggle/fast-wrap → fast-rank → lab-sheet中的draft-rank卡片 → lab-srv服务器 → data-role=go。监听页面sr-rank/list并核对同弱点赛季服务器；对随后sets响应再核对服务器，阻止网站静默回退。源映射JP81、NA82、KR83、GLOBAL84、SEA85、TW-HK91。北美是否能网址导入由实际同步结果决定，不因存在排行选项就声称支持。

当前网站配置模式会把推荐添加为第二个fg-set，截图该容器。严格验证5行、25个角色、5个数字伤害且无错误，等待头像和字体。DOM不符即拒绝截图。结果标签显示“网站当前弱点”与参考赛季，推荐可能来自历史同弱点赛季；缺失回收室等养成可能采用网站默认值。

卡片独立配置AliceUID_SoloCardTheme，默认dark，可选light/random；命令参数仅临时覆盖本次查询。复用整体主题色板，随机模式每次渲染只选择一次，不读取其他卡片主题；网站截图保留原始配色。顶部、说明与截图承托区使用半透明毛玻璃面板，共用预模糊背景及AliceUID_GlassStrength，原生渲染不依赖backdrop-filter。只截结果容器：先测量原始宽度、保留内部flex/grid布局，隐藏所有外围内容并解除祖先裁切，然后整体transform等比缩放至960 CSS像素；严禁仅设置width:960px使边界越过固定左栏。几何检查覆盖五行、25格、头像、个人/队伍/合计伤害及标题；宽度960 CSS像素、截图DPR1.5；PNG先按输出尺寸做四角透明遮罩，再放入22px圆角容器，保证浏览器及Core原生渲染均无直角露出。不降低既有渲染DPI/字体/质量。声明、来源、Powered By GsCore & Created By  AliceUID & dildoro均在卡内。

错误由用户可读的固定文本返回，日志仅异常类型。网站失败不以旧图冒充新结果。当前仅网址导入；私密资料不自动公开，也未自动启用网站书签/JSON备用方式。


## 五天缓存

Core资源目录AliceUID/cache/solo/<哈希>/保存source-<SHA256>.png、render-<样式指纹>.png和snapshot.json。身份哈希包括发起者、Bot、game_id、本人登录标识、区服与加密凭据的单向修订值；磁盘元数据不包含Cookie或分享链接。SCHEMA隔离裁切版本，文件哈希与PNG尺寸检查失败均按未命中处理。

有效期为captured_at起120小时（到期边界不命中），缓存读取/主题重绘均不延长。每次随机主题先选择一次明确亮暗，再查询对应成品；主题/字体/语言/毛玻璃强度/DPI/昵称/UID变化仅重绘，不访问网站。每账号最多保留8种成品，原图保持字节及DPR。

刷新指令绕过缓存，成功获取并渲染后原子发布新元数据；失败不会删除旧的有效结果，也不会在刷新请求中发送它。保存失败仍发送当次成功图片并明确提示。后台解绑和重新登录沿用_invalidate_replaced清理，聊天解绑另行独立清理（其他缓存异常不会跳过），落盘与最终发送均持绑定锁复核；已知失效凭据拒绝旧图。

查询时最多每小时扫一次，另复用现有aliceuid-roster-local-cleanup任务回收五天到期文件，不新增定时任务或网络请求。关闭Bot期间不会主动运行清理，重新查询/定时任务恢复后回收；过期图始终不能命中。
