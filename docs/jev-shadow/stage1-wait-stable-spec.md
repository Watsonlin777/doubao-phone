# Jev 手机任务影子记录 Stage 1 — 等待/稳定判断（仅影子，不改行为）

状态：方案已确认，生产 skill v1.3.12 与看门狗 v1.8.1 未改动；本文件是 Stage 1 的定义与离线复现规范，不是生产 skill 的一部分。
下次手机任务经用户单独授权后，才按本文件在任务外积累影子数据；Jev 模式仍为 shadow，未切换，默认模型仍为 medium。

## 1. 决策点（skill v1.3.12 中 wait_stable() 仅有的三处）
- W1：打开微信后
- W2：点发送后
- W3：标题被通知横幅遮挡后（第一次读屏未通过时）

其他步骤不无条件等稳定，读屏结果本身就是稳定判断，读屏失败再补一次 wait_stable()。影子记录只覆盖 W1/W2/W3，不新增等待点。

## 2. Jev 问题定义（固定措辞，现场不改写）
- 问题类型：noul（是/否）
- 问题：`Is the screen now stable enough to read reliably, with no loading indicator, no banner covering the title, and no UI still changing?`
- state：本次 wait_stable() 前后两次读屏的文字摘要（只含界面文字、标题、输入框状态、底部锚点可见性，不含聊天内容全文、不含联系人以外的私人信息；手机任务数据不走免费 Jev，只走已验证的 TypeSafe 通道）。
- 阈值初值（待影子数据校准，不作上线标准）：
  - noul >= 0.80：影子判断为“已稳定”
  - noul < 0.80：影子判断为“未稳定”
  - Jev 不可用、超时、置信度缺失：记为 unknown，不回落、不改动作
- 对照项（老逻辑的实际结果）：
  - wait_stable() 返回值（稳定/未稳定/超时）
  - 随后读屏是否成功、是否需要重读
  - 该步实际耗时（秒）

## 3. 影子日志格式（每行一条 JSONL，不写进生产状态文件）
文件：下次任务时由任务外脚本写到任务目录的 `jev-wait-shadow.jsonl`（生产状态文件与看门狗逻辑不动）。
字段：
- run_id, decision_point (W1/W2/W3), timestamp
- jev_noul, jev_judgement (stable/unstable/unknown), jev_latency_ms, jev_provider (typesafe)
- old_logic_result (stable/unstable/timeout), readback_ok (true/false), step_seconds
- agree (true/false/null，unknown 时为 null)

## 4. 离线复现流程（不影响 live 手机任务）
1. 任务结束后，从任务记录中提取 W1/W2/W3 的两次读屏摘要与老逻辑结果，写成快照文件（见 replay 脚本的 --dry-run 示例格式）。
2. 用 `jev route`/`jev decide` 的离线方式对快照逐条跑 Jev（provider 固定 typesafe，不用免费 Zen，不用 Hermes 聊天模型），只写影子日志，不改任何任务结论。
3. 汇总：一致率、误判（Jev 说稳定但随后读屏失败）、漏判（Jev 说未稳定但随后读屏一次成功）、平均 Jev 耗时。
4. 上线标准（未达成前不推广）：影子样本足够且误判为零；等待判断的收益只认“Jev 说稳定且随后读屏成功”的样本所省下的固定等待时间，不认单次快慢。

## 5. 明确不做
- 不替换精确标题核对，不替换输入框空/底部锚点的确定性检查。
- 不把 Jev 判断接入控制流，不因 Jev 说稳定就跳过 wait_stable()，不因 Jev 说未稳定就多等或重发。
- 不改默认模型、不改 skill 主流程、不改看门狗阈值、不跑手机任务、不切换 Jev 模式。
- 不用免费 Zen Jev 跑手机任务数据（免费层曾被拒、且训练声明不明），不把手机屏幕/微信内容发给免费通道。
- 下一步（标题预筛、输入框/锚点预筛、下一步动作、发前门）按风险顺序依次重复本文件的流程，每种判断单独验收、单独上线，不批量上线。
