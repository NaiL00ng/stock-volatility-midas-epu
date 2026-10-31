# 当前论文的修订结果

日期：2026-10-31。对应版本0.5-review，完整解释见[方法修订记录](../../docs/dec-method-review.md)。

| 内容 | 文件 | 口径 |
| --- | --- | --- |
| 三市场五模型 | [汇总](point_metrics.csv)、各市场子目录 | 正文上证50使用calendar_corrected；historical_input仅用于控制 |
| 当前规格 | 各市场midas_dec_best_spec.csv及search_results | CSI300、上证50为K24指数Almon；纳斯达克为K12指数Almon |
| 旧数值差异 | [旧复现与存档](legacy_metric_comparison.csv) | 同历史输入，不是新算法效果 |
| 损失差诊断 | [18项HAC/Holm](loss_difference_diagnostics.csv) | mean_A_minus_DEC为正表示DEC更低；探索性，不作确认性因果结论 |
| 稳定求解 | [146次诊断](optimizer_checks.csv) | mean_sse目标；不证明全局最优 |
| 独立梯度/训练目标 | [当前栈](solver_current_training_objective_checks.csv)、[旧栈](solver_old_training_objective_checks.csv) | 每栈108次，有限差分与对应旧求解比较 |
| 跨依赖预测 | [当前重复](solver_current_prediction_sensitivity.csv)、[旧依赖](solver_old_prediction_sensitivity.csv) | 对比正文新DEC，不是匹配历史DEC |
| 固定历史规格控制 | [纳斯达克K12 Beta](solver_current_fixed_spec_metrics.csv) | 仅为分解求解与重新选规格的影响 |
| 环境 | [主体运行](runtime.json)、[当前栈](solver_current_runtime.json)、[旧栈](solver_old_runtime.json) | 两套均为本地试验环境，不称为原环境 |
| 区间 | [30组共同日期结果](intervals/interval_common_dates.csv)、[覆盖诊断](intervals/coverage_common_dates.csv)、[独立构造核验](intervals/interval_checks.csv) | 五模型×2名义水平×3窗口，每组1859共同日期 |

图件与当前表一致。XGB-AR为只含截距与已实现滞后残差的对照。区间表不再使用旧版0.8“有效”告警标签作为结论；以经验覆盖、宽度、得分和覆盖诊断一起解释。

仅分发汇总及研究图。逐期价格、预测、残差、所有起点日志和二进制缓存留在本地generated中，不随包分发。历史目录中的CSV和PNG未覆盖。

样本口径统一见[数据说明](../../data/README.md)与[机器可读记录](../../configs/sample-splits.json)。新增的[合成示例](../../examples/README.md)只用于运行体验，其分数不属于本结果目录。
