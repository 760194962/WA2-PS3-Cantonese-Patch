# WHITE ALBUM2 幸せの向こう側（PS3 / BLJM60571）粤文化补丁
PC 版见 [WA2EE-Cantonese-Patch](https://github.com/760194962/WA2EE-Cantonese-Patch)。

把粤语字幕视频的译文（ic 组 ASS）做进 PS3 版游戏。字体用俊羽圓體（YuPearl），粤字缺字用源泉圓體补。

外传《雪融方恨遲，留待至他朝再次飄雪時》（雪が解け、そして雪が降るまで）的译文采集自 raymondsakura 的公开 YouTube 频道。

本仓库只放工具、脚本和记录。游戏文件（EBOOT、data.dar、日文脚本）、字幕 ASS、字体都不提交。

## 目前进度

- IC（1001–1013，含二周目分支）：10504 / 10665 行已换成粤文。剩下 161 行见 `notes/untranslated_ps3_only.txt`：62 行是 PS3 新增或改写（PC 版没有），99 行 PC 版也有但字幕视频里没有。
- 外传「雪が解け、そして雪が降るまで」（脚本 5000–5004，小说模式）：1896 / 1897 段已换成粤文。
- 字幕漏对的句子：用 PC 版脚本当桥梁找回（`tools/pc_bridge.py`），二周目字幕里的场景和个别句子手工固定（`build_yue3.py` 的 `MANUAL`）。
- 超过 27 字宽的行在构建时重新断行（先保持原行数，只在标点处断，最多 4 行）。
- 说话人名字已改粤文写法（对照表在 `tools/build_yue3.py` 的 `SPEAKER_MAP`）。
- 英文照字幕原样（半角/全角）逐字显示；半角字按各自字宽前进（改了 EBOOT 的绘字代码，对话框和回放记录都已在实机确认）。
- 注音：日文有 `<R…|…>` 而粤文译文写成括号的 4 处已改回注音（`RUBY_FIX`）。
- 实机：HEN PS3 上以 1.01 更新目录方式运行正常，IC 已推进到结尾。RPCS3 未测试（模拟器跑 WA2 不稳定）。
- 待改译文：`notes/text_fixes_todo.txt`。

## 还没做

1. 补写 161 行仍是日文的台词（自己写粤文，需过目）；待改译文见 `notes/text_fixes_todo.txt`。
2. PS3 独有的追加剧情（脚本 4000–4009、5200–5401）和另一篇小说 5100–5104：没有现成字幕。
3. CC 以后的部分（没有现成字幕）。
4. 1.01 PKG：`PARAM.SFO` 的 APP_VER 设 01.01 或更高；补丁改用 1.01 的 EBOOT 做（先跑 `decrypt_101.bat`）。
5. 开场视频（mv01 等）烧录字幕；外传菜单标题（贴图）。
6. PC 版补丁（PS3 版完成后）：`tools/pc_kcap.py` 已能解 PC 的 `script.pak`。

## 使用（Windows）

`python build.py` 跑完后，成品都在 `output\`（不会改动游戏文件夹），直接复制：

- `output\data.dar` → 光盘位置 `.../PS3_GAME/USRDIR/data.dar`（FTP 用二进制模式，1.9GB）
- `output\ps3_npdrm_v3\update_patched\EBOOT.BIN` → PS3 的 `/dev_hdd0/game/BLJM60571/USRDIR/`（scetool 签成 NPDRM UEXEC、key-revision 01、FREE；HEN 不接受光盘位置的 EBOOT，会报 80010009）
- RPCS3：`output\data.dar` 和 `output\rpcs3\EBOOT.BIN` 放进游戏文件夹 `PS3_GAME/USRDIR/`
- EBOOT 和 data.dar 必须是同一次构建，否则字会错位。

（旧流程 `windows/` 里的 bat 仍可用：放进 `cantonese_patch\`，与构建输出一起运行。现在由 `tools/package.py` 代替。）

## 发布包

`python tools/make_release.py v0.1` 生成 `output/release/WA2_PS3_Cantonese_v0.1.zip`（约 2.3MB），不含任何游戏文件：
字库是 `data.dar` 第 2309 项的压缩包，EBOOT 是对官方 1.01 更新 EBOOT（解密后）的差异文件（`EBOOT.wa2d`）。
用家把自己的 `data.dar`、1.01 的 `EBOOT.BIN` 放进 `input\`，scetool 放进 `scetool\`，双击「安裝補丁.bat」，
补丁程序（`tools/release/apply.py`，只用 Python 标准库）会校验版本、解密、套用差异、签名，并给 `data.dar` 打补丁（可还原）。

## 构建

仓库文件夹本身就是素材文件夹（`tools/paths.py` 默认 DATA=仓库根目录；也可设环境变量 `WA2_DATA` 或写 `config.json` `{"data_dir": "..."}`）。需要这些（都不提交）：

```
WHITE ALBUM2 [BLJM60571]/PS3_GAME/USRDIR/EBOOT.elf   原版 v1.00 解密 EBOOT（6,964,168 字节）
dar_dump/02309.bin                                   data.dar 第 2309 项解出的原字库包
ic_ass/*.ass                                         粤语字幕
fonts/YuPearl-1.011/tw/*.ttf                         俊羽圓體（GenSenRounded2TC-M.otf 缺时自动下载）
```

```
pip install numba opencc-python-reimplemented fonttools pillow pylzma
python tools/novel_map.py   # 外传：字幕段落 ↔ 小说页（改了字幕或对齐时才需要重跑）
python tools/pc_kcap.py "WHITE ALBUM2/script.pak" work/pc_jp   # 解 PC 版脚本（一次即可）
python tools/pc_bridge.py   # 用 PC 版脚本找回漏对的字幕
python build.py             # 提取日文脚本 → 对齐 → 过滤 → 生成 → 校验 → 索引 → 打包到 output\
```

中间产物在 `work/build/`；打包需要 `data.dar (bak)`（原版 data.dar）和 `cantonese_patch\scetool\scetool.exe`。
`lzenc`（可选，更快）：`gcc -O2 tools/lzenc.c` + LZMA SDK（pylzma 0.6.1 源码 `src/sdk/C`）；没有则用 pylzma。流不能带结束标记、dict 2^14、lc3 lp0 pb2，游戏的解码器不接受带结束标记的流。

## 引擎笔记（v1.00 EBOOT）

- **资源表**：文件偏移 0x106edc 起，每项 16 字节 BE（name_off, data VA, 原大小, 压缩大小），VA = 文件偏移 + 0x10000。脚本是 elzma（64KiB 分块，块头 `<II usize,csize>` + `5d 00 40 00 00 00 00 00` + 裸 LZMA）。
- **字表**：0xFE3F0 起 2706 个 u16 编码，序号 = 贴图格子序号。查字用 bsearch，所以字表必须按编码升序。新字用 0xF043 起的编码（跳过低字节 < 0x40、0x5C、0x7F）。
  - 初始化：0xC98A 的 `li r3,N` 是字数；原本 malloc 一块再展开，我们改成指向 0x120E00 的静态数组（0xC9F0、0xCA04 两处 lis/addi）。
- **贴图**：data.dar 第 2309 项是 pkg，第一张 GTF 是 2040 宽、A4R4G4B4、40×40 格、51 列；高度可加大（目前 3800，上限 4096）。
- **画字**（0x4e21c，调用者 0x51400 等）：整个 40×40 格子都画出来；全角字每个前进「字号 + 字间距」，换算回贴图约 **29 px**（半角一半）。字体参数由 0x494ac 设定（格子 40、字号 28）。所以汉字之间格子互相重叠，汉字本身两边留空所以看不出。
- **英文**：游戏原本的半角英文是等宽窄字，日文原文里英文一律用全角。我们把英文整词按正常字距渲染，再切成 29 px 一段放进每格中间，左右各带 1 px 相邻笔画，避免平滑处理时露出接缝。
- **注音**：`<R本文|ルビ>`，粤文也可以用。
- **脚本空间不够放译文**：把数据段（第 1 段）的 filesz/memsz 延伸到 .bss 结束之后（VA 0x1209A00），译文脚本放在那里，非载入的 section 和节头表整体后移。新增 PT_LOAD 段的做法 HEN 会报 80010001，不能用。
- **回放记录**存的是当时的文字编码。字表一变，旧存档的回放记录会乱码，属于正常现象，新显示的句子不受影响。
- HEN：光盘位置的 EBOOT（NPDRM EXEC）会报 80010009，只能走更新目录。
