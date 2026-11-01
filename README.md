# mmBench：多模态能力评测

[![CI](https://github.com/BAI-AI-Lab/mmBench/actions/workflows/ci.yml/badge.svg)](https://github.com/BAI-AI-Lab/mmBench/actions/workflows/ci.yml)

mmBench 测"看得懂图的模型"：输入图片、图表、文档、截图或视频帧，输出文字。所有模型答同一套题，同一份结果给出两样东西：

- **能力画像：** 7 项能力各自的得分和 95% 区间，看一个模型强在哪、弱在哪。
- **排名：** 7 项等权合成总分，两两做配对比较，分不开的并列，并写明这套题能分辨多大的差距。

7 项能力**彼此尽量不重叠**：每项只测一种技能、只用一类答题形式，会测到别的能力的题在抽题时就过滤掉。这样某一项的分数低，就只说明这一项弱，不会被别的能力拖累。

题目从 11 个公开评测集按固定随机种子抽取，同一个种子永远抽出同一套题。打分只用确定的规则，不用模型当裁判。

**结果网站：** <https://bai-ai-lab.github.io/mmBench/>：2026-10-31 三个模型的能力画像、排名、费用，评测集说明和逐题结果。网站由 `python web/build.py` 从 `paper/` 的数据生成到 `docs/`（GitHub Pages），不含题面和图片。

## 7 项能力

| 能力 | 测什么 | 答题形式 | 来源（题数） | 难度 | 为了不重叠，排除了什么 |
|---|---|---|---|---|---|
| 学科推理 | 结合学科知识看图推理 | 选择题（10 选 1） | MMMU-Pro 标准版（50） | L1–L3，用它自带的难度标签 | 表格、统计图、截图类的题（归文档、图表、界面定位）；"题目印在图里"的版本（那是读文档） |
| 视觉感知 | 低层视觉：计数、对应点、相似度、反射率、伪造检测、拼图、画风 | 选择题 | BLINK 的 9 个子任务，各 6 题（54） | L2 | BLINK 的深度、方位、多视角、定位 4 个子任务归空间；IQ 测试是抽象推理，不收 |
| 图表 | 读图表的数值、比较、趋势 | 短答案 | ChartQA（15）、CharXiv 推理题（35） | L1、L3 | — |
| 文档 | 读密集文字的页面：表单、版面、表格、收据 | 短答案 | DocVQA（30）、OCRBench 的关键信息抽取（20） | L1、L2 | DocVQA 中问插图和照片的题；信息图（InfographicVQA，本质是图表加文字）；OCRBench 的文档问答（就是 DocVQA、ChartQA、InfoVQA） |
| 空间 | 深度、距离、方位、多视角想象 | 选择题 | CV-Bench 3D（14）、BLINK 空间子任务（16）、MindCube（20） | L1、L2、L3 | 要用坐标作答的题（RefSpatial）；坐标只属于界面定位 |
| 界面定位 | 在截图上找到要点击的图标 | 坐标（0–1000） | ScreenSpot-v2（20）、ScreenSpot-Pro（30） | L1、L3 | 文字目标（等于读字加点击，会和文档重叠） |
| 视频时序 | 单看一帧答不出来的时序问题 | 是非题、二选一 | TimeBlind（50） | L3 | 考专业知识的视频题（MMVU，那是学科推理） |

共 354 题，按难度大约是 L1 96 题、L2 107 题、L3 151 题。每个来源的难度按它对现在的模型是否已经饱和来定，MMMU-Pro 按题自带的难度分档。

## 怎么打分

全部是确定的规则（`mmbench/mm_lib.py`）：

| 题型 | 怎么判 |
|---|---|
| 选择题 | 取回答最后一行 `Answer: X` 中的选项字母，与标准答案相同得 1 分 |
| 是 / 否 | 取最后的 yes 或 no |
| 短答案 | 标准答案是数字时，取回答里的数（可以带单位或 million、billion 等量级词），相对误差 1% 内（ChartQA 按它的规则放宽到 5%）；文字规范化后（小写、去冠词和标点）完全相同 |
| 文档 | ANLS：与最接近的标准答案的归一化编辑距离相似度，低于 0.5 记 0（DocVQA 的规则） |
| 界面定位 | 模型给出 0–1000 的相对坐标，换算到原图后落在目标框内得 1 分 |

读不出答案、生成超时、输出被截断都记 0 分，报告里分别计数。接口始终没有回答（重试用完）的不算模型的错，不计入，下次运行会重问。

## 统计方法

- **单项得分：** 每题每个模型答 k 次（默认 4 次），题目得分取平均；单项得分是该项各题得分的平均，0–100。
- **总分：** 7 项能力的等权平均，不按题数加权。
- **区间：** 每项能力的 95% 区间来自按题重抽样（bootstrap，2000 次）。两个模型的总分差，在每项能力内成对重抽样得到区间。
- **名次：** 名次 = 1 + 明显强于它的模型数。差值区间包含 0 的两个模型判为平手，名次相同。另外给出逐题胜负和符号检验。
- **分辨率：** 每项 50 题时，单项区间约 ±14 分；354 题的总分大约能分出 7–8 分的差距。报告里会写出这套题实际的区间半宽，比它小的差距分不出来。

只比较所有模型都答过的题。

## 评测约定

- **视频：** 每段视频按时间均匀抽 16 帧，作为图片发给模型；所有模型拿到同样的帧，分数才可比。厂商自己的原生视频输入不进排名。
- **图片：** 以 base64 内嵌在请求里。超过 7 MB 的图片在建库时转成 JPEG，以免超过各家接口的大小上限。
- **temperature：** 默认不发送，各家用自己的默认值（有的模型不接受别的值，有的会忽略）。
- **思考深度：** 用 `REASONING_EFFORT` 设定，参加比较的模型要设成一样。
- **MAX_TOKENS：** 默认不设上限，因为思考也占这个上限，设小了会得到空答案。

## 快速开始

需要 Python 3.10 以上；建视频题需要 ffmpeg；生成 PDF 报告需要 xelatex（带 ctex）。

```bash
git clone git@github.com:BAI-AI-Lab/mmBench.git && cd mmBench
bash install.sh                      # 在 .venv 里装 openai、httpx、Pillow、matplotlib
                                     # 在国内：MMB_MIRROR=cn bash install.sh

bin/mmb list                         # 各来源、能力、难度、题数
bin/mmb build --dry-run              # 只检查能不能抽满，不下载
bin/mmb build                        # 只下载抽中的题，写到 data/（约几百 MB）

export MODEL=<模型名> OPENAI_BASE_URL=<兼容 OpenAI 的接口地址> OPENAI_API_KEY=<密钥>
bin/mmb run --smoke                  # 每项能力 1 题，答 1 次：先把链路跑通
bin/mmb run --k 1                    # 每题答 1 次：看实际的 token 和费用
bin/mmb run                          # 正式运行（每题 4 次），结束后自动出单模型报告

bin/mmb report runs/A/mm-full runs/B/mm-full --out reports/2026-11-01_A_vs_B   # 多模型画像与排名
```

运行中断后，再跑同一条命令只补没答完的题，不会重复花钱：
- 回答一到就追加写进 `usage.jsonl` 和 `answers.jsonl`，两份里任意一份在，这道题就不会再问。
- 日志最后一行如果因为断电写了一半，会跳过并提示，不影响续跑。
- 同一个运行目录同时只能有一个进程在跑，第二个会直接退出（退出码 5），不会把同一道题问两遍。
- 开始前会先检查每道题的图片和视频帧都在，缺文件就不发任何请求。

想暂停时，在运行目录下建一个 `STOP` 文件：已经发出的请求会答完，然后程序退出。账户余额不足时会自动停下，已答的题保留。

第一次建好题库后，把 `data/mm.json`（只有题号）复制到 `samples/mm.json` 并提交，以后所有模型都用这套题。

### 环境变量

| 变量 | 作用 |
|---|---|
| `MODEL`、`OPENAI_BASE_URL`、`OPENAI_API_KEY` | 被测模型（必填） |
| `MODEL_NAME` | 报告里显示的完整模型名 |
| `REASONING_EFFORT` | 思考深度，作为 `reasoning_effort` 发送，例如 low / high / max |
| `MM_K` | 每题答几次，默认 4 |
| `MM_TEMPERATURE`、`MM_DETAIL`、`MM_OMIT` | 要发送的 temperature；图片 detail；请求里要去掉的字段 |
| `MAX_TOKENS` | 输出上限，默认不设 |
| `WORKERS`、`RETRIES`、`STREAM` | 并发数（8）、重试次数（3）、是否流式（1） |
| `MM_TIMEOUT`、`MM_MAX_SECONDS`、`MM_CUT_IS_TIMEOUT` | 流式请求多久没有新 token 就重试（300 秒）；单次请求的总时长上限；服务器断流多久以上算超时 |
| `PRICE_IN`、`PRICE_HIT`、`PRICE_OUT` | 每百万 token 的输入、缓存命中、输出单价，报告据此算费用 |
| `REPORT_AUTHOR` | 报告页脚的作者 |
| `MMB_HOME`、`MMB_DATA` | 数据和运行结果放在哪（默认本仓库下的 `data/`、`runs/`） |
| `HF_ENDPOINT`、`HF_DATASETS_SERVER`、`HF_TOKEN` | Hugging Face 镜像、datasets-server 地址、访问受限数据集时的 token |
| `MM_MAX_IMAGE_MB`、`MM_FRAMES` | 图片大小上限（7 MB）、每段视频的帧数（16） |

建库时如果需要代理才能访问 Hugging Face，设置 `https_proxy` 即可。建库时每个请求都带 `Cache-Control: no-cache`，并核对每个返回结果的数据集和行号是否与请求一致，所以按路径缓存的代理不会让题目错位。

## 目录结构

```
bin/mmb                  命令行：list / build / run / report / test
mmbench/mm_sources.py    各来源怎么把一行数据变成一道题（包括为了不重叠而做的过滤）
mmbench/mm_build.py      抽题、下载、抽帧，写 data/items 和 data/mm.json
mmbench/mm_lib.py        题目文件、提示词、答案提取和打分
mmbench/mm_run.py        对任意兼容 OpenAI 的接口作答（可续跑、可暂停）
mmbench/mm_api.py        单次请求与用量日志
mmbench/mm_report.py     能力画像、排名、按难度和来源的分数、成本与速度
mmbench/mm_render.py     Markdown / LaTeX 表格、符号检验、token 与费用
mmbench/mm_figures.py    能力画像柱状图（需要 matplotlib）
samples/models.json      报告"模型简介"一节的资料
tests/                   合成题目的测试和模拟接口
web/build.py             结果网站：读 paper/ 的数据，写 docs/（GitHub Pages）
```

运行目录里有：
- `run.json`：参数。
- `usage.jsonl`：每次调用的时间、token、结束原因和回答。图片只记文件名。
- `answers.jsonl`：每题每次的回答。
- `report/`：`report.md`、`main.tex`、`report.json`，以及有 matplotlib 时的图。

## 数据与许可

代码以 MIT 许可发布。题目、图片和视频帧**不进仓库、也不公开**，只放在运行评测的机器上的 `data/` 里，因为好几个来源只允许学术使用。仓库里只放代码、题号清单（`samples/mm.json`）和汇总分数。

| 来源 | Hugging Face 数据集 | 许可 |
|---|---|---|
| MMMU-Pro | MMMU/MMMU_Pro（图片取自 MMMU/MMMU 的同一题） | Apache-2.0 |
| BLINK | BLINK-Benchmark/BLINK（val） | Apache-2.0 |
| ChartQA | HuggingFaceM4/ChartQA | GPL-3.0 |
| CharXiv | princeton-nlp/CharXiv | CC-BY-SA-4.0 |
| DocVQA | lmms-lab-encoder/DocVQA | 镜像标注 Apache-2.0，原始数据见 DocVQA 条款 |
| OCRBench | echo840/OCRBench | 数据集页面未注明 |
| CV-Bench | nyu-visionx/CV-Bench | Apache-2.0 |
| MindCube | oscarqjh/MindCube_lmmseval（MLL-Lab/MindCube 的 tiny 集） | MIT |
| ScreenSpot-v2 | lmms-lab/ScreenSpot-v2 | Apache-2.0 |
| ScreenSpot-Pro | likaixin/ScreenSpot-Pro | MIT |
| TimeBlind | BaiqiL/TimeBlind | 仅限研究（见数据集页面） |

各来源的分数只是抽样子集上的得分，不能和这些评测集的官方榜单直接比较。CharXiv 官方用 GPT 判分，这里用精确或数值匹配，会严一些。

## 已知局限

- **能否真正分开要靠数据证明：** 7 项能力是按题目性质划分的。第一轮跑完后，可以在每项里抽几题不给图再答一遍；如果某项不看图也能答对，说明它测的是语言能力而不是视觉。
- **文档：** DocVQA 对现在的模型接近满分，这一项主要靠 OCRBench 的关键信息抽取拉开差距。
- **界面定位偏难：** ScreenSpot-Pro 只考图标后分数可能普遍很低。
- **视频只有一个来源：** 想再加一个专门考时序的集，可选的 TVBench、TempCompass 视频都打包在几百 MB 到几 GB 的压缩包里，要另写解包代码。
- **没有 L4：** 最难的一档现在空缺。

## 持续集成

每次推送和每个 PR 都会跑下面几项检查：
- **语法和代码风格：** Python 语法检查、Ruff、ShellCheck。
- **测试：** 在 Python 3.10 和 3.12 上跑完整测试，用合成题目和模拟接口：
  - 各题型的打分；
  - 抽题的可复现性；
  - 过滤规则；
  - 代理缓存检查；
  - 从作答到报告的完整流程。
- **密钥扫描：** gitleaks 扫描全部提交历史。

另外，每周一和手动触发时会对所有来源干跑一次（`--dry-run --strict`，只读元数据），数据集改名或字段变化时会报错。

## 技术报告

[`paper/main.pdf`](paper/main.pdf)：mmBench 的设计、构建、评分与统计方法，以及 Kimi K3.1 Pro、MiniMax M3.1 Flash、DeepSeek Flash V4.1-1017 三个模型的评测结果与成本分析。报告中的全部数字、表格与图由 `paper/` 下的脚本从运行日志生成：

```bash
MMB_HOME=<含 data/ 与 runs/ 的目录> python paper/collect.py   # 汇总运行结果（不含题目内容）
bash paper/build.sh                                         # 统计、表格、图与 PDF（需要 xelatex）
```

mmBench 从 [codingBench](https://github.com/BAI-AI-Lab/codingBench) 的多模态部分拆出，独立维护。

---

由 Albert Huang 创建于 2026-10-30
