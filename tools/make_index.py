"""Offline index of everything the patch shows, to find where a save is and what to test.
   python tools/make_index.py            -> work/index.html  (open in a browser; contains the full script, keep it local)
Reads the build in work/build (what is actually in the game), the Japanese scripts and the alignment data."""
import os, sys, re, json, struct, pickle, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths, common as c, wa2_eboot3 as w
BS = "\\"
B = os.path.join(paths.WORK, "build")

# ---- decode the built scripts (codes -> characters) ----
tb = c.font_table(open(c.ELF, "rb").read())
code2ch = {x: c.code2char(x) for x in tb if x >> 8 >= 0x81 and c.code2char(x)}
cc = 0xF043
for ch in open(os.path.join(B, "new_glyphs.txt"), encoding="utf-8").read():
    while (cc & 0xFF) < 0x40 or (cc & 0xFF) in (0x5C, 0x7F): cc += 1
    code2ch[cc] = ch; cc += 1
elf = open(os.path.join(B, "EBOOT.elf"), "rb").read()
BUILT = {n[:-4]: w.elzma_decompress(elf[d:d + bs], u).split(b",") for _, n, d, u, bs in w.entries(elf) if n.endswith(".txt")}
def dec(b):
    s = []; i = 0
    while i < len(b):
        x = b[i]
        if x < 0x80: s.append(chr(x)); i += 1
        else: s.append(code2ch.get(struct.unpack(">H", b[i:i + 2])[0], "?")); i += 2
    return "".join(s)
def jp(name): return [x.decode("cp932", "replace") for x in open(os.path.join(paths.JP_DIR, name + ".txt"), "rb").read().split(b",")]
def plain(s): return re.sub(r"<R([^|]*)\|[^>]*>", r"\1", re.sub(r"<[WSF]\d*([^>]*)>", r"\1", s)).replace(BS + "k", "")

def breaks(s):                       # line-break positions counted in letters only (ignores punctuation width changes)
    out, k = [], 0
    for ch in s:
        if ch == "\n": out.append(k)
        elif ch.isalnum(): k += 1
    return out
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_yue3.py"), encoding="utf-8").read()
_a = _src.index("MANUAL = {") + len("MANUAL = "); _d = 0
for _b in range(_a, len(_src)):                       # end of the dict literal: match braces
    _d += {"{": 1, "}": -1}.get(_src[_b], 0)
    if _d == 0: break
MANUAL = eval(_src[_a:_b + 1])
_bp = os.path.join(paths.WORK, "pc_bridge.pkl")
BRIDGE = pickle.load(open(_bp, "rb")) if os.path.exists(_bp) else {}
G, res = pickle.load(open(paths.ALIGN_PKL, "rb"))
_, TMAP, _, _ = pickle.load(open(paths.MAP_PKL, "rb"))
ep = {}
for f, r in res.items():
    k = int(re.search(r"(\d\d)\.ass$", f).group(1))
    for a, g in r["pairs"]:
        if g is not None and a is not None: ep[g] = k
rows = []; last = 1; JPC = {}
for gi, (n, i, t) in enumerate(G):
    if re.search(r"\.\w{3}$", t): continue                  # file names (images/animations), never shown
    last = ep.get(gi, last)
    if n not in JPC: JPC[n] = jp(n)
    y = dec(BUILT[n][i]) if n in BUILT else JPC[n][i]
    sub = TMAP.get(n, {}).get(i)
    flags = []; yy = plain(y).replace(BS + "n", "\n")
    if y == JPC[n][i] and re.search(r"[぀-ヿ]", y): flags.append("jp")   # still Japanese
    if re.search(r"[A-Za-z]", yy) and "jp" not in flags: flags.append("en")
    if i in MANUAL.get(n, {}): flags.append("fix")              # hand-fixed in build_yue3.MANUAL
    elif i in BRIDGE.get(n, {}): flags.append("pc")             # recovered through the PC script
    elif sub is not None and breaks(yy) != breaks(sub): flags.append("wrap")
    spk = ""
    prev = JPC[n][i - 1] if i else ""
    if 0 < len(prev) <= 12 and t.startswith(("「", "（", "『")) and not prev.startswith(("「", "（", "『", "<")):
        spk = dec(BUILT[n][i - 1]) if n in BUILT else prev
        if spk != prev and "＆" in prev or "・" in prev: flags.append("name")
    rows.append(dict(r="IC", ch="第%d集" % last, s=n, f=i, sp=spk, y=plain(y).replace(BS + "n", "\n").strip(),
                     j=plain(t).replace(BS + "n", "\n").strip(), fl=flags))
ic_n = len(rows)
# side story: one row per paragraph
chap = ""
for n in "5000 5001 5002 5003 5004".split():
    J = jp(n)
    for i, x in enumerate(J):
        if not (re.search(r"[぀-ヿ一-鿿]", x) and not re.search(r"\.\w{3}$", x)): continue
        ys = dec(BUILT[n][i]).split(BS + "k") if n in BUILT else x.split(BS + "k")
        for si, part in enumerate(x.split(BS + "k")):
            jt = plain(part).replace(BS + "n", "").strip("　 ")
            if not jt: continue
            yt = plain(ys[si]).replace(BS + "n", "").strip("　 ") if si < len(ys) else ""
            m_ = re.match(r"(序章|第.章|終章)", jt)
            if m_: chap = {"序章": "序章", "終章": "終章"}.get(m_.group(1), m_.group(1))
            fl = ["jp"] if yt == jt and re.search(r"[぀-ヿ]", jt) else []
            if m_: fl.append("head")
            if re.search(r"[A-Za-z]", yt) and "jp" not in fl: fl.append("en")
            rows.append(dict(r="外传", ch=chap, s=n, f=i, p=si, sp="", y=yt, j=jt, fl=fl))
for route in ("IC", "外传"):
    rs = [r for r in rows if r["r"] == route]
    for k, r in enumerate(rs): r["pc"] = round(100 * k / max(1, len(rs) - 1), 1)
print("rows", len(rows), "IC", ic_n, "side", len(rows) - ic_n)

PAGE = r"""<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WA2 粤化索引</title>
<style>
:root{--bg:#f6f7f9;--fg:#1d2329;--mut:#66707a;--card:#fff;--line:#dfe3e8;--acc:#2f6fdf;--hl:#fff2a8;--chip:#eef1f5}
@media (prefers-color-scheme:dark){:root{--bg:#14181c;--fg:#e6e9ec;--mut:#9aa4ae;--card:#1c2228;--line:#2c343c;--acc:#7aa7ff;--hl:#5a4d12;--chip:#252d35}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,"Microsoft JhengHei","PingFang TC",sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px;z-index:2}
h1{font-size:17px;margin:0 0 8px}input{width:100%;padding:10px 12px;font-size:16px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
.tabs{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}.tabs button{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:5px 10px;border-radius:999px;cursor:pointer;font-size:13px}
.tabs button.on{background:var(--acc);color:#fff;border-color:var(--acc)}main{padding:12px 16px;max-width:980px;margin:0 auto}
.r{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:8px;cursor:pointer}
.meta{font-size:12px;color:var(--mut);display:flex;gap:8px;flex-wrap:wrap;align-items:center}.pc{font-weight:700;color:var(--acc);font-size:14px}
.y{white-space:pre-wrap;margin-top:4px}.j{white-space:pre-wrap;color:var(--mut);font-size:13px;margin-top:2px}
.chip{background:var(--chip);border-radius:4px;padding:0 6px}mark{background:var(--hl);color:inherit}.ctx{border-left:3px solid var(--acc);margin:6px 0 10px 8px;padding-left:10px}
.ctx .r{cursor:default}.ctx .cur{outline:2px solid var(--acc)}.note{color:var(--mut);font-size:13px;margin:6px 0}
.bar{height:6px;background:var(--chip);border-radius:3px;overflow:hidden;width:120px;display:inline-block;vertical-align:middle}.bar i{display:block;height:100%;background:var(--acc)}
</style>
<header><h1>WA2 粤化索引 · 搜索你在游戏里看到的字，知道读到哪里</h1>
<input id="q" placeholder="输入几个字（粤文/日文/英文都可以），例如 timing、計、Billboard" autofocus>
<div class="tabs" id="tabs"></div></header><main id="out"></main>
<script>
const R=__DATA__;
const TABS=[["s","搜索"],["wrap","重新断行"],["fix","手动修正"],["pc","PC版找回"],["en","含英文"],["name","合称人名"],["jp","仍是日文"],["head","外传章节开头"]];
const LBL={pc:"PC桥接",wrap:"重新断行",fix:"手动修正",en:"英文",name:"人名",jp:"日文",head:"章节"};
let tab="s";const $=s=>document.querySelector(s);
$("#tabs").innerHTML=TABS.map(t=>`<button data-t="${t[0]}">${t[1]}</button>`).join("");
document.querySelectorAll("#tabs button").forEach(b=>b.onclick=()=>{tab=b.dataset.t;draw()});
const esc=s=>s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function hl(s,q){s=esc(s);if(!q)return s;const i=s.toLowerCase().indexOf(esc(q).toLowerCase());return i<0?s:s.slice(0,i)+"<mark>"+s.slice(i,i+q.length)+"</mark>"+s.slice(i+q.length)}
function card(r,k,q,cls=""){return `<div class="r ${cls}" data-k="${k}"><div class="meta"><span class="pc">${r.r} ${r.pc}%</span><span class="bar"><i style="width:${r.pc}%"></i></span><span>${r.ch}</span><span>${r.s} #${r.f}${r.p!=null?"."+r.p:""}</span>${r.fl.map(f=>`<span class="chip">${LBL[f]||f}</span>`).join("")}</div>${r.sp?`<div class="meta">${esc(r.sp)}</div>`:""}<div class="y">${hl(r.y,q)}</div><div class="j">${hl(r.j,q)}</div></div>`}
function draw(){document.querySelectorAll("#tabs button").forEach(b=>b.classList.toggle("on",b.dataset.t==tab));
 const q=$("#q").value.trim();let L=[];
 if(tab=="s"){if(!q){$("#out").innerHTML=`<p class="note">共 ${R.length} 句（IC ${R.filter(r=>r.r=="IC").length}，外传 ${R.filter(r=>r.r!="IC").length} 段）。在上面输入几个字开始搜索；点结果可展开前后文。</p>`;return}
  const ql=q.toLowerCase();R.forEach((r,k)=>{if((r.y+"\n"+r.j+"\n"+r.sp).toLowerCase().includes(ql))L.push(k)})}
 else R.forEach((r,k)=>{if(r.fl.includes(tab)&&(!q||(r.y+r.j).toLowerCase().includes(q.toLowerCase())))L.push(k)});
 $("#out").innerHTML=`<p class="note">${L.length} 条${L.length>300?"，只显示前 300 条":""}，按游戏顺序排列</p>`+L.slice(0,300).map(k=>card(R[k],k,q)).join("");
 document.querySelectorAll("#out > .r").forEach(e=>e.onclick=()=>ctx(e,+e.dataset.k,q))}
function ctx(e,k,q){if(e.nextElementSibling&&e.nextElementSibling.classList.contains("ctx")){e.nextElementSibling.remove();return}
 const d=document.createElement("div");d.className="ctx";let h="";for(let i=Math.max(0,k-4);i<=Math.min(R.length-1,k+4);i++)if(R[i].r==R[k].r)h+=card(R[i],i,i==k?q:"",i==k?"cur":"");d.innerHTML=h;e.after(d)}
let t0;$("#q").oninput=()=>{clearTimeout(t0);t0=setTimeout(draw,150)};draw();
</script></html>"""
out = os.path.join(paths.WORK, "index.html")
open(out, "w", encoding="utf-8").write(PAGE.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":"))))
print(out, os.path.getsize(out) // 1024, "KB")
