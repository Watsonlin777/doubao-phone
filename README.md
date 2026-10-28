# 变身豆包手机

把一台 Android 真机，变成一台云端 AI 可以对话、可以动手操作的 AI 手机。

> 非官方个人项目，与字节跳动、豆包无关。“变身豆包手机”只是项目名，意思是：让手机像一个随叫随到的 AI 助手一样，听懂一句话，就去打开应用、点按、输入、发送，并把结果报回来。

## 这套组合是什么

一句话：**云端 agent + 手机操控插件 + 个人真机 + 一条你自己搭的远程通道**。

```
你的一句话
  → 云服务器上的 Hermes（AI agent）
    → phone_exec（phone-harness 插件）
      → adb（Android 调试桥）
        → 反向 SSH 隧道
          → 你口袋里的 Android 真机
            → 打开微信 / 点按 / 输入 / 发送 / 读屏核对
```

已经实测走通的例子：

- 云端 Hermes 用 `phone_exec` 给微信文件传输助手发“你好”，只发一条，标题核对、输入法恢复都做了。
- 中文输入走微信输入法拼音 + 空格上屏，不直接输中文字符。
- 每步开头用系统通知发阶段提示，通知栏下拉就能看到当前到哪一步。
- 超时、输错会话、输错输入法这些坑，都写进了 skill 和文档里，不用再踩一遍。

## 仓库里有什么

```
.
├── README.md                  本文件
├── LICENSE                    MIT
├── docs/
│   ├── architecture.md        架构：各件分别干什么、数据怎么走
│   ├── server-setup.md        服务器搭建：Hermes、phone-harness、adb、转发
│   ├── phone-setup.md         手机搭建：无线调试、反向隧道、配对授权
│   ├── safety.md              安全边界：哪些绝不做、审批怎么开
│   ├── stage-notifications.md 阶段通知：shell 通知怎么做、为什么不上药丸
│   ├── reliability.md         可靠性：通道会断、中断不等于失败、保活上限（草稿，未发布）
│   └── generic-agent-loop.md  通用 Agent 循环：参考肉包结构的观察-执行-反思循环（发送纪律除外，未实测）
├── skills/
│   └── phone-wechat-send/
│       └── SKILL.md           微信发消息 skill：标题关卡、中文输入、只发一次
├── scripts/
│   ├── phone/
│   │   └── reverse-tunnel.sh  手机端反向隧道模板（占位符，见文件头）
│   └── server/
│       ├── adb-forward.sh     服务器端 adb 转发模板（占位符，见文件头）
│       └── hermes-send-test.sh Hermes 单次测试模板（占位符，见文件头）
└── examples/
    └── wechat-send-prompt.md  给 Hermes 的任务提示词模板
```

## 快速上手（先读安全，再动手）

1. 先读 `docs/safety.md`，把审批、密码、付费这几条边界定下来。
2. 按 `docs/phone-setup.md` 在手机上开无线调试、做首次配对授权、起反向隧道。
3. 按 `docs/server-setup.md` 在服务器上装 Hermes、phone-harness 插件、adb，做 adb 转发。
4. 把 `skills/phone-wechat-send/SKILL.md` 放到 Hermes 能加载的 skill 目录，确认 `hermes skills list` 里能看到它。
5. 用 `examples/wechat-send-prompt.md` 的模板，先在文件传输助手这种“自己给自己发”的会话里测一条，再去碰真人会话。

## 关键结论（实测，不是推测）

- **不要直接输中文**：`adb input text` 输中文会报错；拼音字母 + 中文输入法联想 + 空格上屏才是走通的路。
- **不要反复切搜狗中英、不要切百度输入法**：前者切不过去，后者会弹出隐私同意页，不要替用户点同意。
- **不要点候选词、不要用剪贴板粘贴**：实测里候选词点按不上屏，后台剪贴板读出来是空的。
- **标题关卡不能省**：进会话先核对顶部标题逐字等于目标名，不对就退出，绝不在错会话里输入。
- **Hermes 一趟要按 10 分钟量级留时间**：实测里一次完整流程接近 10 分钟，超时设 600 秒会被掐掉，设 1200 秒才稳；超时后先查输入框，再决定是补发还是重跑，盲目重跑会把“你好”打成“你好你好”。
- **阶段通知用 shell 通知**：`cmd notification post` 发的通知只在通知栏，不上流体云药丸；Termux 常驻通知实测也没上药丸，药丸要走 Android 16 实时更新，得另外做应用，本项目不做药丸。
- **不要开分类器自动运行**：`classifier_auto_run` 是启发式判断，可以被绕过，保持关闭，审批逐次确认。
- **隧道回来了，不等于 adb 回来了**：转发是手动进程，隧道断了它就死，不会自己复活；恢复要按隧道探活、转发监听、设备状态、输入法的顺序查，见 `docs/reliability.md`。
- **模型在列表里，不等于能用**：换模型前要逐个测短调用和完整手机任务，被打断的那一趟没有耗时结论，不能据此换默认模型，见 `docs/reliability.md`。

## 安全与隐私

- 本仓库**不含任何密钥、密码、Token、真实 IP、手机号、个人账号、个人聊天内容**。所有服务器地址、端口、用户名、密钥路径在脚本和文档里都是占位符，用你自己的值替换。
- 手机操控权限很大：能点按、输入、发送、读屏。默认只在你明确说的会话、明确说的消息上动手；密码、验证码、支付、删东西一律不做，出现这类输入框就停下，把手机交回你手里。
- 不要把这个组合挂到任何公开机器人、群聊机器人上：`phone_exec` 一旦能被陌生人调到，就是别人在动你的手机。

## 致谢与来源

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)（未在仓库里附带，只在文档里引用）
- [phone-harness](https://github.com/ShawnPana/phone-harness)：本项目手机操控的核心件，Hermes 插件提供 `phone_exec`
- [Roubao（肉包）](https://github.com/Turbo1123/roubao)（MIT）：`docs/generic-agent-loop.md` 的结构参考，只借规划、执行、反思、记录的分层与循环形状，未抄代码
- Android adb、scrcpy、Termux 等工具，各归各自作者

## License

MIT，见 `LICENSE`。
