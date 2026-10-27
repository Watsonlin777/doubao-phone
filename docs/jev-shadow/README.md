# Jev 影子对照分支（shadow-only，未切换）

本分支记录云端 Hermes 手机任务里 Jev 决策层的影子对照工作，不改变手机任务的主流程。

- 生产 skill 当前版本：v1.3.17（见 `skills/phone-wechat-send/SKILL.md`，已去掉作者行，其余与生产版一致）。
- 看门狗：v1.8.1，未随本分支改动。
- Jev 模式：shadow-only，未切换。默认手机模型仍为 medium，Jev 不实际改模型、不决定发送。
- Jev 通道：已验证的 TypeSafe 通道，不走免费 Zen 通道。手机任务数据不走免费层。

## 五类影子记录（按风险从低到高）

1. 等待/稳定：`stage1-wait-stable-spec.md`，阈值 0.80，决策点 W1/W2/W3。
2. 标题预筛：`stage2-title-prescreen-spec.md`，阈值 0.90，决策点 T1/T2。
   标题精确核对永远是确定性最终门，Jev 预筛只能决定是否重读，不能决定发送。
3. 输入框/锚点预筛：`stage3-input-anchor-prescreen-spec.md`，
   输入框阈值 0.90、锚点阈值 0.85，决策点 I1/P2。
4. 下一步动作：`stage4-next-action-spec.md`，choice 置信度阈值 0.85，决策点 N1/N2，
   选项只有 proceed / re-read / stop，绝不直接选“发送”。
5. 发前门与发后核对：`stage5-presend-postsend-spec.md`，
   发前门阈值 0.95（全方案最高）、发后阈值 0.90，决策点 G1/G2。
   发前门不能替代用户当次确认，发后核对不能改变 fail-closed 判定。

每类影子文件只记布尔值与耗时，不记消息原文、标题原文、联系人姓名、聊天内容。
任务内禁止调用 Jev，Jev 判断一律任务结束后离线做；影子记录失败忽略并继续，绝不因记录失败而停下或重发。

## 离线复现脚本

`scripts/jev-shadow/` 下的 5 个脚本均为 dry-run 合成数据复现，不调用 Jev，
不触碰真实手机任务，不写生产状态文件。真实 Jev 调用需单独授权，且只走 TypeSafe。

## 评估与审查（截至 2026-10-27）

- `real-shadow-summary.md`：3 趟任务、16 行真实快照的汇总。
- `evaluation-memo.md`：已证明弱证据、未证明缺口、上线三条前置条件现状。
- `adversarial-review.md`：对抗性审查，结论是目前不能上线任何一类 Jev 判断，
  主要缺口是失败样本缺失、屏上证据缺失、阈值未校准、逐点耗时不可信。

本分支不是上线分支，任何一类上线都须单独验收、单独授权。
