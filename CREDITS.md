# 素材与授权说明 / Credits

这个仓库里的演示视频有三个版本，音轨来源不同。**代码和动效本身不依赖任何第三方素材**，只有第三个版本例外。

## 三个演示版

| 文件 | 音轨 | 第三方素材 | 状态 |
|---|---|---|---|
| `docs/demo.mp4` | 解说 + 音效 + **程序化合成 BGM** | 无 | 默认版本，全部自有 |
| `docs/demo-no-bgm.mp4` | 解说 + 音效，**无背景音乐** | 无 | 全部自有 |
| `docs/demo-carefree.mp4` | 解说 + 音效 + **Carefree**（Kevin MacLeod） | 有，见下 | CC BY 4.0，已署名 |

前两个版本的配音由 edge-tts 生成，音乐和音效由 `scripts/audio.py` 用 numpy 程序化合成（Karplus-Strong 拨弦 + 鼓组 + 五类音效）。**不含任何第三方录音。**

## 第三方音乐署名

`docs/demo-carefree.mp4` 使用的背景音乐：

```
Carefree — Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0
https://creativecommons.org/licenses/by/4.0/
```

- 曲目页：https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400037
- 授权：Creative Commons Attribution 4.0 International（CC BY 4.0）
- 允许商用、允许改编、允许再分发，**唯一义务是署名**。本项目已在正文、本文件与该视频的说明中署名。

## 关于这首曲子

CC BY 4.0 **不是**「无版权」，它是有版权但预先授权。它的实际约束只有两条：

1. 你（和任何二次使用这个视频的人）必须保留署名。转发视频时把这段 credit 一起带过去即可。
2. 不能给这首曲子或它的衍生版本再加限制（比如声明成自己的独家版权）。

所以把它放进开源仓库没有法律障碍，但它**不是我自己的东西**，这也是默认演示版改用合成音乐的原因：拿到仓库的人可以直接商用、二创、剪进自己的片子，不用处理任何署名链路。

**仓库不附带这首曲子的音频原文件**，只附带混音后的成片。想在自己的片子里用它，请自行从 incompetech 下载并保留上面的署名。

## 如果你要换音乐

在 `beats.json` 里设 `bgm.source: "file"` 挂自己的曲子。授权自己确认一遍：

- **CC0 / Public Domain** — 随便用，不用署名。
- **CC BY** — 可以商用，必须署名（像上面那样）。
- **CC BY-NC** — 不能商用。
- **YouTube 音频库** — 标「无需署名」的可直接用；标「需署名」的按提示贴。
- **流媒体平台上的商业歌曲** — 不要用。哪怕只用了 3 秒。

不放心就用 `scripts/audio.py` 的合成 BGM（`bgm.enabled: true` 且不指定 `source`），完全自有。
