# 相关文献与本项目的差异

核对日期：2026-10-31。定位：混频波动代理预测的探索性实证与复现案例。下面是有针对性的差异对照，不是穷尽性综述，也不是与文献模型在同一数据上重跑的性能排名。

## 方法与证据对照

| 相关工作及已核对来源 | 已有方法 | 本项目的具体差异 | 不能据此声称什么 |
| --- | --- | --- | --- |
| *The impact of economic policy uncertainty on stock volatility: Evidence from GARCH–MIDAS approach*，Physica A 570 (2021), 125794；[出版方摘要和方法预览](https://www.sciencedirect.com/science/article/pii/S0378437121000662) | 用GARCH-MIDAS连接日度股票收益与月度EPU，并研究EPU相对已有波动信息的预测价值 | 先用日度市场特征训练XGBoost，再对其样本外误差加入滞后误差及月度EPU加权项；目标是下一日平方收益率的对数代理，不是直接建立GARCH长短期条件方差分解 | EPU进入混频波动预测不是本项目首创；本项目的GARCH基准不含MIDAS，尚未与该文的EPU-GARCH-MIDAS直接比较 |
| Li, Zhang & Li (2023), *Forecasting stock volatility with economic policy uncertainty: A smooth transition GARCH-MIDAS model*；[出版方摘要、方法及数据预览](https://www.sciencedirect.com/science/article/pii/S1057521923002247)，DOI: 10.1016/j.irfa.2023.102708 | 在GARCH-MIDAS中用平滑转换结构刻画EPU与波动关系的状态变化；研究S&P500与美国EPU及其分类指数 | 本项目用固定候选滞后长度和权重族选择、扩展窗口重估；没有显式平滑转换状态模型，使用CSI300、上证50和纳斯达克 | 不能把滚动重估称为识别了该文意义上的状态转换，也不能据不同市场的分数宣称胜过该文 |
| Wang & Kang (2021), *Forecasting China’s Steam Coal Prices Using Dynamic Factors and Mixed-Frequency Data*；[期刊原文PDF，第4245页方法步骤](https://www.pjoes.com/pdf-131856-67439?filename=Forecasting+China_s+Steam.pdf)，DOI: 10.15244/pjoes/131856 | 先建单因素MIDAS，再用XGBoost预测其误差并修正预测，最后组合修正后的预测；对象是周度动力煤价格与日度驱动因素 | 本项目顺序为XGBoost市场预测→滞后样本外残差与月度EPU-MIDAS修正；频率方向、预测对象和第二阶段不同；增加同重估节奏的无EPU残差AR对照 | MIDAS与XGBoost结合、以第二模型修正误差均已有先例。顺序不同只是可说明的设计差异，不足以证明新算法或预测优势 |
| O’Leary & Rust, *Variable Projection for Nonlinear Least Squares Problems*；[作者机构NIST摘要](https://www.nist.gov/publications/variable-projection-nonlinear-least-squares-problems)，DOI: 10.1007/s10589-012-9492-9 | 可分离非线性最小二乘中消去线性参数的变量投影方法；沿用Golub与Pereyra的既有方法脉络 | 本项目把这一思想用于两参数MIDAS权重估计，增加解析梯度、固定多起点、边界驻点验收与跨依赖敏感性检查 | 变量投影、多起点及梯度检查本身不是本项目的理论创新；通过驻点验收不证明全局最优 |
| Xu & Xie (2021), *Conformal prediction interval for dynamic time-series*；[PMLR原始发表页面](https://proceedings.mlr.press/v139/xu21h.html) | EnbPI围绕bootstrap集成构造序列预测区间，并在特定依赖条件下给出近似边际覆盖论证 | 本项目使用过去绝对预测误差的滚动分位数区间，并在五模型共同日期上评估覆盖、宽度和区间得分；没有实现EnbPI的bootstrap集成 | 不能继承EnbPI的理论覆盖保证；经验覆盖接近名义值也不证明条件覆盖或独立性 |

前两项只据出版方可读取的摘要和方法/数据预览讨论其结构，不推断未读到的训练细节。煤价论文的方法步骤已核对原文。其余两项用于界定优化和区间方法的归属。引用保留学术作者姓名，不包含本项目作者的个人身份资料；未随包附第三方论文全文。

## 本项目可以支持的贡献表述

本项目研究一个具体问题：在已有XGBoost市场预测及残差AR修正之上，月度EPU项是否带来可重复的额外预测信息。主要可复查内容是三市场对照、残差AR消融、损失函数之间的权衡，以及输入日历、树模型列抽样和第二阶段求解器的复现审计。

当前结果显示，DEC相对XGB-Market和XGB-AR在三市场均降低QLIKE、提高对数MSE；中国两个市场的MAE下降，纳斯达克的MAE上升。CSI300的共同日期区间没有显示DEC改善区间得分。这些是本样本上的结果，不是普遍优势或EPU因果效应。[汇总与限制](../results/revised/README.md)、[方法修订证据](dec-method-review.md)给出对应数据。

因此，推荐表述为“组合预测与复现方法的应用研究”，而不是“首创XGBoost-MIDAS”“证明EPU普遍提升预测”或“新型共形预测保证”。本页补充发布材料的研究定位，不改变论文中的实验数值、方法或结论。

## 仍需怎样的比较才能加强研究

1. 在同一输入版本、预测时点、目标和日期上增加EPU-GARCH-MIDAS基准；当前普通GARCH不能替代它。
2. 增加把可得EPU直接作为XGBoost特征的对照，区分混频权重结构和单纯增加信息的作用；当前残差AR对照仅隔离第二阶段EPU项。
3. 使用EPU真实发布/修订版本及新的留出时期，并报告多重规格选择带来的不确定性。

这些是后续研究建议，尚未执行，也没有列入当前实验成果。合成示例只检验运行链路，不能弥补上述实证证据缺口。
