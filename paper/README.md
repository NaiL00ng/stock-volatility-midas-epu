# 中英文论文与引用

当前版本：0.5-review。整理日期：2026-10-31。作者：Boursin Nickel。两份论文作为[项目仓库](https://github.com/NaiL00ng/stock-volatility-midas-epu)的研究稿分发，不代表期刊发表或同行评审通过。

| 版本 | 成品与源码 | 定位 |
| --- | --- | --- |
| 中文公开修订版 | [PDF](thesis-public.pdf)、[LaTeX入口](source/main.tex) | 保留完整研究说明、当前结果和历史复现附录；加入许可页，修正一处舍入笔误 |
| English research edition | [PDF](thesis-en.pdf)、[LaTeX entry](english-source/main.tex) | 英文研究稿，按研究论文结构重组表述；不是逐句翻译，不是新增实验或独立验证 |
| 共用参考文献 | [BibTeX](references.bib) | 保留原学者与公开文献机构的真实归属 |

若GitHub内嵌PDF预览无法加载，可直接下载[中文PDF](https://raw.githubusercontent.com/NaiL00ng/stock-volatility-midas-epu/main/paper/thesis-public.pdf)或[English PDF](https://raw.githubusercontent.com/NaiL00ng/stock-volatility-midas-epu/main/paper/thesis-en.pdf)，也可从克隆后的paper目录打开。

英文稿覆盖目标定义、数据与样本、HAR/GARCH/XGBoost、MIDAS与稳定DEC求解、XGB-AR消融、三市场结果、30组区间设置的核心汇总、探索性推断、历史训练配置及数值控制。现有研究具备编写英文研究稿的完整结构和证据，但仍不能据此声称达到期刊录用标准或已验证实时预测能力。

两个版本共用相同结果CSV和原图，不独立维护一套英文实验值。PDF保留上传前已审阅的0.5-review成品；许可页中的“本地修订”“候选版”和未提供仓库URL的表述记录编译时状态，当前获取与引用地址以本页为准。公开上传不产生新实验或改变论文数值。原始数据不随包提供，完整实验需要自备授权输入；最小合成示例不代表论文结果。研究方法、当前/历史入口和样本口径见[版本表](../docs/version-map.md)、[运行说明](../docs/reproduction.md)与[数据说明](../data/README.md)。

## 本次一致性修正

XGB-AR在CSI300主区间设置下的得分为9.879349911097734，四位小数应为**9.8793**。既有CSV及正文表格正确；本次只统一原摘要、结论、README及方法记录中写成9.8794的文字。实验CSV、图件、训练配置和研究代码没有因此修改。英文稿采用9.8793。

## 编译

需要已安装的XeLaTeX、BibTeX及常见TeX Live数学、图表和参考文献宏包。中文另需ctex及Fandol；英文使用fontspec及Latin Modern。编译不需要私人数据或运行机器学习代码。

进入`paper/source/`编译中文，或进入`paper/english-source/`编译英文，分别执行以下相同命令：

```bash
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
bibtex main
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
```

两个目录分别生成`main.pdf`；需保留相对路径，使源码能找到`../references.bib`和`../../results/`中的图件。已审阅成品保存在本目录，不应由未经检查的新编译自动替换。临时LaTeX产物和两处`main.pdf`均不属于上传候选清单。PDF生成日期等构建元数据可能随编译改变；分发SHA256验证的是已审阅成品，不承诺独立编译字节一致。

本次两份PDF在macOS上的现有TeX环境编译并检查；此前Windows/Linux最小示例验证不等于已在这些系统编译论文。

## 论文引用

中文：Boursin Nickel（2026）。《基于机器学习与动态误差修正的股指波动率预测研究》。公开研究修订版，0.5-review，2026-10-31。

English: Boursin Nickel (2026). *Stock Volatility Forecasting with MIDAS EPU Correction: Stable Estimation, Residual Ablation, and Retrospective Reanalysis*. English research edition, version 0.5-review, revised 2026-10-31.

可复制的英文稿BibTeX条目：

```bibtex
@misc{BoursinNickel2026Volatility,
  author = {{Boursin Nickel}},
  title = {Stock Volatility Forecasting with {MIDAS EPU} Correction:
           Stable Estimation, Residual Ablation, and Retrospective Reanalysis},
  year = {2026},
  url = {https://github.com/NaiL00ng/stock-volatility-midas-epu},
  note = {English research edition, version 0.5-review, revised 2026-10-31}
}
```

引用项目软件时使用根目录[CITATION.cff](../CITATION.cff)。仓库来源为[NaiL00ng/stock-volatility-midas-epu](https://github.com/NaiL00ng/stock-volatility-midas-epu)；尚无DOI、期刊或同行评审信息，不填写虚构条目。两种语言是同一研究的版本，不应计作两项独立实证证据。

## 许可与第三方边界

作者有权许可的中英文论文文字、LaTeX内容及原创图表采用[CC BY 4.0](../LICENSE-CONTENT.txt)，配套代码采用[Apache-2.0](../LICENSE)。两份PDF均有独立许可页。许可不覆盖第三方文献、底层数据或内嵌字体；详见[许可范围](../docs/licensing.md)与[第三方说明](../THIRD_PARTY_NOTICES.md)。署名保留Boursin Nickel，不包含作者学校、私人联系方式或致谢。
