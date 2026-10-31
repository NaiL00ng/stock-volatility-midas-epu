# 第三方来源与许可说明

核对日期：2026-10-31。本文记录公开候选材料中的第三方关联；不替代第三方已有条款，也不声称完成全部历史代码或数据的权属审计。本项目原创部分的正式许可范围见[许可证与范围](docs/licensing.md)。

## XGBoost诊断构建

- 上游：dmlc/xgboost，v2.0.3，Apache-2.0；上游许可证中的版权声明为“Copyright (c) 2019 by Contributors”。[上游许可证](https://github.com/dmlc/xgboost/blob/v2.0.3/LICENSE)及[随包保存的原文](third-party/XGBoost-LICENSE.txt)。
- 对应材料：[兼容补丁](scripts/patch_xgboost_sampling.py)及[本地构建说明](docs/reproduction.md)。补丁核对src/common/random.cc的原SHA256，插入可选的列洗牌逻辑并添加cstdlib头文件引用。
- 修改用途：区分列抽样实现造成的数值差异，不是上游官方版本，也不是恢复出的原始二进制。上游版权与许可不因修改而消失。
- 当前分发包不包含XGBoost源码树、wheel、编译库或模型。若以后分发修改后的源码或二进制，须按届时实际分发内容保留适用许可证、修改声明和上游NOTICE，不能只沿用本页链接。

## Microsoft STL算法参考

- 上游：microsoft/STL，vs-2022-17.6，stl/inc/algorithm；版权声明“Copyright (c) Microsoft Corporation.”，标识为Apache-2.0 WITH LLVM-exception。[源文件](https://github.com/microsoft/STL/blob/vs-2022-17.6/stl/inc/algorithm)、[上游许可证](https://github.com/microsoft/STL/blob/vs-2022-17.6/LICENSE.txt)及[随包保存的原文](third-party/Microsoft-STL-LICENSE.txt)。
- 对应材料：[patch_xgboost_sampling.py](scripts/patch_xgboost_sampling.py)中的REPLACEMENT字符串。它按上游shuffle与_Rng_from_urng的行为，对full-range mt19937实现升序Fisher–Yates和拒绝/取模映射；没有复制完整STL头文件。
- 本页按算法参考/适配来源保留许可与归属，不把对应上游部分改称作者原创。LLVM例外仅针对符合其条件的上游材料；不能据此把本项目所有代码都标为附带该例外。

## Python依赖和字体

requirements清单用于从软件源安装依赖；清单本身不是依赖库的重新授权。当前包不分发Python依赖源码、wheel、编译器、TeX发行版或独立字体文件。以后若把这些内容打包，须按实际版本另核对其随附许可，不能只采用项目代码许可证。

论文PDF中识别到Fandol、Latin Modern以及Computer Modern/AMS字体族的嵌入子集。字体程序保留各自上游条件，中英文论文采用的CC BY 4.0只覆盖作者有权许可的论文内容，不替字体重新授权。Fandol来源说明为GPL加字体例外；Latin Modern采用GUST Font License；CTAN的AMSFonts包说明为SIL Open Font License。这里是字体族和包级来源记录，不是对每个嵌入子集的逐文件版本还原。[Fandol来源](https://ctan.org/texarchive/fonts/fandol?lang=en)、[Latin Modern来源](https://www.ctan.org/tex-archive/fonts/lm)、[AMSFonts来源](https://ctan.org/pkg/amsfonts)。

## 文献、图件与数据

参考文献保留原作者及出版信息，未附第三方论文全文。引用他人的理论或研究结论不表示本项目取得其文本、图件或数据的再许可权。项目生成的研究图应与原始输入数据的授权分开理解；作者只能许可自己有权许可的图表表达和汇编部分。

行情和EPU原始工作簿、逐期价格/预测面板及模型缓存不在分发范围。其上游版本与再分发条件仍未完全核实，不能因为原创图表采用CC BY 4.0就推断底层数据可以重新分发。[数据范围](data/README.md)与[逐项清单](docs/upload-manifest.md)共同限定本次交付。
