---
name: paper-collage-video
description: 纸片拼贴风解说片生成器（Vox / paper-collage explainer）——把任何主题做成一条 9:16 或 16:9 的纸片剪贴动画短片：AI 只出拼贴海报，纸片飞入/回弹/震屏/镜头缓推由本地逐帧引擎画，中文配音走 edge-tts，BGM 与音效全部程序化合成，ffmpeg 收口。当用户说"做成纸片风""纸片拼贴""剪纸风介绍片""拼贴动画""Vox 风格视频""纸片定格""把这个项目/产品/文章做成一条几十秒的介绍片""带配音和音乐的小视频"时使用。全程零视频 API，只有生图消耗额度。
---

# 纸片拼贴 · 讲解片生成器

一句话进，一条拼贴动画片出：**AI 只负责出海报，动态 / 配音 / 音乐 / 字幕全部本地生成**。

> 本项目改造自 [Alisa0808/vox-director](https://github.com/Alisa0808/vox-director)（MIT）。
> 原项目走 Claude Code + Atlas Cloud 付费接口，这里把出图交给宿主的 ImageGen、动效/配音/配乐全部本地化。
> 代码是重写的，沿用方法论与海报 prompt 定式。不是官方版本。授权见 `LICENSE`。

这条管线的价值在于：纸片拼贴的动态本质是"纸片啪一下拍上去、弹一下、镜头缓缓推"，这种动作**代码做得比视频模型更准、更清晰**，而且一帧都不花钱。用视频模型反而常把剪纸糊成塑料。

## 何时用 / 不用

**用**：项目介绍、产品说明、知识科普、文章转视频、周报视频化、活动预热——任何需要 15–60 秒、有节奏、有配音的说明性短片。

**不用**：需要真人/实拍、需要复杂运镜（航拍、跟拍）、需要口型同步、需要长片（>90 秒请拆条，或换别的管线）。

## 五步流程

| 步 | 谁干 | 动作 | 产出 |
|---|---|---|---|
| 1 | 你 | `python scripts/doctor.py` | 环境自检通过 |
| 2 | 你 | 写 `<proj>/beats.json` | 分镜表（唯一数据源） |
| 3 | **你调 ImageGen** | 按 prompt 库出 3–6 张海报 | `keyframes/kf_*.jpg` |
| 4 | 脚本 | `python scripts/run.py <proj>` | `final.mp4` |
| 5 | 你 | 抽帧看图 + `verify.py` 报告 | 通过或返工 |

**第 3 步只能由你做**，因为 ImageGen 是 agent 工具，不是 Python 能调的接口。脚本在这里只负责"把清单列出来 / 把已就位的图吃进去"。这也是为什么重跑渲染永远不会重复花钱。

## 步骤 0：环境

```bash
python scripts/doctor.py            # 缺什么会直接告诉你
python scripts/doctor.py --install  # 缺的包一次装完
```

硬依赖只有三样：`pillow`、`numpy`、`edge-tts`，加一个 ffmpeg 二进制。
ffmpeg 按这个顺序找：`$FFMPEG_BIN` → `<skill>/tools/ffmpeg.exe` → PATH → `imageio_ffmpeg` 自带。
**拿不到 ffmpeg 时不要死磕 winget 或官网直连**（这两条在国内常失败/被限速到 25KB/s），直接 `pip install imageio-ffmpeg`，它有预编译静态包，装完自动被识别。

## 步骤 1：写分镜

复制 `examples/beats.example.json` 改成自己的。字段全在 `references/beats-spec.md`，这里只讲三条最容易踩的：

- **每句旁白 12–18 字**，一个信息点。中文 TTS 约 4.8 字/秒，6 拍 × 2.5 秒 ≈ 23 秒
- **`title_cn` 2–5 字**，是标签不是句子；标题和旁白不许重复同一个说法
- **总时长由 `voice.tail` 控制**（默认 1.06 秒/拍）。要更紧凑就调到 0.7，要更从容就 1.4

## 步骤 2：出海报（唯一花钱的一步）

读 `references/poster-prompts.md`，里面有可直接改的骨架、6 组配色、6 种已验证场景写法。

不可违反的三条：

1. **prompt 里必须有 `ABSOLUTELY NO lettering, no words`**——中文大字由本地字体渲染，AI 写字必错
2. **必须有 `whole frame completely filled edge-to-edge`**——否则模型留白底，推镜就露怯
3. **必须有 `Keep the top quarter calmer`**——标题条压在 15.6% 高度

参数：9:16 用 `size=1024x1536`，16:9 用 `1536x1024`，输出到 `<proj>/keyframes/`。
出完**逐张看图验收**（有字？有纸感？底色铺满？上方留白？），不合格重生，别带着废图往下走。

## 步骤 3：一条命令出片

```bash
python scripts/run.py <proj>               # 配音 → 渲染 → 自检，全流程
python scripts/run.py <proj> --no-tts      # 文案没改，只重渲画面
python scripts/run.py <proj> --size 1920x1080
```

单步：

```bash
python scripts/tts.py <proj>      # edge-tts 配音 + 削首尾静音 + 时长回写（~10s）
python scripts/render.py <proj>   # 逐帧动效 + 混音 + 编码（6 拍 ~2-3 分钟）
python scripts/verify.py <proj>   # 电平/削波/空档/时长自检
python scripts/frame.py <proj>    # 抽帧，供肉眼验收
```

`render.py` 每次都整体重渲，不会残留旧片段——所以改任何参数都可以直接重跑。

## 画面里到底发生了什么

引擎每拍做的事（全在 `scripts/render.py`，约 300 行）：

- **镜头缓推** 1.0 → 1.055，纵向轻微上移，模拟手持推近
- **标题纸条**拍入：从 1.34 倍缩放到 1.0，配 back-ease 回弹 + 6 帧衰减震屏 + 从 -6° 转到 -1.4°
- **装饰件**从画外飞入：胶带 + 半调圆片，奇数拍从左、偶数拍从右（自动避开底部字幕区）
- **字幕**在拍内 0.42 秒后淡入，`fit_sub` 自动缩字号保证不超过两行，`wrap` 做避头点（标点不孤零零掉行）
- **转场** 4 帧白闪衰减，遮住硬切
- **纸条/字幕/水印全部本地字体渲染**（微软雅黑 Bold），所以中文零错字

声音侧（`scripts/audio.py`）：112 BPM 尤克里里走 C-G-Am-F，扫弦是谐波合成，鼓组合成，音效 5 类卡在动作点上（标题拍入的 slap、飞入的 whoosh、贴纸的 tape、转场前的 riser、收尾铃），**人声包络带侧链**——说话时音乐自动压到 28%，说完抬回来。

### 用现成音乐代替合成 BGM

合成 BGM 节奏天然对齐、零版权风险，但终究是程序化的，听感偏"电子"。要更真实的律动，挂外部曲子：

```json
"bgm": {
  "enabled": true,
  "source": "file",
  "file": "audio/bgm.mp3",
  "start": 0.0,
  "gain": 0.50,
  "duck": 0.72
}
```

- `file` 相对项目目录，`start` 是从曲子第几秒开始取（跳过前奏），不够长会自动无缝循环（接缝 60ms 交叉淡化）
- 外部曲子母带响度差别很大，脚本会先按 RMS 归一到 0.085，所以 `gain` 的语义对合成和外部音乐一致；挂外部曲子时 `gain` 通常要 **0.45–0.55**，合成时是 **0.22–0.38**
- 换音乐**不需要重渲画面**，视频流直接 copy：

```bash
python scripts/audio.py <proj> --bgm-file audio/bgm.mp3 --bgm-start 4 --bgm-gain 0.5 --out mix-b.wav
# 然后只换音轨重新封装（-c:v copy，零画质损失）
```

要想完全不花钱、也能改配音/音乐而不动画面，就靠这一条——画面渲染一次，音轨可以反复试。

**外部音乐务必确认授权。** Kevin MacLeod（incompetech.com）全站 CC BY 4.0，可商用但**必须在视频描述或片内署名**；选 CC0 曲库（如 Pixabay、FreePD 原有的曲目）则无需署名。没确认授权的曲子别直接上，平台音乐库识别到会限流或下架。

## 步骤 4：验收（不要跳过）

听不到声音也能判断片子对不对，两条命令：

```bash
python scripts/frame.py <proj>          # 自动抽每拍中点，输出到 build/frame_*.png
python scripts/frame.py <proj> 2.2 9.6  # 指定时刻
# 然后用 ViewImage 逐张看
python scripts/verify.py <proj>
```

`verify.py` 会报：时长/画幅是否与分镜吻合、峰值与削波率、每秒 RMS、>0.6s 的空档、每拍配音时长。
**判断标准**：峰值 ≤1.0、削波 <0.05%、无 >1.2s 空档、时长与分镜合计差 <1s。

抽帧重点看三处：字幕有没有压住主体、标题条有没有撞到拼贴元素、暗底上水印是否还看得见。

## 调参手册

| 想要什么 | 改哪里 |
|---|---|
| 更紧凑 / 更从容 | `voice.tail`（0.7 / 1.4） |
| 语速更快 | `voice.rate` 调到 `+12%`（别超 +18%，会像念稿机） |
| 换音色 | `voice.voice`，音色表在 `references/beats-spec.md` |
| 音乐更响 / 更轻 | `bgm.gain`（合成 0.22–0.38；外部曲子 0.45–0.55） |
| 音乐更欢快 | 合成：`bgm.bpm` 调到 128；或换外部曲子（`bgm.source: file`） |
| 音乐从哪进 | `bgm.start`（秒），跳过前奏直接进主段 |
| 不要音乐 | `bgm.enabled: false` |
| 换画幅 | `aspect` 改 `16:9` / `1:1` / `4:5`，代码按比例自适应，不用改 |
| 换水印 | `watermark`，空字符串则不画 |
| 去角标更狠 | `poster_crop_bottom_ratio`（0.04 → 0.06） |

## 常见故障

| 现象 | 原因 / 处理 |
|---|---|
| 标题是方块 | 系统没中文字体，设 `COLLAGE_FONT_BOLD=/path/font.ttc` |
| 找不到 ffmpeg | `pip install imageio-ffmpeg`，别去官网下 |
| 配音全静音 | edge-tts 需要访问 `speech.platform.bing.com`，墙外网络受限；换网络或 `doctor.py` 看连通性 |
| 画面糊 | 海报原图太小或被二次压缩。改用 1024x1536 原图直接放 `keyframes/`，别先缩 |
| 字幕掉两行且挤 | 该拍旁白超过 22 字，回 `beats.json` 拆句 |
| 转场闪白看不见 | 正常，只有 4 帧。想要更强就把 `render.py` 里白闪 alpha 数组调高 |
| 音画不同步 | 手改过 `dur`。改文案后必须重跑 `tts.py`，让 `dur` 重算 |
| 视频模型糊纸片 | 你没在用本地引擎，走的是 VideoGen。这类片子建议全用本地逐帧 |

## 成本

- **出图**：5–10 credits/张，一条 6 拍的片子 4–6 张 ≈ 25–50 credits
- **其余全部为零**：动效、配音、BGM、音效、编码都在本地跑
- 改文案、换音色、调音乐、换画幅、重渲——**一律不花钱**

这也是这条管线相对 vox-director 原版的核心差异：原版每帧都走 Atlas Cloud 付费 API，一条 60 秒片子约 1200–2000 credits；这条管线把它压到只付生图的钱。
