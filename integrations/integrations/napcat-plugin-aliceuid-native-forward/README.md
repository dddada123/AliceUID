# AliceUID 原生图片转发配套插件（实验性）

**candidate3已恢复标准转发主线，不需要安装本配套。** 本目录保留candidate2可选实验源码，不能自动启用。若此前已安装本配套，要测试fix1标准路线请先禁用并重启NapCat；下面安装步骤只适用于主动选择原生实验路线时。

用于NapCat 4.18.37与AliceUID 1.0.08 candidate2。只处理AliceUID帮助、图鉴卡片、出刀的“文字标题＋完整单图”转发，沿用现有GScore适配器连接。登录链接与其它插件沿用原路线。

## 安装

1. 更新GsCore端的AliceUID插件，并保留原data/AliceUID、数据库和密钥。
2. 将本目录整层napcat-plugin-aliceuid-native-forward放入NapCat的plugins目录，与现有GScore适配器目录同级；可使用发行版提供的独立NapCat配套ZIP。文件夹内应直接包含package.json、index.mjs和本说明。
3. 在NapCat插件管理中启用本插件，重启NapCat与Core。首次启动应看到`[AliceUID Native] enabled for AliceUID card forwards only`。不兼容时会显示inactive，不要将其视为已启用。
4. 先测试nk帮助，再测试nk出刀和nk卡片。命令在Core中仍可自定义前缀。转发开关已保存为关闭时需手动开启，新的默认值不覆盖旧设置。

**需要Core插件和本NapCat配套同时安装。** 只更新AliceUID不能把远端NapCat切换到原生路径。无需修改GScore适配器、全局packetBackend、账号头像或配置Token，也不需要NoneBot。

## 发送流程

Core先把编码完成的成品图原子写入data/AliceUID/cache/forward_outbox，读取并校验后再发送。缓存上限64MiB、32张，15分钟有效，后续写入时清理过期文件；只缓存图片，不缓存登录链接/二维码，不提供公开下载接口。

本插件按AliceUID固定预览标题和单图结构识别输出，在该次调用专用对象上选择原生准备流程：

`准备文字/图片元素 → 发送到机器人自身会话 → 每个节点取得自身消息ID → 原生合并转发到原群`

因此会在机器人自身QQ会话留下用于合并的文字和图片消息；不会先把临时完整图发进目标群再撤回。自身消息属于QQ历史，Core本地缓存的15分钟清理不代表删除这些QQ消息。全部节点齐全才合并，部分失败不发送缺图/仅标题的转发。

不修改全局Packet状态；其他插件和普通消息保持原路。使用当前账号的原生自身消息作为转发来源，最终头像/昵称以QQ实机显示为准。依赖4.18.37中的发送方法，未来NapCat更新后应重新验证。

## 日志与失败处理

- `route=native_cached`：已识别并采用原生路径。
- `stage=cache_ready`：文字或图片元素准备完成。
- `stage=self_confirmed nodes=1/2`：自身会话节点已确认。
- `stage=merge_confirmed`：取得原生合并发送结果。
- `outcome=unconfirmed`：在所标阶段失败或超时，交给Core按原逻辑回退一次普通消息；不再改走Packet重复尝试。

单次总预算8秒，避免长期占住Core等待；同一实例同时只进行一次此类原生准备，并发新请求会有限失败回退。QQ发送无法强制撤销已发起的网络操作，最终合并迟到成功时仍可能与普通回退重复。缓存、节点确认和离线验证不能保证实际QQ网络发送成功。

## 卸载与恢复

禁用此NapCat插件并重启NapCat，发送方法恢复原实现；如需继续稳定使用普通图片，在Core后台关闭对应转发开关。无需更改全局Packet设置或删除运行数据。旧candidate1及正式1.0.07包可继续作为回退包。
