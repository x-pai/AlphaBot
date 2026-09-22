# 系统机器人与个人渠道管理

系统提供一个 QQ、Telegram、飞书机器人，用户绑定自己的 AlphaBot 账号。消息入口和发送工具共用身份/接收目标服务；不会把 Telegram 用户映射到固定的 user.id=1。

## 部署

安装更新后的 `requirements.txt`，在后端 `.env` 或部署环境中配置：

```dotenv
QQ_BOT_ENABLED=true
QQ_BOT_APP_ID=你的机器人AppID
QQ_BOT_APP_SECRET=你的机器人AppSecret
QQ_BOT_LOCK_PATH=/tmp/alphabot-qq.lock
TELEGRAM_ENABLED=true
FEISHU_ENABLED=true
WEBHOOK_ENABLED=true
```

其余 TG、飞书凭证沿用 `.env.example`。QQ 默认关闭；其他渠道默认开启以兼容已有部署，没有凭证则不可用。关闭渠道同时停止入站和出站；定时任务仍生成报告，单独记录通知失败。环境变量修改后重启后端。

QQ 通过 WebSocket 主动连接腾讯，订阅 C2C 和群 @ 消息，无需公网回调。实现 Identify、Heartbeat/ACK、Resume、会话失效重新鉴权、指数退避重连。收消息与 Agent 处理分开，队列有容量限制。REST 使用 `https://api.bot.qq.com`，Token 在内存缓存并按有效期刷新。超时且发送结果不确定时不自动重复 POST。

同一主机多个进程使用文件锁，仅一个进程接收 QQ 事件。容器副本应共享锁文件所在卷；多主机部署请仅在一个接收实例开启 QQ 接收服务（本版本未实现分布式网关选主）。部署建议继续使用当前 docker-compose 的单后端实例。文件锁适用于 Linux/macOS。

TG 默认使用现有长轮询。若使用 Telegram webhook，配置 `TELEGRAM_WEBHOOK_SECRET` 并在 Telegram `setWebhook` 中指定同样的 `secret_token`；配置后不启动轮询。飞书仍使用事件回调，必须配置 `FEISHU_VERIFICATION_TOKEN` 或 `FEISHU_ENCRYPT_KEY`，以验证绑定指令的来源。此次未新增飞书 WebSocket。

凭证不写入绑定记录或返回给浏览器。`.env` 不提交 Git，文件权限建议设为 `600`。Webhook 地址由用户管理并存于数据库，不在列表响应中回显完整 URL。只接受公网 HTTPS，发送时固定已验证的 DNS 地址、保持 TLS 主机校验、不跟随重定向；原有 HTTP/内网 Webhook 升级后需调整。

## 用户操作

主页用户菜单 → **系统管理 → 消息渠道 → 个人渠道管理**（`/system#channels`）：

1. 点击 QQ/TG/飞书的「绑定账号」。
2. 在对应机器人私聊发送 `绑定 <绑定码>`（也支持 `/bind <绑定码>`）。
3. 绑定码 10 分钟有效，仅存摘要、单次使用、限制生成频率和尝试次数。
4. 绑定弹窗显示倒计时与复制反馈，每 3 秒自动确认绑定结果，成功后显示完成状态；私聊目标自动生成。
5. 添加群目标时先完成私聊绑定，再用同一渠道身份在群内 @机器人发送群绑定码。
6. 在个人区域切换渠道，可通过弹窗修改目标备注、测试发送、删除目标或解绑；失败详情支持展开和复制。解绑会删除该用户在该机器人下的全部接收目标并撤销未使用绑定码；原有任务不会自动转到其他目标。

不同用户的绑定和目标相互隔离。每次业务发送在服务端检查目标归属。群目标只授权给完成绑定的申请人，不向群内所有用户共享权限。群内对话上下文按渠道、机器人、群、发送者和系统用户隔离。群成员身份的绑定证明不等于平台群管理员权限。

系统管理 → **消息渠道**上方的「系统消息渠道」仅管理员可见，显示配置/启用状态，QQ 额外显示当前进程的连接状态。下方「个人渠道管理」对所有登录用户可见，只管理自己的绑定和接收目标。凭证和总开关仍在服务端配置，不在网页编辑。

## 每日任务与预警

Agent 每日任务选择渠道和已绑定的接收目标，任务只保存 `target_id`。报告发布成功后，各渠道统一发送标题和报告链接。外部链接需配置可从接收者网络访问的 `APP_PUBLIC_BASE_URL`。

「仅补发最近通知」发送上次任务保存的通知内容，不再次执行 Agent。先保存目标变更再补发；该操作会重新发送一条通知，应仅在需要补发时使用。QQ 主动接收开关、消息权限和平台频控可能影响送达。API 接受成功不等同于用户已读。

预警和 `send_channel_message` 工具使用同一接收目标校验。未绑定群仍可与已绑定用户对话，但不会自动获得该群的主动通知目标。

## 兼容与数据迁移

数据库初始化自动创建新表，并执行带版本标记的迁移：

- 飞书现有 `feishu_<openid>` 账户映射到配置中的飞书机器人，保持原账户归属，不创建新的渠道用户。
- 有明确 user_id 的旧每日任务和预警推送配置导入该用户的接收目标；身份绑定不由旧 Chat ID 推断。
- 没有明确用户或机器人配置的旧目标保留原配置，发送时提示待确认，需要重新绑定选择。
- TG 原共享账户的历史数据不自动划分给个人。
- 飞书身份已属于其他账户时拒绝覆盖，保留历史数据。跨账户数据合并不属于本次实现，需管理员另行处理。
- 机器人更换后旧 OpenID 不复用，用户重新绑定。

## 验证

```sh
cd backend
.venv/bin/python -m pytest app/tests/test_channels.py app/tests/test_phase2_alert.py app/tests/test_phase5_registries.py -q
cd ../frontend
npm run build
```

测试使用模拟 QQ HTTP/WebSocket，不会向真实用户发消息。生产启用后还需实际测试：私聊绑定、多轮对话、群绑定及 @ 回复、主动推送、接收开关关闭、重启恢复。

官方协议参考：
- https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/api-call-guide.html
- https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html
