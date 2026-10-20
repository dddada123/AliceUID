# GsCore 数据库管理接入（1.0.0）

参考 XutheringWavesUID 的 `@site.register_admin` / `GsAdminModel` / `PageSchema` 注册已有表的方式，不改变 `AliceBind`、Fernet 密钥或 `data/AliceUID`。管理页入口为 AliceUID → 用户绑定管理（脱敏只读）。不依赖插件是否上架商店。

注册前安装仅作用于 `/api/database/table/alicebind` 的服务端保护。普通分页和CSV导出仅保留身份摘要、区服、有效期及公开/主账号标志；不返回 Cookie 密文或 openid。通用新增、编辑、导入和删除返回409，避免绕过加密、绑定校验和任务撤销。其它插件接口保持原样。CSV为脱敏摘要，不能用于恢复登录。

管理接口需要 GsCore 当前的 `webconsole.mount_app`、`app_app`、`web_api.require_admin`、`utils.database.admin_api`。缺少新版管理接口时记录兼容性提示，正常登录和查询继续可用。部署后需完整重启Core，不在运行中临时修改中间件链。

## 专用解绑

`POST /api/aliceuid/bindings/{id}/unbind`，复用Core管理员认证。JSON为 `user_id`、`bot_id`、`binding_version`；最后一项由分页数据接口返回，为密文的SHA256，不能解密登录信息。必须使用最新列表值。

专用接口根据id读取绑定，验证用户/Bot和版本，再通过 `AliceBind.delete_bind(..., expected_revision=...)` 在绑定锁内二次检查、撤销社区授权和删除绑定，随后清除旧登录会话及衍生缓存。新登录已替换版本时拒绝旧确认，不会误删新绑定。

通用表格按钮不承担解绑生命周期；界面显示为只读。正常用户通过 `nk解绑`，更新凭据通过 `nk重新登录`。专用接口不提供批量清库，不修改用户群权限或社区预算。

验证见 `test_v100_admin.py`：FastAPI/ASGI、GZip、分页/CSV脱敏、其它插件隔离、管理员认证、真实SQLite版本复核及解绑后的撤销。它不替代用户NAS上的最终实机验收。
