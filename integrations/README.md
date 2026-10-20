# NapCat ↔ GsCore 标准转发说明

## 1.0.08：只更新AliceUID

2026-10-20，用户实机确认candidate3的nk卡片、nk帮助、nk出刀转发均成功。正式交付沿用该发送代码，不调整节点结构或重新编码默认值。以下阶段性待验收提示已由此三项成功结果更新，仍保留不同环境的实验性与失败回退。

当前主线按用户要求恢复fix1曾成功的标准方式：

`卡片完整原图 → Core磁盘缓存/读回校验 → 标题文字节点＋图片节点 → 现有GScore适配器 → NapCat`

只替换Core的plugins/AliceUID并重启Core，保留data/AliceUID、数据库和密钥。无需安装新NapCat插件、修改插件ID、GScore适配器源码或全局packetBackend。原卡片本来就有cache/roster磁盘JPG缓存，发送时读取；这次不是第一次引入磁盘缓存。

转发始终是纯node帧，不附外层at，输入中的at/at_all子段过滤；节点内保留标题text和完整image。普通消息或失败回退可@发起者。帮助标题与快速开始说明合成一个文字节点；图鉴标题为AliceUID·游戏昵称·图鉴展示，出刀为AliceUID·公会名-出刀统计。

帮助、卡片、出刀、登录四个开关默认开启，已有设置不覆盖，功能仍为实验性。登录/重新登录共用开关，二维码独立且不重新编码。短卡片、文字版帮助、进度和错误仍按原方式发送。

## 原图与可选JPG转换

“转发图片转换JPG”默认关闭：完整PNG/JPG/WEBP保持原字节、全部尺寸、DPI和元数据，不分页、不缩放。对照保存的1.0.07 fix1 ZIP，离线验证原/新代码经过真实Core和固定TS适配器后的最终send_msg参数一致。

需要转换时可手动开启，使用既有JPG编码流程；质量默认95、0–100整数，下次发送生效，100仍非无损。已有JPG直接发送，透明图保留PNG。关闭转换时质量设置仍保留但不参与编码。登录二维码和普通发送不编码。

成品传输缓存位于data/AliceUID/cache/forward_outbox：原子写入、读取SHA256校验后发送，64MiB/32张、15分钟有效，后续写入清理。缓存失败整体普通回退，不形成自动重放队列。完整图片超过8MiB插件保护上限或像素/格式无效时整体普通发送原内容；该大小不是QQ官方限制。

## 回执与自动回退

实际链路为AliceUID → GsCore → xiowo/napcat-plugin-gscore-adapter → NapCat → QQ。[固定适配器源码](https://github.com/xiowo/napcat-plugin-gscore-adapter/blob/df1859b396ffbd73bd2b72ce4a35147667281472/src/services/gscore-service.ts)将node转换成OneBot节点并调用send_msg。默认bot.send只确认Core入队，不证明QQ送达。

保留fix1的wait_recall=True观察参数，由现有适配器回传消息ID；该参数不改变最终send_msg节点内容。取得ID才确认，未确认时普通发送原内容一次并暂停该连接转发300秒，不重新取数、重绘、创建登录会话或无限重试。普通回退不会递归转发。旧Core不支持回执、私聊、Core禁止转发或连接处于暂停期时直接普通发送。取消不回退，权限和发送前绑定核验照常执行。

Core通常等待约10秒，不能据此判断NapCat已经终止上传；迟到成功仍可能与普通回退重复。缓存命中只说明Core本地有图，不证明QQ资源缓存命中或网络可达。

## 测试与日志

1. 更新Core的AliceUID并重启；这会清空本插件内存暂停状态。四个转发开关旧值保留，需要测试的开关请确认开启，JPG转换先保持默认关闭。
2. 测试nk卡片、nk帮助及nk出刀。正常应出现一个标题节点、一张完整图，不带@；日志为strategy=classic_original及strategy=classic_node。
3. 成功以群中实际转发和Core消息ID确认判断。失败可见普通回退及300秒暂停；暂停期内后续普通图片不是开关失效。
4. 失败时保留Core格式/尺寸/体积/回执日志与同期NapCat错误，隐藏登录链接和凭据。若NapCat仍报Highway connect ETIMEDOUT，恢复旧节点结构不能保证修复出站网络。不要仅凭Core“发送消息”或本地cache_ready判断成功。

用户明确报告最初卡片以及fix1标题＋图片形式曾实机成功。该事实作为对照依据保留；后来完整卡片也失败，尚不能仅凭历史成功定位当前故障。离线协议一致不等于当前QQ上传成功。

## 头像昵称

AliceUID不添加身份控制段或独立头像QQ选项，沿用现有适配器。固定适配器支持customForwardInfo：关闭使用默认小助手；开启且customForwardQQ/customForwardName留空时读取当前机器人selfId/selfNickname；有自定义值则用相应值。这是NapCat端现有GScore适配器设置，影响其发送的其它转发，非本次必须修改的项目。[身份读取源码](https://github.com/xiowo/napcat-plugin-gscore-adapter/blob/df1859b396ffbd73bd2b72ce4a35147667281472/src/core/state.ts)。

## 可选的candidate2实验

[原生转发配套](napcat-plugin-aliceuid-native-forward/README.md)仅留作可选实验，不是candidate3安装条件，也未自动启用。它需要用户主动另装NapCat插件，会在机器人自身会话产生准备消息，再原生合并到群；Core缓存到期不会删除QQ历史。

用户19:42测试只更新Core，未安装配套，故未进入该原生路径。现在优先验收标准fix1路线，不要求继续安装配套。此前若已安装，请禁用该配套并重启NapCat，才能对照当前标准路线；现有GScore适配器保持启用。
