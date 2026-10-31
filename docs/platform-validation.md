# 平台安装与运行验证

日期：2026-10-31。仅验证无需私人数据的合成示例，不代表完整论文实验的跨平台复现。运行命令见[示例说明](../examples/README.md)。

## 实际测试与静态检查

| 平台/检查 | 执行方式 | 当前结论 |
| --- | --- | --- |
| macOS ARM64，Python 3.12.14 | 前轮两个新venv从PyPI安装26个wheel并完整运行 | 实测通过；沿用系统已有libomp，不是空白操作系统测试 |
| Ubuntu 24.04.5 LTS ARM64，Python 3.12.3 | 本轮新UTM虚拟机，安装python3.12-venv及libgomp1；新venv从PyPI安装27个wheel | 安装、pip check、原生库加载、完整示例、独立输出核验通过 |
| Windows 11 ARM64，x64 Python 3.12.10 | 本轮新UTM虚拟机；新venv从PyPI安装26个wheel，Python构建平台为win-amd64 | 安装、pip check、原生库加载、完整示例、独立输出核验通过；属于ARM64系统上的x64兼容层实测 |
| Windows x86_64 / Python 3.12.14目标 | 在macOS上运行uv二进制依赖解析，目标x86_64-pc-windows-msvc | 26包版本约束可解析；不是Windows安装或运行测试 |
| Windows ARM64原生Python 3.12.10目标 | 在macOS上以aarch64-pc-windows-msvc和only-binary约束解析 | 失败：statsmodels 0.15.0没有可用wheel；README改为x64 Python路径，未尝试原生源码构建 |
| Linux x86_64 / Python 3.12.14目标 | 在macOS上运行uv二进制依赖解析，目标x86_64-manylinux_2_28 | 27包版本约束可解析；不是Linux x86_64运行测试 |
| CP437控制台编码 | 在macOS上设置PYTHONIOENCODING=cp437后完整运行 | 修复启动横线导致的UnicodeEncodeError；这是编码模拟，不是Windows实测 |
| Git换行转换 | macOS本地临时Git索引与checkout-index，core.autocrlf=true | 用于验证字节保留；不是Windows文件系统或Git for Windows实测 |

两个虚拟机仅接收公开材料，均不挂载原始研究目录，关闭剪贴板共享。软件从官方来源下载；没有上传研究数据或连接GitHub仓库。虚拟机、系统镜像、日志及测试输出均为本地运行材料，不在公开清单内。Windows ISO SHA256与微软页面公布值一致，已启用UTM的TPM/UEFI设置。

## Linux实测证据

Ubuntu内核为6.8.0-147-generic、aarch64。虚拟机由官方Ubuntu 24.04云镜像创建，镜像SHA256匹配官方清单；UTM 5.0.8，3核、3 GiB内存。依赖在新建venv中安装，未启用系统site-packages或用户site-packages。包下载使用PyPI、只接受wheel并关闭pip缓存；27项依赖不包含pip本身。Linux额外安装`nvidia-nccl-cu13==2.32.3`，来自普通XGBoost的Linux传递依赖；不表示使用了GPU。

实际运行得到640条合成价格、617条准备后样本，按200/200/217切分；3模型、6个MIDAS候选规格、10次选中拟合均通过。独立复算12个指标的最大绝对误差为4.44×10⁻¹⁶。

与本轮macOS默认种子运行比较，XGBoost预测逐值相同；AR最大差异2.13×10⁻¹⁴，DEC最大差异9.19×10⁻⁹。指标最大差异4.30×10⁻⁹以内。合成目标本身因跨平台浮点计算也存在约7.64×10⁻¹⁴差异，因此不承诺跨平台文件或数值逐位相同。运行记录中的系统信息用于识别证据范围，不能据此推断未测硬件。

本地安装报告、运行输出与复算记录保存在`generated/platform-review/`；它们不分发。原始论文实验数据未参与本轮测试。

## Windows实测证据

实际系统查询为Windows 11 Home Single Language、26H2、构建26300.9457，操作系统为ARM64。UTM 5.0.8虚拟机使用4核、6 GiB内存、64 GiB磁盘。使用官方Python 3.12.10 x64安装程序，Windows数字签名验证为有效，发布者为Python Software Foundation，传入客户机前后的SHA256一致。系统中已有x64及ARM64 Visual C++运行库14.42.34438.00。

Python报告`platform.machine()=ARM64`、`sysconfig.get_platform()=win-amd64`、64位指针；这里的Python和wheel实际为x64。新venv关闭系统与用户site-packages，pip 25.0.1按README依赖清单从PyPI无缓存安装26个wheel，没有源码构建，也未安装arch、openpyxl或seaborn。核心版本为NumPy 2.5.4、pandas 3.1.0、SciPy 1.18.1、statsmodels 0.15.0、XGBoost 3.4.1、scikit-learn 1.9.1及Matplotlib 3.11.2。

环境创建及依赖安装在本地测试账户的PowerShell 5.1会话执行；完整示例和核验命令随后通过UTM客户机代理在SYSTEM账户的PowerShell中执行。均使用venv解释器直接调用，没有运行Activate.ps1或改变执行策略。已验证这些命令的实际执行，但没有完成普通权限账户下的完整交互流程测试。

pip check、五个核心库的独立导入、默认完整示例、公开样本口径与170项分发文件哈希核验均通过。独立检查器在Windows内及取回输出后分别运行：217条预测、3模型、6候选规格和10次驻点验收通过；12个指标复算最大绝对误差8.88×10⁻¹⁶。

| Windows输出对照 | macOS ARM64 | Linux ARM64 |
| --- | --- | --- |
| XGBoost预测最大绝对差 | 0 | 0 |
| 残差AR预测最大绝对差 | 7.11×10⁻¹⁵ | 2.14×10⁻¹⁴以内 |
| DEC预测最大绝对差 | 8.71×10⁻⁹以内 | 9.49×10⁻⁹以内 |
| 12项测试指标最大绝对差 | 2.64×10⁻⁹以内 | 6.93×10⁻⁹以内 |

三平台均选中K=12、指数Almon规格，选择样本119/80一致。权重参数并非逐位相同：Windows与另两平台的theta2最大差异约2.89×10⁻⁷，选择集MSE差异约3.61×10⁻⁸以内。它们仍通过各自的驻点检查；不能将“选中同一规格”写成“全部拟合参数完全相同”。这些比较只属于固定种子的合成示例，不是历史DEC差异的解释或论文有效性的新增证据。

## 兼容性修复与限制

- 示例启动日志改用ASCII横线，避免窄控制台编码中断运行；计算方法和训练参数未改变。
- 新增[独立检查器](../scripts/check_demo_output.py)，核对平台记录、日期、样本数量、六个候选、驻点验收与独立评分。把macOS输出伪当Windows输出、或把MSE改动1的两个负例均实际被拒绝。
- 新增[.gitattributes](../.gitattributes)禁用自动文本换行转换，保留已有归档字节。修复前模拟检出改变168个文件中的108个，足以使SHA256失败；修复后171个文件全部保持字节不变。模拟仅使用临时本地Git索引，没有提交或远程地址。
- Windows使用环境解释器直接执行，不依赖Activate.ps1或改变PowerShell执行策略。Python标准库校验工具也应使用同一解释器运行。
- Windows命令明确使用x64 Python；固定的statsmodels 0.15.0在原生Windows ARM64目标的二进制解析失败，未尝试源码构建。本次兼容层测试成功，仍不能记为原生ARM64 Python或原生x86_64硬件测试。
- 示例运行元数据新增`sysconfig.get_platform()`和指针位数。`platform.machine()`可能报告系统架构，不能单独据此判断Python进程的wheel架构。新增字段后的macOS对照运行与独立核验通过，三份数值CSV与修改前逐字节相同。
- 本轮不测试真实数据训练、定制XGBoost 2.0.3构建、论文编译、所有Linux发行版或所有Windows架构。静态依赖可解析不保证原生库加载、操作系统兼容或算法运行成功。

官方依据：[Python venv](https://docs.python.org/3.12/library/venv.html)、[XGBoost安装与运行库](https://xgboost.readthedocs.io/en/stable/install.html)、[Git换行属性](https://git-scm.com/docs/gitattributes)、[Ubuntu云镜像](https://cloud-images.ubuntu.com/noble/current/)、[Windows ARM64镜像](https://www.microsoft.com/en-us/software-download/windows11arm64)。
