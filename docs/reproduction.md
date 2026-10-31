# 运行与复现

日期：2026-10-31。先选择用途：初次体验运行合成示例；重算当前论文使用稳定DEC入口；历史复现仅用于追溯旧结果。

| 用途 | 入口 | 所需数据/环境 | 输出 |
| --- | --- | --- | --- |
| 无数据快速体验 | [synthetic_demo.py](../examples/synthetic_demo.py) | 无私人输入；普通依赖 | `generated/synthetic-demo/` |
| 当前论文点预测 | [run_dec_revision.py](../scripts/run_dec_revision.py) | 五工作簿、兼容XGBoost构建、完整依赖 | `generated/dec-revision/` |
| 当前论文区间 | [run_revised_intervals.py](../scripts/run_revised_intervals.py) | 上一步CSI300预测面板 | `generated/dec-revision-intervals/` |
| 当前DEC数值检查 | [check_dec_solver.py](../scripts/check_dec_solver.py) | 当前修订实验输出 | `generated/dec-solver-check/` |
| 历史候选训练 | [run_experiments.py](../scripts/run_experiments.py) | 五工作簿、普通环境；旧DEC | `generated/runs/`，不对应当前正文 |
| 历史XGBoost匹配 | [reproduce_historical_xgb.py](../scripts/reproduce_historical_xgb.py) | 本地历史档案与兼容构建 | 只用于历史追溯 |

## 无私人数据的最小示例

以下为macOS/Linux命令，从项目根目录执行；Windows完整PowerShell命令及输出解释见[示例说明](../examples/README.md)。实际运行与静态检查的范围见[平台验证](platform-validation.md)。

先按[前置环境](../examples/README.md#前置环境)准备Python 3.12与平台运行库；macOS的`libomp`不属于pip依赖，不能遗漏。当前已完成全新venv安装演练，范围见[演练记录](release-rehearsal.md#全新隔离环境安装验证)。

```bash
python3.12 --version
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
.venv/bin/python -m pip check
.venv/bin/python -c "import xgboost; print('XGBoost load OK')"
.venv/bin/python examples/synthetic_demo.py
.venv/bin/python scripts/check_demo_output.py
```

示例使用人工数据与较小树模型，复用正式稳定DEC实现，不重现论文分数。输出明确标记synthetic_demo。无需安装实验依赖也可做静态校验：

```bash
python3 scripts/verify_package.py
python3 scripts/check_release_contract.py
```

第二条核对配置与公开汇总的样本口径，不读取私人数据或重新训练模型。

最小示例的全新安装验证覆盖示例依赖；平台专属依赖使包数量不同，详见[平台验证](platform-validation.md)。下节完整研究环境及兼容构建沿用此前研究运行记录，本轮未在新环境重新安装和训练全部研究流程。

## 环境与输入

本次使用Python 3.12.14。[锁定清单](../requirements-reproduction.txt)记录本次成功运行的依赖，包含必需的scikit-learn；它不是历史环境记录。新环境可按以下步骤准备，已有本地`.venv`可直接使用：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-reproduction.txt
```

按[data说明](../data/README.md)准备5个原始输入，默认放入`data/`。这些输入不随公开包分发。只核验分发文件不需要实验依赖：

```bash
python3 scripts/verify_package.py
```

## 当前修订实验

按前节准备完整依赖和五个输入工作簿，并按下文“全部XGBoost预测匹配的诊断构建”准备兼容构建。新用户将工作簿放入data/，运行：

```bash
.venv/bin/python scripts/run_dec_revision.py --data-dir data --xgboost-python-path generated/xgb203 --output generated/dec-revision
.venv/bin/python scripts/run_revised_intervals.py --input generated/dec-revision/csi300/all_model_predictions.csv --output generated/dec-revision-intervals
.venv/bin/python scripts/check_dec_solver.py --input generated/dec-revision --output generated/dec-solver-check
python3 scripts/check_release_contract.py --predictions generated/dec-revision
```

新入口默认从原始输入训练XGBoost；包含上证50历史/修正输入控制、稳定DEC、XGB-AR及HAR/GARCH重估。输出目录必须为空且位于generated/。`configs/dec-revision.json`记录本轮求解规则，稳定实现为`scripts/dec_stable.py`。规格选择失败或未通过驻点验收即停止，不能略去失败候选后宣称完整比较。

已有本地档案时，可用`--archive /path/to/local-research-archive`代替`--data-dir`。本次运行用`--reuse-local-first-stage`复用先前已验证的本地XGBoost缓存，校验日期、标签和目标，保存SHA256；这个选项依赖本地training-forensics目录，不适合新下载项目直接启用。主体第二阶段、HAR及GARCH确实重新估计。

`check_dec_solver.py`的跨依赖检查可添加`--dependency-path generated/<isolated-dependency-folder>`，只使用用户已经准备的依赖目录，不自动安装。两套实际版本见当前结果目录的runtime记录；新方法不承诺逐位跨平台相同或全局最优。

当前样本口径统一见[data说明](../data/README.md)和[sample-splits.json](../configs/sample-splits.json)：CSI300/上证50测试各1919条，纳斯达克1554条，CSI300区间共同1859条。当前论文结果位于results/revised/，原目录仅作历史档案；脚本输出不会自动覆盖分发结果或论文。运行后应重新核验、更新相关表述与PDF，再更新完整性清单。

## 历史候选训练（不生成当前修订正文）

```bash
MPLCONFIGDIR=generated/matplotlib .venv/bin/python scripts/run_experiments.py --data-dir data --market all
```

可将`all`改为`csi300`、`sse50`或`nasdaq`。参数及文件对应见[配置](../configs/experiments.json)。输出写入`generated/runs/<market>/`，包括逐期预测、汇总、图件、运行警告及依赖版本；重复运行会覆盖这个生成目录的同名文件，不覆盖`results/`。

若本地保留原档案，可添加`--reference-archive /path/to/local-research-archive`，逐点比较预测日期、缺失位置和数值。比较容差为绝对1e-6；不应以四舍五入的指标接近替代逐点核对。现有存档树模型结果未被本次新结果替换。

原CSI300入口仍可使用：`scripts/csi300_epu_final_from_oldcode.py`读取`data/`并写入`generated/csi300_epu_final_outputs/`。随后运行`scripts/conformal_interval_experiment.py`，默认读取这一CSI300目录。统一入口的CSI300输出位于`generated/runs/csi300/`，两者路径不同，不要混用。

## 来源追查与组件核验

```bash
MPLCONFIGDIR=generated/matplotlib .venv/bin/python scripts/trace_provenance.py --archive /path/to/local-research-archive
MPLCONFIGDIR=generated/matplotlib .venv/bin/python scripts/check_training_components.py --archive /path/to/local-research-archive
.venv/bin/python scripts/audit_results.py --archive /path/to/local-research-archive
```

- `trace_provenance.py`检查额外零值的全部插入位置、24个统计数值指纹、三市场输入矩阵及标签，并生成正确的3941条描述统计与图。插入零值只用于追查，不是正式观测。
- `check_training_components.py`检查当前安装版本下的有限XGBoost配置探针，再固定存档XGBoost预测复算第二阶段。该隔离检查不是完整训练复现。原附录早停切分未完整保存，探针的15%内部留出属于诊断假设。
- `audit_results.py`不训练模型，检查349个历史汇总值并重建24组区间。与旧描述统计比较的5项差异会继续显示；它们已有来源解释，旧报告未被改成虚假的全通过。

本地档案应包含`data source/`、`outputs/{csi300,SSE50,NASDAQZH}_epu_final_outputs/`、`res/csi300_epu_interval_outputs/`，以及`论文主体/GD2025TempLatex20250922/images/`中的完整精度检验表。各工具默认只向本项目`generated/`写入；原输入只读。

来源核验报告在`results/verification/`，正确描述统计在`results/descriptive-corrected/`。所有已经完成的检查及其实际范围见[验证记录](validation.md)。

## 全部XGBoost预测匹配的诊断构建

这不是上游官方发行版或恢复出的原安装包。已在本机macOS ARM64编译XGBoost 2.0.3，并仅增加可切换的MSVC列洗牌兼容逻辑。官方macOS轮子即使同为2.0.3，也不会自动得到这一行为。Python数据和研究文件始终在本地使用。

需要已安装CMake、C++编译器和OpenMP。主依赖按上节准备；将[PyPI的XGBoost 2.0.3源码包](https://pypi.org/project/xgboost/2.0.3/#files)解压到`generated/xgboost-2.0.3/`。以下为macOS步骤；不在系统目录安装或替换库：

```bash
.venv/bin/python -m pip install --no-deps --target generated/xgb203 xgboost==2.0.3
python3 scripts/patch_xgboost_sampling.py --source-dir generated/xgboost-2.0.3/cpp_src
cmake -S generated/xgboost-2.0.3/cpp_src -B generated/xgb-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DUSE_CUDA=OFF -DUSE_OPENMP=ON -DKEEP_BUILD_ARTIFACTS_IN_BINARY_DIR=ON
cmake --build generated/xgb-build --parallel 4
cp generated/xgb-build/lib/libxgboost.dylib generated/xgb203/xgboost/lib/libxgboost.dylib
OMP_NUM_THREADS=4 .venv/bin/python scripts/reproduce_historical_xgb.py --archive /path/to/local-research-archive --xgboost-python-path generated/xgb203 --save-models
```

补丁核对原源码SHA256，并拒绝修改generated之外的文件。若CMake没有自动找到OpenMP，应按本机已有库路径设置OpenMP相关CMake变量；本次构建使用已有Homebrew libomp。这里没有打包编译器、第三方源码或二进制。

兼容补丁的XGBoost和Microsoft STL来源及原许可证见[第三方说明](../THIRD_PARTY_NOTICES.md)。项目许可证不替代上游条件；以后如另行分发修改后的源码或库，须保留适用的许可证、修改声明和NOTICE。

入口默认启用兼容抽样。`--sampling native --output generated/native-control`可作同构建原生抽样对照。每次输出应选新的空目录；脚本拒绝覆盖既有运行记录。输出含完整预测、逐点比较、所有重估点的有效Booster配置、训练输入指纹、优化诊断和运行环境；`--save-models`额外保留每次重估的UBJ模型。模型和日志仅留在generated，不分发。

本次已保留的可重用本地诊断包在`generated/training-forensics/xgb203built/`；经验证的公开入口输出在`generated/training-forensics/public-run-verified/`。它们是本地运行材料，不属于上传候选清单。实际依赖及库指纹见[匹配构建记录](../results/verification/matched_runtime.json)，数值匹配不证明原机就是该版本。

## 历史第二阶段诊断与交易日历修正

MIDAS使用单起点L-BFGS-B和剖面OLS。代码显式固定原默认停止参数，并保存`midas_optimizer_diagnostics.json`；相对目标变化满足停止条件不等于梯度收敛，不能忽略运行警告或把该估计当作全局最优。本次加诊断后，预测与未加诊断的兼容试跑完全相同。

```bash
MPLCONFIGDIR=generated/matplotlib .venv/bin/python scripts/check_method_timing.py --archive /path/to/local-research-archive
```

该脚本检查原始目标日期与过滤后残差滞后，确认上证50的2018-06-18休市记录造成目标污染；另生成排除该已确认休市行、从头构造的`generated/method-timing/sse50_calendar_corrected_prepared.csv`。这是新的输入版本；历史追查阶段另用本页“上证50日历清洗对照”的脚本实际重训四模型，当前正文则采用上方五模型修订入口；结果独立保存，不能直接替换历史指标。零成交量本身不足以判断其他日期休市；此检查也不声称完成了所有交易所的完整日历审计。

## 编译论文

中英文源码与编译要求见[论文说明](../paper/README.md)。已安装含ctex、Fandol、Latin Modern字体和常见数学/表格宏包的TeX Live后，中文在`paper/source/`、英文在`paper/english-source/`分别运行：

```bash
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
bibtex main
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
```

各自生成`main.pdf`；经检查的公开成品分别为`paper/thesis-public.pdf`和`paper/thesis-en.pdf`。请不要直接覆盖已审阅成品；编译成功后仍需核对引用、图表和版式。源码通过相对路径引用图件与文献。`.venv/`、`generated/`、`data/`中的原始数据和LaTeX临时产物均不属于上传范围，逐项范围由[清单](upload-manifest.md)确定。

## 上证50日历清洗对照

使用与前述复现相同的本地诊断包运行：

```bash
OMP_NUM_THREADS=4 .venv/bin/python scripts/check_calendar_sensitivity.py --archive /path/to/local-research-archive --xgboost-python-path generated/xgb203
```

原输入与排除2018-06-18后的输入分别训练四模型；输出中的all_dates_metrics使用各自1915/1919条，common_dates_metrics统一1915个日期并对两组预测使用同一修正目标。该控制试验仅处理这一已确认休市行，不等同于完整数据清洗或历史模型原封不动复现。
