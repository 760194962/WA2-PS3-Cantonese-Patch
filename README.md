# WHITE ALBUM2 幸せの向こう側（PS3 / BLJM60571）粤文化补丁

把粤语字幕视频的译文（ic 组 ASS）做进 PS3 版游戏。字体用俊羽圓體（YuPearl），粤字缺字用源泉圓體补。

本仓库只放工具、脚本和记录。游戏文件（EBOOT、data.dar、日文脚本）、字幕 ASS、字体都不提交。

## 目前进度

- IC（1001–1013，含二周目分支）：10403 / 10665 行已换成粤文，剩下 262 行是 PS3 改写/追加、两份 ASS 都没有的内容，见 `notes/untranslated_ps3_only.txt`。
- 说话人名字已改粤文写法（对照表在 `tools/build_yue3.py` 的 `SPEAKER_MAP`）。
- 英文按整词渲染（见下面「英文」一节）。
- 注音：日文有 `<R…|…>` 而粤文译文写成括号的 4 处已改回注音（`RUBY_FIX`）。
- 实机：HEN PS3 上以 1.01 更新目录方式运行正常；RPCS3 也可。
- 待改译文：`notes/text_fixes_todo.txt`。

## 还没做

1. 补写 262 行 PS3 独有台词（自己写粤文，需过目）。
2. 外传「雪が解け、そして雪が降るまで」（ASS: The Snow Melts 01–03 → 脚本 5000 系列）。
3. CC 以后的部分（没有现成字幕）。
4. 1.01 PKG：`PARAM.SFO` 的 APP_VER 设 01.01 或更高；补丁改用 1.01 的 EBOOT 做（先跑 `decrypt_101.bat`）。
5. 开场视频（mv01 等）烧录字幕。

## 使用（Windows）

`windows/` 里的文件放进补丁文件夹 `cantonese_patch\`（与游戏文件夹 `WHITE ALBUM2 [BLJM60571]` 同级），再放入构建出来的 `EBOOT.elf`、`02309.elzma`、`02309.size`。

1. `run_undo_patch.bat` → `run_apply_patch.bat`：把新字库追加进 `data.dar`（第 2309 项），并把 `EBOOT.elf` 装成游戏文件夹的 `EBOOT.BIN`（RPCS3 用）。
2. `make_ps3_eboot.bat`：用 scetool 签成 NPDRM UEXEC（key-revision 01、FREE），输出 `ps3_npdrm_v3\update_patched\EBOOT.BIN`，放到 PS3 的 `/dev_hdd0/game/BLJM60571/USRDIR/`。
3. EBOOT 和 data.dar 必须是同一次构建，否则字会错位。

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
python3 build.py out        # 提取日文脚本 → 对齐 → 过滤 → 生成 → 校验
```

输出 `out/EBOOT.elf`、`out/02309.elzma`、`out/02309.size`，拷到 `cantonese_patch\` 后按上面「使用」走。
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
