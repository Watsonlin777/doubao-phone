# 真实影子快照汇总（截至 run 20261027-1725，未调用 Jev）

## 总量

- 共 8 个文件、3 趟任务、16 行快照。
- run 20261027-1644：等待 2 行（W1、W2）。
- run 20261027-1705：等待 2 行、标题 2 行。
- run 20261027-1725：等待 2 行、标题 2 行、输入框/锚点 2 行、下一步 2 行、发前门/发后 2 行（五类首次齐全）。

## 各类老逻辑结果（全部为通过，无失败样本）

- 等待/稳定：6 行，均为 W1/W2，W3 0 行（3 趟均未触发横幅遮挡）。
  wait_stable_result 6 行均为 false，readback_ok 为 W1 false、W2 true 的 pattern 出现 2 次（1644、1725），1705 两次均为 true。
  注意：wait_stable_result 全为 false，说明该字段作为“是否稳定”的地面真值不可靠，
  离线对照应以 readback_ok 与后续步骤是否成功为准，不应直接拿 wait_stable_result 当稳定真值。
- 标题：4 行，title_match 均为 true，readback_ok 均为 true。
- 输入框/锚点：2 行，I1 input_empty true，P2 input_match true、anchor_visible true。
- 下一步：2 行，N1/N2 均为 proceed，check_passed 均为 true。
- 发前门/发后：2 行，G1 gate_pass true，G2 send_after_present true、plus_one true。

## 数据质量提醒（离线对照前必须先说明）

1. 全部 16 行老逻辑结果都是通过，没有任何失败、停下、重读样本。
   因此真实 Jev 对照只能检验“Jev 是否误报 unknown”（假阴性），不能检验“Jev 是否误放行”（假阳性），
   更不能据此得出“安全误放行样本为零”的结论。安全结论需要失败样本，而目前数据里没有。
2. run 1725 的标题、输入框、下一步、发前门各点 step_seconds 出现重复值
   （首次核对均为 1.848 秒、二次均为 1.5 秒），逐点耗时不宜当独立实测值用。
   等待类的 step_seconds 变化较大（6.615–26.452 秒），相对可信。
3. 影子文件经核对只含 run_id、决策点、布尔值与耗时，不含消息原文、标题原文、联系人姓名、聊天内容。
   因此给 TypeSafe 的离线对照输入也只会是这些布尔值摘要加固定问题，不会带私人内容。

## 真实 Jev 对照待跑清单（尚未执行，需用户单独授权）

共 16 条对照，问题与阈值均按各阶段 spec 固定不变，通道只走已验证的 TypeSafe，绝不走免费 Zen：

- 等待/稳定 6 条：固定 noul 问题，阈值 0.80，对照 readback_ok 与后续成功。
- 标题 4 条：固定 noul 问题，阈值 0.90，对照 title_match。
- 输入框/锚点 2 条：输入框 noul 阈值 0.90、锚点 noul 阈值 0.85，对照 input_empty / input_match / anchor_visible。
- 下一步 2 条：固定 choice 问题 proceed / re-read / stop，置信度阈值 0.85，对照 next_action。
- 发前门/发后 2 条：发前门 noul 阈值 0.95、发后 noul 阈值 0.90，对照 gate_pass / plus_one。

执行前须确认：只跑以上 16 条，不改 skill、不改看门狗、不切换 Jev 模式、不跑手机任务；
跑完只出一致率与误报 unknown 统计，不据此上线任何一类判断。
