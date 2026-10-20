# NapCat ↔ GsCore 转发通道说明

适用于 AliceUID 1.0.07 紧急修订。**无需安装 NoneBot，也无需额外安装 AliceUID 前端插件。** 上次的 NoneBot 配套代码已移出正式插件并可恢复归档。

## 当前设置

**转发为实验性功能。** fix2实机帮助转发仍未成功，自动回退/暂停已触发；1.0.07正式封包保留此已知限制，后续发送修复在1.0.08继续。失败或未确认时自动回退一次普通消息，并暂停本连接转发5分钟。

按用户最新授权，帮助、完整卡片、出刀及登录转发四个开关全部默认开启。如果开启后群内看不到消息，请关闭对应开关回到普通模式。升级保留已有值；旧配置为关闭时需要手动开启，默认值不覆盖已有选择。

转发首节点先展示文字标题，随后展示完整图片。帮助为 AliceUID帮助；图鉴为 AliceUID·游戏昵称·图鉴展示；出刀为 AliceUID·公会名-出刀统计。普通消息与错误/进度提示不额外添加标题。

主题新默认 random，毛玻璃新默认 20%；已保存的主题与强度仍优先使用，不覆盖自定义。

## 为什么后台有“发送”但群里没有消息

用户实际链路为：

`AliceUID → GsCore → xiowo/napcat-plugin-gscore-adapter → NapCat → QQ`

[适配器固定源码](https://github.com/xiowo/napcat-plugin-gscore-adapter/blob/df1859b396ffbd73bd2b72ce4a35147667281472/src/services/gscore-service.ts)参考版本 1.3.5：handleGsCoreMessage 将节点转换后调用 send_msg，并在适配器自身捕获错误。Core 默认的 bot.send 只等待消息入队/写入WebSocket，所以其返回None和“发送消息”日志不是 QQ 送达证明。这是此前没有触发回退的可复现缺口。

后续实机日志已确认：NapCat Highway TCP连接上传服务器8080超时，回退HTTP同样超时，随后报告转发资源上传失败。上传连接尚未建立，不能认定图片格式或体积本身有错；帮助/出刀PNG约2.63MB、成功卡片JPG约2.25MB，也不能单凭这一差距认定超出大小限制。参考[NapCat TCP上传源码](https://github.com/NapNeko/NapCatQQ/blob/450fb0429a064e3418e0c698b1b4d78324101929/packages/napcat-core/packet/highway/uploader/highwayTcpUploader.ts)与[HTTP回退源码](https://github.com/NapNeko/NapCatQQ/blob/450fb0429a064e3418e0c698b1b4d78324101929/packages/napcat-core/packet/highway/uploader/highwayHttpUploader.ts)。

本次识别 napcat 或 napcat-* 的 OneBot 连接，请求 Core 的 wait_recall 消息ID回执。适配器成功返回ID后确认转发；没有确认时，回退一次同一图片或登录链接。不会重新取数、重绘、创建登录会话，原图像素、DPI和字体不变。旧Core没有回执能力或连接已判定不支持时，直接走普通模式。

参考Core等待上限为10秒。未确认后普通回退一次，并暂停本连接转发5分钟，后续请求走普通路径；不反复重试转发。超时可能意味着仍在上传，迟到成功可能产生一次重复。旧版适配器没有回执时建议关闭转发或更新适配器。取消任务不触发回退。其它非NapCat适配器的未知None/空回执仍不自动重发。

## JPG质量与完整分页

转发新编码图片默认JPG质量95，GsCore后台“转发图片JPG编码质量”可设0–100整数，下次转发生效。100仍是有损编码，不能把95理解为压缩到原文件95%。现有合规JPG直接发送以保留已成功的卡片路径；透明图保留PNG，登录二维码与普通发送不重编码。新编码JPG使用4:4:4，不缩放、保留DPI；高度超过4096像素或单页超过4MiB时按顺序完整分页，全部原始行保留。编码失败或完整输出超过保护上限时，整体普通发送原图。

该处理减小部分图片并缩短单页高度，属于兼容改善，不能保证更换编码后QQ网络上传必定成功。如仍报connect ETIMEDOUT，请在NapCat所在容器/主机排查日志指定服务器的出站TCP8080、路由/代理和防火墙；浏览器能上网或Core可渲染不足以证明该上传路径可达。不硬编码上传IP，也不无限重试。

## 头像和昵称设置在正确的位置

AliceUID 不再提供“使用当前QQ身份”开关，不发送自定义控制段，沿用适配器的转发身份。

xiowo 适配器自身已经支持：

- customForwardInfo 关闭：使用适配器默认“小助手”身份。
- customForwardInfo 开启，customForwardQQ / customForwardName 留空：分别读取 pluginState.selfId / selfNickname，即当前挂载机器人的QQ头像与实际昵称。
- 填写自定义QQ或昵称：使用适配器的相应自定义值。

这些设置属于**NapCat中的GScore适配器**，不是GsCore的AliceUID设置；会影响该适配器发送的其它插件转发。不同版本UI入口可能不同，源码当前在自定义转发/彩蛋配置中。无需修改账号头像、填写AliceUID的头像QQ或安装NoneBot。如果不调整适配器，就继续保持“小助手”。

[身份读取源码](https://github.com/xiowo/napcat-plugin-gscore-adapter/blob/df1859b396ffbd73bd2b72ce4a35147667281472/src/core/state.ts)通过 get_login_info 获取自身资料；参考的[AstrBot千小妹插件](https://github.com/dddada123/astrbot_plugin_chisa_still_eating/blob/5d4c82a5192a7cfe3418ddc8b17ac6d2178615ef/main.py)也是通过当前机器人uin指定头像，但其示例使用标题作为节点名称，并不能直接当作GsCore的昵称接口使用。

## 实机检查

1. 替换整个 plugins/AliceUID 后重启Core，检查四个独立转发开关；新配置默认开启，旧配置保留原值。
2. 查看首节点标题与完整图片分页；确认成功时Core日志出现“已取得消息ID回执”，未确认则普通回退并暂停该连接转发300秒。暂停期内的普通发送不代表开关失效，可等待5分钟后再测试。
3. 同时查看NapCat的GScore适配器日志。如有“发送回复消息失败”，提供错误码/原因并隐藏个人信息、登录链接及凭据。不要只用Core的“发送消息”行判断成功。
4. JPG质量可先用95或100比较；若仍有Highway网络超时，关闭对应转发开关并排查上传网络。本修订不自动部署或推送GitHub。
