# 正式版本与代码、结果对应

日期：2026-10-31。当前候选版本0.5-review。原始档案不改，历史和修订结果分开。

| 内容 | 代码/配置 | 结果 | 对应关系 |
| --- | --- | --- | --- |
| 当前中文论文 | [源码](../paper/source/main.tex) | [PDF](../paper/thesis-public.pdf) | 正文采用下列修订实验 |
| 英文研究稿 | [英文源码](../paper/english-source/main.tex)、[版本与引用](../paper/README.md) | [英文PDF](../paper/thesis-en.pdf) | 重组英文表述；与中文同一组实验、表格、图件和限制，不是新增实验 |
| 当前DEC与消融 | [运行入口](../scripts/run_dec_revision.py)、[稳定求解](../scripts/dec_stable.py)、[规则](../configs/dec-revision.json) | [当前结果](../results/revised/README.md) | CSI300/SSE50为K24指数Almon；Nasdaq为K12指数Almon |
| 当前CSI300区间 | [新入口](../scripts/run_revised_intervals.py) | [共同日期结果](../results/revised/intervals/interval_common_dates.csv) | 五模型30组，每组1859共同日期 |
| 数值稳定核验 | [检查入口](../scripts/check_dec_solver.py) | [跨依赖比较](../results/revised/solver_old_prediction_sensitivity.csv) | 新方法最大差异小于1e-7；不是还原历史DEC |
| 历史点预测 | [历史主脚本](../scripts/csi300_epu_final_from_oldcode.py)、[匹配入口](../scripts/reproduce_historical_xgb.py)、[配置](../configs/experiments.json) | [CSI300](../results/csi300/)、[SSE50](../results/sse50/)、[Nasdaq](../results/nasdaq/) | 6888条XGBoost匹配；旧DEC未精确还原；旧Nasdaq为K12 Beta |
| 历史CSI300区间 | [原区间脚本](../scripts/conformal_interval_experiment.py) | [历史区间](../results/intervals/) | 24组原样保留，不是当前论文数值 |
| 当前描述统计 | [统计入口](../scripts/csi300_descriptive_statistics.py) | [修正统计](../results/descriptive-corrected/) | 3942价格形成3941收益率，已用于论文 |
| 历史描述统计 | [来源追查](../scripts/trace_provenance.py) | [历史统计](../results/descriptive/) | 额外零值可重构24项，保留追溯 |

上证50旧划分1500/500/1915，修订划分1500/500/1919；CSI300为1500/500/1919，Nasdaq为2000/500/1554。新方法与历史复现的详细区别见[DEC修订记录](dec-method-review.md)。原21张CSV、19张PNG保留。

发布准备补充：[合成示例](../examples/README.md)仅演示当前实现，不是正文实验；[样本口径](../configs/sample-splits.json)统一当前/历史样本；[文献差异](related-work.md)说明研究定位。实证结果与论文仍对应0.5-review，发布前演练未改动其数值。

本次落实Apache-2.0代码与CC BY 4.0原创内容许可，增加英文研究稿，并统一XGB-AR区间得分为按CSV四舍五入的9.8793；实验数值和配置不变。继续保留0.5-review，未新建正式发布标签。当前交付范围和未定发布信息见[候选版说明](release-notes.md)。
