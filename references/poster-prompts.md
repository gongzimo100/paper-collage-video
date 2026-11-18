# 海报 prompt 库（ImageGen 用）

片子好不好看，八成取决于这 3–6 张海报。渲染引擎只做"让纸片动起来"，它变不出质感。

## 核心原则：让 AI 只出画面，绝不出字

AI 生图写中文字**必错**，写字英文也常糊。而纸片拼贴的灵魂恰恰是那行粗体标题。

所以分工是死的：

- **AI 负责**：纸张质感、撕边、胶带、半调网点、场景构图
- **本地代码负责**：标题纸条、字幕、水印（Pillow + 系统字体，一个字不会错）

每条 prompt 都必须带这句：`ABSOLUTELY NO lettering, no words, no readable text anywhere.`
生成后**一定看图确认**，有字的直接重生——有字的图在动画里会变成一坨糊。

## 通用骨架（直接抄，只换 SCENE 和颜色）

```
Overhead flat-lay paper collage poster, the whole frame completely filled edge-to-edge with
bold flat {底色} paper as the dominant surface. Style: clean modern flat 2D illustrated collage
in the Vox explainer motion-graphic style, bold flat-color vector-illustration cut-outs, simple
confident shapes, limited palette of {底色}, cream, {点缀色}, black, crisp infographic editorial
layout. Clearly layered hand-cut paper cut-outs with visible torn and scissor-cut edges, tape
corners and soft real paper drop shadows. Halftone print dots, newspaper-clipping scraps,
paper-stencil shapes, aged paper texture, slight print misregistration, scattered geometric
paper accents (triangles, circles, zigzags, washi tape). Figures are PRINTED / illustrated
cut-outs, NOT CGI, NOT a 3D render — keep print grain and paper imperfections. High-contrast,
punchy, tactile, hand-assembled, densely layered all over the frame.
SCENE (as layered paper cut-outs): {具体场景}.
ABSOLUTELY NO lettering, no words, no readable text anywhere.
Keep the top quarter calmer so a title strip can be added later.
Vertical 9:16 poster composition.
```

三个约束不能删：

| 句子 | 为什么 |
|---|---|
| `whole frame completely filled edge-to-edge` | 不说这句，模型爱留大片白底，动态一推镜就露怯 |
| `NOT CGI, NOT a 3D render — keep print grain` | 不说这句，出来是塑料质感的 3D 渲染，没有纸味 |
| `Keep the top quarter calmer` | 标题条要压在 15.6% 高度上，这里必须有留白 |

## 配色轮换（相邻两拍不要同色）

| 底色 | 点缀 | 情绪 | 适合的段落 |
|---|---|---|---|
| 暖赭黄 `warm ochre` | 砖红 / 墨黑 | 开场、暖 | 提出问题 |
| 墨水蓝 `deep ink blue` | 芥黄 / 米白 | 冷静、可信 | 讲方法 |
| 砖红 `deep brick red` | 米白 / 芥黄 / 一点青 | 有劲、强调 | 讲结果 |
| 深青 `deep teal` | 米白 / 芥黄 | 技术感 | 讲机制 |
| 芥末黄 `mustard yellow` | 墨黑 / 米白 / 一点红 | 活泼 | 讲速度、动效 |
| 米白 `cream off-white` | 墨黑 / 一点红 | 收尾、盖章 | 结论、CTA |

引擎会自动按拍号轮换标题条的底衬色（黄/青/红/黑），海报配色跟着这套走才统一。

## 场景描述怎么写

场景要写成**"一堆纸片怎么摆"**，不是"一个概念"。动词用剪纸的动作：taped、pasted、cut-out、peeling、stuck along。

已验证好用的几种：

| 讲什么 | SCENE 怎么写 |
|---|---|
| 输入 → 输出 | `a cut-out lightbulb silhouette on the left transforming step by step into a strip of photographic film on the right, a small washi-tape arrow pointing between them` |
| 多种入口 | `three polaroid-style paper cards taped in a row — the first a folded note with a pencil, the second a small screen frame holding a printed portrait of a talking person, the third a handheld snapshot of a face` |
| 分层/步骤 | `one finished collage poster lying flat in the lower part of the frame, while its layers peel apart and float upward as four separated torn paper sheets, thin dotted paper lines connecting them` |
| 速度/流程 | `long torn paper strips arcing in from the left and right edges toward an empty torn-paper frame in the centre, paper-cut arrows and striped speed lines sweeping inward` |
| 流水线 | `a long horizontal strip of film-tape crossing the frame like an editing timeline, with chunky cut-out icons stuck along it in a row — a loudspeaker, a music note, a subtitle bar, a gear, a play button` |
| 结论/认可 | `two large round paper approval medallions side by side, the left stamped with a bold black paper check-mark cut-out and the right with a black paper star, a torn paper arrow pointing at them from below` |

## 出图参数

| 画幅 | size | 说明 |
|---|---|---|
| 9:16 | `1024x1536` | 裁掉底部 4%（去角标）后 cover 到 1080×1920 |
| 16:9 | `1536x1024` | 提示词末句改成 `Horizontal 16:9 poster composition.` |
| 1:1 | `1024x1024` | 末句改成 `Square 1:1 poster composition.` |

生成后放进 `<proj>/keyframes/`，命名 `kf_1.jpg`、`kf_2.jpg`……（PNG 转 JPG 质量 95 即可，省一半体积）。
`posters` 里写相对路径。

## 验收：四条都过才留

1. **有纸感** — 能看见撕边、胶带、投影、半调网点。看不出纸就是废图。
2. **没有字** — 任何可读字母/汉字都不要，包括看似"装饰"的小字。
3. **底色铺满** — 四边不留白底。
4. **上方四分之一不挤** — 标题条会压在那里。

不合格就重生，一次只改一句 prompt（通常是补 `densely layered` 或加重底色描述）。
同一张图重生超过 3 次还不理想，**换场景描述**，别继续调形容词。

## 复用省钱

- 同一个概念可以给两拍共用一张图（`"poster": "keyframes/kf_1.jpg"` 覆盖映射）
- 改文案不用重出图，只重跑渲染
- 一张图约 5–10 credits，一条 6 拍的片子正常 4–6 张就够
