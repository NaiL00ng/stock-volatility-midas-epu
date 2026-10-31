# 0.5-review研究档案说明

整理日期：2026-10-31。作者：Boursin Nickel。项目仓库：[NaiL00ng/stock-volatility-midas-epu](https://github.com/NaiL00ng/stock-volatility-midas-epu)，公开可见。版本0.5-review保留研究预发布定位；实际上传后验收单独记录，不把上传等同于科研结论验证。

## 面向使用者的内容

本项目是混频波动代理预测的探索性研究与复现档案，提供中英文研究稿、对应代码、公开汇总、历史追溯证据和无需私人数据的最小示例。[版本对应](version-map.md)区分当前论文与历史结果；新用户从[合成示例](../examples/README.md)开始，论文版本与引用见[论文说明](../paper/README.md)。

当前修订采用稳定多起点DEC求解、上证50已确认休市行修正、XGB-AR消融及共同日期区间比较。三市场中，DEC相对两个XGB对照都降低QLIKE，但都提高MSE；CSI300区间质量未改善。改进数值求解并不保证所有预测指标改善。完整结论见[方法修订](dec-method-review.md)。

真实数据实验需要自备有权使用的工作簿及已说明的兼容构建；本包不提供完整私人输入，因此合成示例通过不等于从公开包独立重现全部论文结果。研究尚缺EPU真实发布与修订版本、完整上游数据审计及全新留出评估。

## 已完成的运行验证

| 实际平台 | Python | 已完成范围 |
| --- | --- | --- |
| macOS ARM64 | 3.12.14 | 新venv安装、依赖检查、最小示例；使用系统已有libomp |
| Ubuntu 24.04.5 ARM64 | 3.12.3 | 新虚拟机、新venv安装、最小示例及独立核验 |
| Windows 11 ARM64上的x64兼容层 | 3.12.10 x64 | 新虚拟机、新venv安装、最小示例及独立核验；完整示例由SYSTEM账户执行 |

原生x86_64硬件和Windows普通权限账户的完整交互流程未实测；原生Windows ARM64 Python的固定statsmodels wheel解析失败。CP437编码与Git自动换行检查属于macOS上的模拟。详细版本、账户范围和数值差异统一见[平台验证](platform-validation.md)，不把静态解析写成目标平台运行通过。此前许可及英文稿更新未重复平台安装和真实数据训练，也未声称在Windows/Linux编译过论文。

## 本次许可与双语材料收尾

作者已正式采纳代码[Apache-2.0](../LICENSE)与原创学术内容[CC BY 4.0](../LICENSE-CONTENT.txt)。[许可范围](licensing.md)、[NOTICE](../NOTICE)及[第三方说明](../THIRD_PARTY_NOTICES.md)区分代码、论文、图表、数据汇编、上游适配和字体；第三方许可证原文保留，底层数据授权不被扩大。

中文论文加入版本及许可页，新增英文研究稿及源码，二者共用同一组实验与图件。XGB-AR主区间得分统一为CSV四舍五入后的9.8793，修正原摘要等文字的9.8794笔误；结果文件、代码和训练配置不变。README、CITATION.cff、版本表、数据说明、编译说明、清单和哈希同步更新。作者署名继续使用Boursin Nickel。

只分发[逐项清单](upload-manifest.md)中的文件，并以[SHA256表](checksums.sha256)核对。原始数据、运行环境、虚拟机、模型、日志和本地备份均不随包分发。既有匿名化要求继续应用于中英文稿；目标账号和GitHub提供的noreply邮箱已核实，提交署名使用Boursin Nickel。私人登录邮箱不写入仓库或提交元数据。

## 上传前材料齐全检查

本节记录上传前阶段的实际检查。2026-10-31完成190个文件的整体预检，按**探索性研究与复现档案**准备首发；这不改变前述科研限制，也不是期刊录用或全部实验可公开独立复现的保证。

| 材料组 | 文件数 | 核对结果 |
| --- | ---: | --- |
| 根目录说明、引用、许可证与依赖清单 | 11 | README、CITATION、两份项目许可证、NOTICE及第三方说明齐全 |
| 训练与样本配置 | 3 | 当前训练入口、样本切分与公开汇总一致 |
| 数据说明 | 1 | 仅data/README.md；不含私人输入 |
| 使用与核验文档 | 15 | 版本表、方法限制、运行说明、上传清单及哈希齐全 |
| 最小示例 | 2 | 示例代码与说明齐全，沿用此前平台实测范围 |
| 中英文论文 | 22 | 两份PDF、18份LaTeX源码、共用文献及论文说明齐全 |
| 结果与追溯证据 | 116 | 当前修订结果、历史对照及说明均保留 |
| 运行与检查脚本 | 18 | 当前与历史入口明确区分 |
| 第三方许可证原文 | 2 | 保留各自上游条款 |

公开文件合计约14.4 MiB，最大文件为中文PDF（约3.33 MiB），本包不需要Git LFS。清单、189项文件哈希、Markdown本地链接及所用标题锚点、56处LaTeX资源引用均通过检查。190个文件在macOS本地Git暂存、对象读取与core.autocrlf=true检出后逐字节不变；8项隐私或构建产物排除规则通过探针检查。该预检阶段尚未创建正式提交或远程仓库。

实际上传建议从干净副本通过Git提交完整目录树；不要把本地运行目录混入，也不要只把ZIP当作仓库内容。GitHub网页上传每次至多100个文件，且不应用.gitattributes，故不适合作为本包的首选路径，见[官方上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)。容量判断依据见[官方大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

该预检阶段只补充发布准备记录并生成本地分发副本，未修改论文、实验结果、代码、配置或依赖。原始420个文件哈希保持不变。完整检查范围见[验证记录](validation.md)；本地交接包和操作说明存于generated/upload-preparation，不将该运行目录整体上传。

## 仓库与发布状态

| 项目 | 当前状态 |
| --- | --- |
| 项目许可证 | 代码Apache-2.0；作者有权许可的论文、文档及原创图表CC BY 4.0；第三方与数据边界保留 |
| GitHub仓库 | [NaiL00ng/stock-volatility-midas-epu](https://github.com/NaiL00ng/stock-volatility-midas-epu)，公开 |
| 版本 | 0.5-review，探索性研究档案；不提升为已验证的实时系统 |
| Git提交身份 | Boursin Nickel；使用目标账号设置页核实的GitHub noreply邮箱 |
| 上传后的验收 | 2026-10-31匿名克隆190文件核验通过；macOS ARM64新venv安装26个wheel、最小示例与独立检查通过；具体范围见[验证记录](validation.md) |

两份PDF和研究源码沿用已审阅的修订稿；当前获取与引用地址见[论文说明](../paper/README.md)及[CITATION.cff](../CITATION.cff)。历史准备记录中的“尚未上传”等指相应阶段。论文结果、数据授权边界和研究限制不因公开上传而改变。
