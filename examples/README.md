# 无私人数据的最小运行示例

此示例在内存中生成虚构行情和月度指标，复用当前特征构造、扩展窗口XGBoost、稳定DEC求解及残差AR对照。**无需Excel工作簿、原档案、历史预测缓存或定制XGBoost构建；运行脚本不访问网络。**

## 前置环境

Python 3.12必须先可用；虚拟环境不会自行安装Python。本机的`python3.12`起初不在PATH中，因此演练用已安装的3.12解释器完整路径创建环境。若`python3.12 --version`提示命令不存在，先准备Python 3.12，或将下面命令中的`python3.12`替换为其实际完整路径。不要直接假定系统`python3`就是3.12。[Python虚拟环境说明](https://docs.python.org/3.12/library/venv.html)说明了它与基础解释器的关系。

macOS需要OpenMP运行库。前轮从PyPI新装的XGBoost 3.4.1实际加载了系统已有的Homebrew `libomp`；它不会由`requirements-demo.txt`中的Python包自动安装。已有Homebrew时可按[官方libomp安装说明](https://formulae.brew.sh/formula/libomp)执行`brew install libomp`，然后进行下面的加载检查。此命令管理系统侧依赖；前轮macOS依赖验证没有执行它，本轮Homebrew仅用于另行授权的虚拟化工具安装。只设`n_jobs=1`不能消除已编译库的加载依赖。

Linux需支持对应wheel的glibc与OpenMP运行库。Ubuntu 24.04可用`sudo apt update`后执行`sudo apt install python3.12-venv libgomp1`准备；其他发行版须使用对应包管理器，不直接照搬apt命令。本次Ubuntu 24.04.5 ARM64虚拟机实际使用Python 3.12.3。Windows需64位Python 3.12，并按[XGBoost官方安装说明](https://xgboost.readthedocs.io/en/stable/install.html)准备匹配架构的Visual C++运行库。Python进程架构和操作系统架构可能不同，不能仅凭操作系统名称选择wheel。

已实际完成macOS ARM64、Linux ARM64及Windows 11 ARM64搭配x64 Python的全新依赖安装与示例。具体版本、执行账户与静态检查范围见[平台验证](../docs/platform-validation.md)。合成示例使用CPU，不要求NVIDIA显卡，也不需要定制XGBoost构建。

## 运行

在项目根目录执行。已测试Python 3.12；以下路径适用于macOS/Linux：

```bash
python3.12 --version
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
.venv/bin/python -m pip check
.venv/bin/python -c "import xgboost; print('XGBoost load OK')"
.venv/bin/python examples/synthetic_demo.py
.venv/bin/python scripts/check_demo_output.py
```

已有满足版本要求的专用环境可跳过创建和安装步骤，仍应执行依赖检查与原生库加载检查。首次安装依赖需要软件源网络连接；示例自身不会下载数据。

### Windows PowerShell

先安装**x64版Python 3.12**。当前固定的statsmodels 0.15.0没有可用的Windows ARM64 wheel，本项目未验证其源码构建，因此原生ARM64 Python不属于即装即用路径。ARM64版Windows 11可运行x64应用，详见[微软说明](https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation)；此时操作系统是ARM64，Python仍使用`win-amd64`依赖。实际验证范围见[平台记录](../docs/platform-validation.md)。

在项目根目录运行，无需激活环境或修改PowerShell执行策略。先检查下一条架构命令输出为`win-amd64 64`；若不是，应使用x64解释器的完整路径创建环境。若`py`不可用，将`py -3.12`替换为已安装x64 Python 3.12的调用方式；含空格的完整路径须使用PowerShell调用运算符`&`和引号。

```powershell
py -3.12 --version
py -3.12 -c "import sysconfig, struct; print(sysconfig.get_platform(), struct.calcsize('P') * 8)"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import xgboost; print('XGBoost load OK')"
.\.venv\Scripts\python.exe examples/synthetic_demo.py
.\.venv\Scripts\python.exe scripts/check_demo_output.py --expected-platform Windows
```

命令存在不等于平台已通过测试；以[平台验证表](../docs/platform-validation.md)为准。项目采用`.gitattributes`保留归档字节，避免Git的自动LF/CRLF转换破坏SHA256校验。不要手动批量转换结果CSV或论文源码的换行符。

新环境应单独创建，不复用已有研究环境。`requirements-demo.txt`用`requirements-reproduction.txt`约束传递依赖版本，但只安装示例所需的包；macOS及Windows x64 Python各实装26个wheel，Linux ARM64实装27个，均未安装`arch`、`openpyxl`或`seaborn`。Linux额外的NCCL包由普通XGBoost发行包引入，示例仍以CPU执行；该平台专属传递包未由macOS来源的约束表锁定，实际版本见平台记录。不要为减少下载量而在同一环境混装`xgboost`与`xgboost-cpu`。`pip check`检查Python依赖兼容性，不能代替原生库加载检查。若加载报错包含`libomp.dylib`、`libgomp.so.1`或VC运行库DLL，先按平台补齐运行库；只有出现`XGBoost load OK`后再运行示例。

默认输出到`generated/synthetic-demo/`。再次执行须指定新的空目录：

```bash
.venv/bin/python examples/synthetic_demo.py --output generated/synthetic-demo-repeat
.venv/bin/python scripts/check_demo_output.py --input generated/synthetic-demo-repeat
```

可用`--seed 2027`改变合成数据；默认2026只是可重复演示的固定种子，不是挑选有利结果的搜索。拒绝覆盖非空目录，拒绝输出到`generated/`以外。若中途失败，保留日志并为重试选择另一个空目录。

## 应看到什么

终端会显示`SYNTHETIC DEMO ONLY`和`PASS: 640 synthetic price rows -> 617 prepared -> 200 / 200 / 217.`，并列出三个模型的测试指标。首次运行还可能先显示Matplotlib构建字体缓存的提示。成功意味着样本完整、六个MIDAS候选规格均完成、选中解通过驻点检查；不是论文结果复现或模型有效性的证明。

| 输出 | 用途 |
| --- | --- |
| `synthetic_predictions.csv` | 217个共同测试预测，含预测起点`date`与下一合成工作日`target_date` |
| `synthetic_metrics.csv` | 三模型MSE、MAE、QLIKE及偏差；标记`data_kind=synthetic_demo` |
| `synthetic_spec_search.csv` | 六个候选规格的验证分数及选择样本数 |
| `synthetic_run.json` | 种子、样本划分、参数、系统与machine报告、Python构建平台和指针位数、依赖版本及各次优化诊断 |
| `README.md` | 明确输出只属于合成演示 |

640行虚构价格经过22日滚动特征及下一行目标构造后留下617行，按200训练、200验证、217测试顺序划分。验证段首个滞后残差缺失，因此第二阶段使用199条，分为119条拟合和80条选择。合成日历只排除周末，不代表任何交易所日历；虚构月度指标也没有真实发布日期含义。

## 与论文实验的边界

| 设置 | 此示例 | 当前论文 |
| --- | --- | --- |
| 输入 | 固定种子生成，无真实行情/EPU | 需有权使用的五个工作簿 |
| XGBoost | 普通3.4.1；40棵树、深度2、行列采样均为1、单线程 | 匹配历史列抽样的2.0.3定制构建；300棵树、深度4等，见正式配置 |
| 第二阶段 | 同一`dec_stable.py`；K=6/12/24、Beta/指数Almon；每60行重估 | 同一稳定求解规则；更长的真实样本 |
| 模型与区间 | XGB、XGB-AR、DEC三模型点预测 | 五模型点预测及CSI300区间 |
| 分数用途 | 理解和检查执行流程 | 受已披露限制约束的实证结果 |

没有预设DEC必须优于基准；不同种子或依赖可能给出不同排名，不应据此修改论文结论。固定环境、固定种子可比较重复运行；不承诺跨平台逐位相同。当前完整实验入口和样本口径见[运行说明](../docs/reproduction.md)与[数据说明](../data/README.md)。
