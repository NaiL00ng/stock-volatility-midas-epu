# Stock Volatility Forecasting with MIDAS EPU Correction

**作者 / Author: Boursin Nickel**

[中文](#中文) | [English](#english)

研究版本 / Research version: **0.5-review** · [GitHub Pre-release](https://github.com/NaiL00ng/stock-volatility-midas-epu/releases/tag/v0.5-review)

## 中文

研究下一交易日平方收益率对数代理的预测，比较HAR、GARCH、XGB-Market、残差单独修正XGB-AR，以及加入月度EPU的DEC。

当前研究档案报告包含**稳定求解、日历修正与消融重分析**：DEC相对两个XGB对照在三个市场都降低QLIKE，但都提高MSE。它没有改善CSI300的区间质量。材料适合带限制阅读，不是已验证的实时预测系统；EPU真实发布版本与全新留出评估仍缺失。修订结论及“变好还是变差”的完整对照见[DEC方法修订](docs/dec-method-review.md)。

### 首次运行：不需要私人数据

先准备64位Python 3.12及平台原生运行库，见[前置环境](examples/README.md#前置环境)。先获取[公开仓库](https://github.com/NaiL00ng/stock-volatility-midas-epu)，以下macOS/Linux命令在项目根目录执行；Windows完整命令见[PowerShell步骤](examples/README.md#windows-powershell)。实际测试与静态检查分开记录在[平台验证](docs/platform-validation.md)。

```bash
git clone https://github.com/NaiL00ng/stock-volatility-midas-epu.git
cd stock-volatility-midas-epu
python3.12 --version
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
.venv/bin/python -m pip check
.venv/bin/python -c "import xgboost; print('XGBoost load OK')"
.venv/bin/python examples/synthetic_demo.py
.venv/bin/python scripts/check_demo_output.py
```

示例只生成虚构数据，复用当前DEC代码，输出写入`generated/synthetic-demo/`；不代表论文结果。最后一条命令独立复算评分并检查样本、日期和优化诊断。重复运行需指定新的空输出目录，并将该目录传给检查器的`--input`。完整输出解释及演练范围见[示例说明](examples/README.md)和[发布前演练](docs/release-rehearsal.md)。

当前真实数据实验使用`run_dec_revision.py`及`run_revised_intervals.py`，需要自备有权使用的输入及兼容构建。`run_experiments.py`保留作历史入口。三市场测试数量依次为1919、1919、1554；CSI300区间统一1859条，见[样本口径](configs/sample-splits.json)。

### 从何处开始

中英文论文均已提供，配套技术说明目前以中文为主。

- [相关文献差异](docs/related-work.md)：哪些设计已有先例、本项目可支持的贡献及尚缺的直接比较。
- [中文修订论文](paper/thesis-public.pdf)与[英文研究稿](paper/thesis-en.pdf)：同一组实验与限制，作者化名，无身份页与致谢；[源码、编译与论文引用](paper/README.md)。
- [当前结果](results/revised/README.md)：五模型、三市场、共同日期区间与数值验证。
- [运行说明](docs/reproduction.md)：安装、本地兼容构建、数据结构及修订实验入口。
- [版本对应表](docs/version-map.md)：明确历史与当前论文分别对应什么。
- [历史追溯](docs/provenance-resolution.md)：6888条XGBoost预测已逐点重现，旧DEC精确轨迹尚未恢复。
- [研究限制](docs/research-review.md)、[数据说明](data/README.md)、[上传清单](docs/upload-manifest.md)。
- [版本说明](docs/release-notes.md)：当前验证范围、仓库信息与发布状态；[许可范围](docs/licensing.md)及[第三方来源](THIRD_PARTY_NOTICES.md)。

若GitHub内嵌PDF预览无法加载，可直接下载[中文PDF](https://raw.githubusercontent.com/NaiL00ng/stock-volatility-midas-epu/main/paper/thesis-public.pdf)或[English PDF](https://raw.githubusercontent.com/NaiL00ng/stock-volatility-midas-epu/main/paper/thesis-en.pdf)，也可从克隆后的paper目录打开。

### 当前CSI300结果

测试1919条。MSE与MAE在对数目标尺度上计算。下表为修订实验；历史CSV与图件保留在原结果目录，不静默覆盖。

| 模型 | 对数MSE | 对数MAE | QLIKE |
| --- | ---: | ---: | ---: |
| GARCH | 7.375868 | 1.983865 | 1.564183 |
| XGB_MIDAS_EPU_DEC | 5.112644 | 1.725558 | 3.536964 |
| HAR | 4.905206 | 1.724860 | 3.905553 |
| XGB_Residual_AR | 5.094169 | 1.758021 | 4.705936 |
| XGB_Market | 5.099716 | 1.763086 | 4.951636 |

![CSI300修订QLIKE比较](results/revised/csi300/fig_metrics_bar.png)

纳斯达克的验证最优规格由12个月Beta改为12个月指数Almon；相对旧DEC，MSE改善约0.99%，QLIKE变差约2.65%。更可靠的求解不保证每个测试指标改善。上证50正文结果已在特征构造前排除确认的休市行。

90%区间、校准窗口250、共同1859个日期上，DEC得分10.1995，高于HAR 9.6973、XGB-Market 9.8534及XGB-AR 9.8793。区间针对未来观测代理，不是潜在条件方差；统计诊断仍受回顾性分析、序列依赖和规格选择限制。

无需安装依赖即可核验分发文件：

```bash
python3 scripts/verify_package.py
python3 scripts/check_release_contract.py
```

### 文件结构与使用条件

`examples/`为合成示例，`paper/`为论文，`scripts/`为运行和检查入口，`results/revised/`为当前结果，`results/`其他目录保留历史证据，`docs/`为说明，`data/`仅提供输入规范。

运行输出写入`generated/`。本地`.venv/`、`generated/`、原始数据、模型和逐期预测不属于分发范围。分发范围以清单为准，不应将本地运行目录或父目录推送到仓库。

Copyright © 2026 Boursin Nickel。作者有权许可的**代码、可执行示例与运行配置采用[Apache-2.0](LICENSE)**；**中英文论文、说明文字和原创图表采用[CC BY 4.0](LICENSE-CONTENT.txt)**。这是按材料划分的授权，不是在两种许可证之间任选。具体范围、数值汇编和代码片段的处理见[许可说明](docs/licensing.md)及[NOTICE](NOTICE)。第三方材料保留[各自原有条款](THIRD_PARTY_NOTICES.md)，许可不覆盖底层行情与EPU数据。

软件引用见[CITATION.cff](CITATION.cff)，中英文论文引用见[论文说明](paper/README.md)。当前版本为0.5-review，[项目仓库](https://github.com/NaiL00ng/stock-volatility-midas-epu)按探索性研究档案提供；上传后的克隆与运行验收见[验证记录](docs/validation.md)。这不是期刊发表或实时预测能力认证。

## English

This project forecasts a log-transformed squared-return proxy for the next trading day. It compares HAR, GARCH, XGB-Market, the residual-only correction XGB-AR, and DEC incorporating monthly economic policy uncertainty (EPU).

The current research archive presents **stable estimation, trading-calendar corrections, and an ablation reanalysis**. Relative to both XGBoost controls, DEC lowers QLIKE but raises MSE in all three markets. It does not improve interval quality for the CSI300. Read the findings together with their limitations: this is not a validated real-time forecasting system, and real-time EPU vintages and a fresh holdout evaluation remain unavailable. See the [DEC method review](docs/dec-method-review.md) for the revised conclusions and the complete comparison of improvements and deterioration.

### First run: no private data required

Prepare 64-bit Python 3.12 and the native runtime libraries required by your platform; see the [prerequisites](examples/README.md#前置环境). Obtain the [public repository](https://github.com/NaiL00ng/stock-volatility-midas-epu) and run the following macOS/Linux commands from the project root after cloning. For Windows, follow the [PowerShell instructions](examples/README.md#windows-powershell). Actual execution tests and static checks are distinguished in the [platform validation record](docs/platform-validation.md).

```bash
git clone https://github.com/NaiL00ng/stock-volatility-midas-epu.git
cd stock-volatility-midas-epu
python3.12 --version
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
.venv/bin/python -m pip check
.venv/bin/python -c "import xgboost; print('XGBoost load OK')"
.venv/bin/python examples/synthetic_demo.py
.venv/bin/python scripts/check_demo_output.py
```

The demo generates fictitious data, reuses the current DEC implementation, and writes its outputs to `generated/synthetic-demo/`. These outputs are not the paper's empirical results. The final command independently recomputes the scores and checks sample counts, dates, and optimization diagnostics. For another run, select a new empty output directory and pass that directory to the checker's `--input` option. See the [demo guide](examples/README.md) and [release rehearsal](docs/release-rehearsal.md) for output descriptions and the scope of the tests.

The current experiments with real data use `run_dec_revision.py` and `run_revised_intervals.py`. They require inputs you are authorized to use and the documented compatible build. `run_experiments.py` is retained as a historical entry point. Test sample sizes are 1919, 1919, and 1554 for CSI300, SSE50, and Nasdaq, respectively; CSI300 interval comparisons use 1859 common dates. See the [sample definitions](configs/sample-splits.json).

### Where to start

Both Chinese and English papers are available. Most supporting technical documentation is currently in Chinese.

- [Related work](docs/related-work.md): established methods, contributions supported by this project, and direct comparisons that remain to be performed.
- [Revised Chinese paper](paper/thesis-public.pdf) and [English research paper](paper/thesis-en.pdf): the same experiments and limitations, published under a pseudonym without identity pages or acknowledgments; see [sources, compilation, and paper citations](paper/README.md).
- [Current results](results/revised/README.md): five models, three markets, intervals evaluated on common dates, and numerical checks.
- [Reproduction guide](docs/reproduction.md): installation, the compatible local build, input structure, and entry points for the revised experiments.
- [Version map](docs/version-map.md): correspondence between the current paper, historical versions, code, and results.
- [Historical provenance](docs/provenance-resolution.md): all 6888 historical XGBoost predictions were reproduced point by point; the exact historical DEC trajectory remains unrecovered.
- [Research limitations](docs/research-review.md), [data specification](data/README.md), and [distribution manifest](docs/upload-manifest.md).
- [Version notes](docs/release-notes.md): validation scope, repository information, and publication status; see also the [license scope](docs/licensing.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

If GitHub's embedded PDF preview does not load, download the [Chinese PDF](https://raw.githubusercontent.com/NaiL00ng/stock-volatility-midas-epu/main/paper/thesis-public.pdf) or [English PDF](https://raw.githubusercontent.com/NaiL00ng/stock-volatility-midas-epu/main/paper/thesis-en.pdf) directly, or open the files in the cloned `paper/` directory.

### Current CSI300 results

The test sample contains 1919 observations. MSE and MAE are evaluated on the log target. The table reports the revised experiments; historical CSV files and figures remain in their original result directories without being overwritten.

| Model | MSE (log target) | MAE (log target) | QLIKE |
| --- | ---: | ---: | ---: |
| GARCH | 7.375868 | 1.983865 | 1.564183 |
| XGB_MIDAS_EPU_DEC | 5.112644 | 1.725558 | 3.536964 |
| HAR | 4.905206 | 1.724860 | 3.905553 |
| XGB_Residual_AR | 5.094169 | 1.758021 | 4.705936 |
| XGB_Market | 5.099716 | 1.763086 | 4.951636 |

![Revised CSI300 QLIKE comparison](results/revised/csi300/fig_metrics_bar.png)

For Nasdaq, the specification selected on the validation set changed from 12-month Beta weights to 12-month exponential Almon weights. Relative to the historical DEC result, MSE improves by approximately 0.99%, while QLIKE worsens by approximately 2.65%. A more reliable solver does not guarantee improvement in every test metric. The SSE50 results in the current paper exclude the confirmed non-trading-day row before feature construction.

For 90% intervals with a calibration window of 250 observations and 1859 common dates, DEC has an interval score of 10.1995, compared with 9.6973 for HAR, 9.8534 for XGB-Market, and 9.8793 for XGB-AR. These intervals concern the future observed proxy, not latent conditional variance. Statistical diagnostics remain subject to retrospective analysis, serial dependence, and specification-selection limitations.

The distributed files can be checked without installing third-party dependencies:

```bash
python3 scripts/verify_package.py
python3 scripts/check_release_contract.py
```

### File structure and terms of use

`examples/` contains the synthetic demo, `paper/` the papers, and `scripts/` the execution and verification entry points. `results/revised/` holds the current results; other directories under `results/` retain historical evidence. `docs/` contains the documentation, and `data/` contains input specifications only.

Runtime outputs belong in `generated/`. Local `.venv/` and `generated/` directories, raw data, model files, and per-period predictions are outside the distribution scope. The manifest defines the public file set; do not push local runtime directories or the parent research directory to the repository.

Copyright © 2026 Boursin Nickel. To the extent the author has the right to license them, **code, executable examples, and runtime configurations use [Apache-2.0](LICENSE)**, while **the Chinese and English papers, documentation text, and original figures use [CC BY 4.0](LICENSE-CONTENT.txt)**. The licenses apply to different materials; they are not interchangeable options for the same material. See the [license scope](docs/licensing.md) and [NOTICE](NOTICE) for numerical compilations, code snippets, and other details. Third-party materials retain [their original terms](THIRD_PARTY_NOTICES.md); the project licenses do not cover the underlying market or EPU data.

For software citations, use [CITATION.cff](CITATION.cff); for the papers, see the [paper guide](paper/README.md). The current research version is 0.5-review. The [repository](https://github.com/NaiL00ng/stock-volatility-midas-epu) is provided as an exploratory research archive; post-upload cloning and execution checks are recorded in the [validation notes](docs/validation.md). Publication on GitHub does not imply journal publication or certification of real-time forecasting performance.
