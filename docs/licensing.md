# 许可证与适用范围

采纳日期：2026-10-31。对应版本：0.5-review。Copyright © 2026 Boursin Nickel。

作者已正式采纳：**代码采用Apache-2.0；论文、说明文档和原创图表采用CC BY 4.0。** 授权仅覆盖作者拥有或有权再许可的部分。这是按材料分别适用不同条款，不是使用者可在两个许可证之间任选；本地采纳日期不是GitHub发布日期。

完整标准条款分别保存在[LICENSE](../LICENSE)和[LICENSE-CONTENT.txt](../LICENSE-CONTENT.txt)，归属说明见[NOTICE](../NOTICE)。本页是范围说明，不修改许可证条款。

| 材料 | 正式许可范围 | 边界 |
| --- | --- | --- |
| scripts/、examples/中的Python代码，configs/配置，requirements依赖清单，.gitignore、.gitattributes等运行配置 | Apache-2.0 | 第三方适配部分和原有声明保留上游条件 |
| paper/中的中英文PDF、作者撰写的LaTeX内容，README、docs/、data/和results/中的说明文字，CITATION.cff等引用编排 | CC BY 4.0 | 第三方引文及PDF内嵌字体不改授为作者所有 |
| results/、docs/中的原创研究图、方法图及原创表格编排 | CC BY 4.0 | 论文内与单独导出的同一张图保持相同授权；不许可其底层第三方数据 |
| 文档中的可执行代码或命令示例 | Apache-2.0 | 与周围叙述文字的CC BY 4.0区分 |
| 分发的数值CSV、指纹、环境JSON及其他结果汇编 | CC BY 4.0，仅限作者拥有的版权及数据库权利 | 不主张对单纯事实或数值拥有排他权；不扩大数据供应方授权 |
| 第三方源码适配、许可证文本、依赖、引文与字体 | 各自原有条件 | 见[第三方说明](../THIRD_PARTY_NOTICES.md)，不被上述项目许可覆盖或替换 |
| 未分发的行情/EPU工作簿、逐期数据及预测面板、模型二进制、本地日志 | 不纳入本次授权或分发 | 数据使用及再分发条件仍须按来源核实 |

## 使用与署名

Apache-2.0允许按条款使用、修改及分发代码，包括商业用途；保留适用版权和归属说明、提供许可证、标明修改，并遵守NOTICE相关要求。其贡献者专利许可有明确范围，不要求所有下游修改均公开。[Apache官方条款](https://www.apache.org/licenses/LICENSE-2.0)

CC BY 4.0允许分享和改编原创学术内容，包括商业用途；应适当署名、提供许可链接并指出修改，不得暗示作者为使用者背书。对遵守条款的使用，已给予的许可不能随意撤销。完整条款而非本页摘要决定权利义务。[CC BY 4.0官方说明](https://creativecommons.org/licenses/by/4.0/)

内容署名可写为：

> Boursin Nickel，*Stock Volatility Forecasting with MIDAS EPU Correction*，0.5-review（2026年研究修订稿），CC BY 4.0，https://creativecommons.org/licenses/by/4.0/ 。材料来源：https://github.com/NaiL00ng/stock-volatility-midas-epu。如有修改，请说明修改。

软件引用见[CITATION.cff](../CITATION.cff)，中英文论文引用见[论文说明](../paper/README.md)。学术引用是研究使用建议，不是对Apache-2.0添加“必须引用论文”的限制。未设定仅限学术使用、禁止商业使用或禁止改编等附加条件。

## 第三方与数据边界

[第三方说明](../THIRD_PARTY_NOTICES.md)保留XGBoost 2.0.3与Microsoft STL vs-2022-17.6的具体来源、适配用途、版权和上游许可证；LLVM例外只适用于符合其条件的上游材料。依赖清单不重新授权依赖库。参考文献作者及第三方版权主体不因项目作者采用化名而替换。

中英文论文中的Fandol、Latin Modern及Computer Modern/AMS嵌入字体保留上游条件。引用他人的文献不授予其全文、图件或数据库的权利。本次没有打包第三方论文全文、独立字体、依赖wheel或编译库。

原创图表与汇总的许可不能自动许可底层行情或EPU数据库。当前包不分发原始工作簿、逐期价格/预测和模型；输入来源、未核实的版本及再分发限制见[数据说明](../data/README.md)。该范围说明不是对全部历史材料法律权属的保证。

## 本次落实状态

根目录标准许可文本、NOTICE、中英文论文许可页、README、软件引用信息、逐项清单和SHA256已同步。第三方上游许可证原文保留。项目公开仓库为[NaiL00ng/stock-volatility-midas-epu](https://github.com/NaiL00ng/stock-volatility-midas-epu)；许可采纳与具体发布事件分开记录，发布状态见[版本说明](release-notes.md)。
