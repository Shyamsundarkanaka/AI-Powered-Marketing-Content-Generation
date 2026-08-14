"""Render docs/PROJECT_DOCUMENTATION.md into a styled, mobile-friendly HTML page.

Targeted Markdown converter — it handles exactly the constructs used in that
document (headings, tables, fenced code incl. mermaid, blockquotes, nested
lists, rules, inline code/bold/italic/links) rather than pulling in a
dependency. Edit the Markdown, then regenerate the page with:

    python docs/build_doc_html.py

Both paths default to this script's own directory; pass them explicitly to
render a different pair:

    python docs/build_doc_html.py <in.md> <out.html>
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

# --- inline -----------------------------------------------------------------

_CODE_TOKEN = "\x00CODE{}\x00"


def _inline(text: str) -> str:
    """Escape, then apply inline markdown. Code spans are pulled out first so
    their contents are never touched by the bold/italic/link passes."""
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(html.escape(match.group(1)))
        return _CODE_TOKEN.format(len(spans) - 1)

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Non-greedy so `**bold with *italic* inside**` pairs correctly; code spans
    # are already stashed, so a `**kwargs` in code can never be matched here.
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<em>\1</em>", text)

    for index, span in enumerate(spans):
        text = text.replace(_CODE_TOKEN.format(index), f"<code>{span}</code>")
    return text


def slug(text: str) -> str:
    """GitHub-compatible heading anchor."""
    text = re.sub(r"`", "", text).lower()
    text = re.sub(r"[^a-z0-9 \-]", "", text)
    return text.strip().replace(" ", "-")


# --- block ------------------------------------------------------------------

_PIPE = "\x01"


def _table(rows: list[str]) -> str:
    def cells(line: str) -> list[str]:
        line = line.replace(r"\|", _PIPE).strip()
        line = line.strip("|")
        return [c.strip().replace(_PIPE, "|") for c in line.split("|")]

    header = cells(rows[0])
    body = [cells(r) for r in rows[2:]]
    out = ['<div class="scroll-x"><table><thead><tr>']
    out += [f"<th>{_inline(c)}</th>" for c in header]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _list_block(lines: list[tuple[int, str, bool]]) -> str:
    """lines: (indent, text, ordered). Supports two levels."""
    out: list[str] = []
    stack: list[str] = []
    # Indents are relative to the block: a whole list written at 3 spaces (as the
    # sub-sequences in the rebuild guide are) is one flat level, not a nested one.
    base = min(indent for indent, _, _ in lines)

    for indent, text, ordered in lines:
        level = 1 if (indent - base) >= 2 else 0
        level = min(level, len(stack))  # never open a nested list with no parent
        tag = "ol" if ordered else "ul"
        while len(stack) > level + 1:
            out.append(f"</li></{stack.pop()}>")
        if len(stack) == level + 1:
            out.append("</li>")
        while len(stack) < level + 1:
            if stack:
                out.append("")  # nested list lives inside the open <li>
            out.append(f"<{tag}>")
            stack.append(tag)
        out.append(f"<li>{_inline(text)}")
    while stack:
        out.append(f"</li></{stack.pop()}>")
    return "".join(out)


def convert(md: str) -> tuple[str, list[tuple[str, str]]]:
    lines = md.split("\n")
    out: list[str] = []
    toc: list[tuple[str, str]] = []
    i = 0
    section_open = False

    while i < len(lines):
        line = lines[i]

        # fenced code / mermaid
        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            body = html.escape("\n".join(buf))
            if lang == "mermaid":
                out.append(f'<div class="scroll-x diagram"><pre class="mermaid">{body}</pre></div>')
            else:
                cls = f' class="lang-{lang}"' if lang else ""
                out.append(f'<div class="scroll-x"><pre><code{cls}>{body}</code></pre></div>')
            continue

        # headings
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            raw = heading.group(2).strip()
            anchor = slug(raw)
            if level == 2:
                if section_open:
                    out.append("</section>")
                out.append(f'<section id="{anchor}">')
                section_open = True
                number = re.match(r"^(\d+)\.\s+(.*)$", raw)
                if number:
                    toc.append((anchor, number.group(2)))
                    out.append(
                        '<div class="sec-head">'
                        f'<span class="sec-num">{number.group(1)}</span>'
                        f'<h2>{_inline(number.group(2))}</h2></div>'
                    )
                else:
                    out.append(f'<div class="sec-head plain"><h2>{_inline(raw)}</h2></div>')
            else:
                out.append(f'<h{level} id="{anchor}">{_inline(raw)}</h{level}>')
            i += 1
            continue

        # horizontal rule
        if re.match(r"^-{3,}\s*$", line):
            i += 1
            continue

        # table
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(
            r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]
        ):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            out.append(_table(block))
            continue

        # blockquote
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip())
                i += 1
            paras = "\n".join(buf).split("\n\n")
            inner = "".join(f"<p>{_inline(p.replace(chr(10), ' '))}</p>" for p in paras if p.strip())
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # list
        item = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if item:
            buf = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m:
                    buf.append((len(m.group(1)), m.group(3), m.group(2)[0].isdigit()))
                    i += 1
                elif lines[i].strip() and lines[i].startswith("   ") and buf:
                    indent, text, ordered = buf[-1]
                    buf[-1] = (indent, text + " " + lines[i].strip(), ordered)
                    i += 1
                else:
                    break
            out.append(_list_block(buf))
            continue

        # blank
        if not line.strip():
            i += 1
            continue

        # paragraph
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,4}\s|```|>|\s*([-*]|\d+\.)\s|-{3,}\s*$)", lines[i]
        ) and not lines[i].strip().startswith("|"):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{_inline(' '.join(buf))}</p>")

    if section_open:
        out.append("</section>")
    return "\n".join(out), toc


# --- page -------------------------------------------------------------------

STYLE = """
:root{
  /* Palette lifted from the project's own brand.yaml — the file this page documents. */
  --ink:#0B0E14; --surface:#151C28; --primary:#FF5A1F; --accent:#17E0C4;
  --paper:#F5F7FA; --muted-brand:#9AA7B8;

  --bg:#FBFCFD;
  --bg-raised:#FFFFFF;
  --bg-sunken:#F1F4F8;
  --fg:#10151E;
  --fg-soft:#4A566A;
  --fg-faint:#79879C;
  --rule:#DCE3EC;
  --rule-soft:#E9EEF4;
  --link:#D9430A;
  --code-fg:#0B6E63;
  --code-bg:#F1F4F8;
  --quote-bg:#F4F7FA;

  --display:"Bahnschrift","DIN Alternate","Segoe UI Variable Display","Segoe UI",
            system-ui,-apple-system,sans-serif;
  --body:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --mono:"Cascadia Code","Cascadia Mono","SF Mono","JetBrains Mono",
         ui-monospace,Consolas,"Liberation Mono",monospace;

  --measure:74ch;
  --rail:16.5rem;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0B0E14; --bg-raised:#151C28; --bg-sunken:#10151E;
    --fg:#EEF2F7; --fg-soft:#B4C0D0; --fg-faint:#8593A6;
    --rule:#243044; --rule-soft:#1B2534;
    --link:#FF7A45; --code-fg:#17E0C4; --code-bg:#151C28; --quote-bg:#121A26;
  }
}
:root[data-theme="dark"]{
  --bg:#0B0E14; --bg-raised:#151C28; --bg-sunken:#10151E;
  --fg:#EEF2F7; --fg-soft:#B4C0D0; --fg-faint:#8593A6;
  --rule:#243044; --rule-soft:#1B2534;
  --link:#FF7A45; --code-fg:#17E0C4; --code-bg:#151C28; --quote-bg:#121A26;
}
:root[data-theme="light"]{
  --bg:#FBFCFD; --bg-raised:#FFFFFF; --bg-sunken:#F1F4F8;
  --fg:#10151E; --fg-soft:#4A566A; --fg-faint:#79879C;
  --rule:#DCE3EC; --rule-soft:#E9EEF4;
  --link:#D9430A; --code-fg:#0B6E63; --code-bg:#F1F4F8; --quote-bg:#F4F7FA;
}

*{box-sizing:border-box;}
body{
  margin:0; background:var(--bg); color:var(--fg);
  font-family:var(--body); font-size:16px; line-height:1.65;
  -webkit-text-size-adjust:100%; overflow-x:hidden;
}

/* progress bar — an echo of the one media/movie.py draws into every video */
#progress{
  position:fixed; inset:0 auto auto 0; height:3px; width:0;
  background:var(--primary); z-index:60; transition:width .1s linear;
}
@media (prefers-reduced-motion: reduce){ #progress{transition:none;} }

.masthead{
  border-bottom:1px solid var(--rule);
  background:var(--bg-raised);
  padding:2.75rem 1.25rem 2rem;
}
.masthead-inner{max-width:calc(var(--rail) + var(--measure) + 6rem); margin:0 auto;}
.eyebrow{
  font-family:var(--mono); font-size:.7rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--accent); margin:0 0 .85rem;
  display:flex; flex-wrap:wrap; gap:.5rem .9rem;
}
.eyebrow span::before{content:"/ "; color:var(--fg-faint);}
.eyebrow span:first-child::before{content:none;}
h1{
  font-family:var(--display); font-weight:600; font-size:clamp(1.9rem,5.2vw,3.1rem);
  line-height:1.08; letter-spacing:-.015em; margin:0 0 .7rem; text-wrap:balance;
}
.standfirst{
  max-width:62ch; margin:0; color:var(--fg-soft);
  font-size:clamp(1rem,2.4vw,1.14rem); line-height:1.6;
}
.stats{
  display:flex; flex-wrap:wrap; gap:.5rem; margin:1.6rem 0 0; padding:0; list-style:none;
}
.stats li{
  font-family:var(--mono); font-size:.72rem; letter-spacing:.03em;
  border:1px solid var(--rule); border-radius:2px;
  padding:.32rem .6rem; color:var(--fg-soft); background:var(--bg);
  font-variant-numeric:tabular-nums;
}
.stats b{color:var(--fg); font-weight:600;}

.shell{
  max-width:calc(var(--rail) + var(--measure) + 6rem); margin:0 auto;
  display:grid; grid-template-columns:var(--rail) minmax(0,1fr);
  gap:3.5rem; padding:0 1.25rem 6rem; align-items:start;
}

nav.rail{position:sticky; top:1.5rem; padding-top:2.5rem;}
nav.rail h2{
  font-family:var(--mono); font-size:.68rem; letter-spacing:.15em;
  text-transform:uppercase; color:var(--fg-faint); margin:0 0 .9rem; font-weight:500;
}
nav.rail ol{list-style:none; margin:0; padding:0; counter-reset:s;
  display:flex; flex-direction:column; gap:.08rem;}
nav.rail a{
  display:grid; grid-template-columns:1.9rem 1fr; gap:.15rem; align-items:baseline;
  padding:.28rem .45rem; border-radius:2px; text-decoration:none;
  color:var(--fg-soft); font-size:.845rem; line-height:1.3;
  border-left:2px solid transparent;
}
nav.rail a::before{
  counter-increment:s; content:counter(s,decimal-leading-zero);
  font-family:var(--mono); font-size:.68rem; color:var(--fg-faint);
  font-variant-numeric:tabular-nums;
}
nav.rail a:hover{background:var(--bg-sunken); color:var(--fg);}
nav.rail a.active{
  color:var(--fg); border-left-color:var(--primary); background:var(--bg-sunken);
}
nav.rail a.active::before{color:var(--primary);}

.toc-mobile{display:none;}

main{min-width:0; padding-top:2.5rem;}

section{scroll-margin-top:1.5rem;}
.sec-head{
  margin:4rem 0 1.4rem; padding-top:1.6rem;
  border-top:1px solid var(--rule);
  display:grid; grid-template-columns:auto 1fr; gap:.85rem; align-items:baseline;
  position:relative;
}
.sec-head::before{
  content:""; position:absolute; top:-1px; left:0; width:3.5rem; height:2px;
  background:var(--accent);
}
section:first-of-type .sec-head{margin-top:0;}
.sec-num{
  font-family:var(--mono); font-size:.8rem; font-weight:600; color:var(--primary);
  font-variant-numeric:tabular-nums; letter-spacing:.02em;
}
.sec-head.plain{grid-template-columns:1fr;}
h2{
  font-family:var(--display); font-weight:600; font-size:clamp(1.35rem,3.4vw,1.72rem);
  line-height:1.18; letter-spacing:-.008em; margin:0; text-wrap:balance;
}
h3{
  font-family:var(--display); font-weight:600; font-size:1.16rem; line-height:1.3;
  margin:2.6rem 0 .7rem; letter-spacing:-.004em; text-wrap:balance;
}
h4{
  font-family:var(--mono); font-weight:600; font-size:.8rem; letter-spacing:.08em;
  text-transform:uppercase; color:var(--fg-soft); margin:2rem 0 .6rem;
}
p{margin:0 0 1.05rem; max-width:var(--measure);}
a{color:var(--link); text-underline-offset:.18em; text-decoration-thickness:1px;}
a:focus-visible, nav.rail a:focus-visible, summary:focus-visible{
  outline:2px solid var(--primary); outline-offset:2px; border-radius:2px;
}
strong{font-weight:650; color:var(--fg);}

ul,ol{margin:0 0 1.15rem; padding-left:1.35rem; max-width:var(--measure);}
li{margin:0 0 .38rem;}
li>ul, li>ol{margin:.4rem 0 .1rem;}
ul{list-style:none; padding-left:1.1rem;}
ul>li{position:relative;}
ul>li::before{
  content:""; position:absolute; left:-.95rem; top:.66em;
  width:5px; height:1px; background:var(--fg-faint);
}

code{
  font-family:var(--mono); font-size:.855em; color:var(--code-fg);
  background:var(--code-bg); padding:.1em .32em; border-radius:2px;
  word-break:break-word;
}
pre{
  margin:0; padding:1.05rem 1.15rem; background:var(--bg-sunken);
  border:1px solid var(--rule-soft); border-left:2px solid var(--accent);
  border-radius:2px; overflow-x:auto;
}
pre code{
  background:none; padding:0; color:var(--fg); font-size:.815rem; line-height:1.62;
  white-space:pre; word-break:normal;
}
.scroll-x{overflow-x:auto; max-width:100%; margin:0 0 1.5rem;
  -webkit-overflow-scrolling:touch;}
.diagram pre{
  border-left-color:var(--rule-soft); background:var(--bg-raised);
  padding:1.4rem .9rem; display:flex; justify-content:center;
}
.diagram svg{max-width:100%; height:auto;}

table{border-collapse:collapse; font-size:.86rem; min-width:100%;}
th,td{
  text-align:left; padding:.55rem .8rem; border-bottom:1px solid var(--rule-soft);
  vertical-align:top;
}
th{
  font-family:var(--mono); font-size:.7rem; letter-spacing:.07em;
  text-transform:uppercase; color:var(--fg-soft); font-weight:600;
  border-bottom:1px solid var(--rule); white-space:nowrap;
}
tbody tr:hover{background:var(--bg-sunken);}
td code{font-size:.8em;}

blockquote{
  margin:0 0 1.5rem; padding:.9rem 1.1rem; max-width:var(--measure);
  background:var(--quote-bg); border-left:2px solid var(--primary);
  border-radius:0 2px 2px 0; color:var(--fg-soft);
}
blockquote p{margin:0 0 .6rem;}
blockquote p:last-child{margin:0;}
blockquote strong{color:var(--fg);}

/* --- narrow screens ---------------------------------------------------- */
@media (max-width:999px){
  .shell{grid-template-columns:minmax(0,1fr); gap:0; padding:0 1.15rem 4rem;}
  nav.rail{display:none;}
  .toc-mobile{
    display:block; margin:1.75rem 0 0;
    border:1px solid var(--rule); border-radius:2px; background:var(--bg-raised);
  }
  .toc-mobile summary{
    cursor:pointer; padding:.85rem 1rem; font-family:var(--mono);
    font-size:.74rem; letter-spacing:.12em; text-transform:uppercase;
    color:var(--fg-soft); list-style:none;
  }
  .toc-mobile summary::-webkit-details-marker{display:none;}
  .toc-mobile summary::after{content:" +"; color:var(--primary);}
  .toc-mobile[open] summary::after{content:" \\2212"; }
  .toc-mobile ol{
    margin:0; padding:0 1rem 1rem; list-style:none; counter-reset:m;
    columns:2; column-gap:1.2rem;
  }
  .toc-mobile a{
    display:block; padding:.4rem 0; font-size:.82rem; line-height:1.35;
    text-decoration:none; color:var(--fg-soft); break-inside:avoid;
  }
  .toc-mobile a::before{
    counter-increment:m; content:counter(m) ". ";
    font-family:var(--mono); font-size:.7rem; color:var(--primary);
  }
  main{padding-top:1.5rem;}
  .masthead{padding:2rem 1.15rem 1.6rem;}
  .sec-head{margin-top:3rem;}
  pre code{font-size:.76rem;}
  table{font-size:.8rem;}
  th,td{padding:.5rem .6rem;}
}
@media (max-width:520px){
  body{font-size:15.5px;}
  .toc-mobile ol{columns:1;}
  .stats li{font-size:.68rem;}
  .sec-head{grid-template-columns:1fr; gap:.3rem;}
  th,td{padding:.45rem .5rem;}
}

footer{
  border-top:1px solid var(--rule); margin-top:4rem; padding:2rem 0 0;
  font-family:var(--mono); font-size:.74rem; color:var(--fg-faint);
  max-width:var(--measure);
}
"""

SCRIPT = """
(function(){
  var bar = document.getElementById('progress');
  var links = Array.prototype.slice.call(
    document.querySelectorAll('nav.rail a'));
  var sections = links.map(function(a){
    return document.getElementById(a.getAttribute('href').slice(1));
  });

  function onScroll(){
    var top = window.scrollY || document.documentElement.scrollTop;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = (max > 0 ? (top / max) * 100 : 0) + '%';

    var current = 0;
    for (var i = 0; i < sections.length; i++){
      if (sections[i] && sections[i].getBoundingClientRect().top <= 120) current = i;
    }
    for (var j = 0; j < links.length; j++){
      links[j].classList.toggle('active', j === current);
    }
  }
  var ticking = false;
  window.addEventListener('scroll', function(){
    if (!ticking){
      window.requestAnimationFrame(function(){ onScroll(); ticking = false; });
      ticking = true;
    }
  }, {passive:true});
  onScroll();

  var dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
    (!document.documentElement.getAttribute('data-theme') &&
     window.matchMedia('(prefers-color-scheme: dark)').matches);
  if (window.mermaid){
    window.mermaid.initialize({
      startOnLoad:true,
      theme: dark ? 'dark' : 'neutral',
      themeVariables:{
        fontFamily:'"Cascadia Code","SF Mono",ui-monospace,Consolas,monospace',
        fontSize:'13px',
        primaryColor: dark ? '#151C28' : '#F1F4F8',
        primaryTextColor: dark ? '#EEF2F7' : '#10151E',
        primaryBorderColor: dark ? '#243044' : '#DCE3EC',
        lineColor: dark ? '#8593A6' : '#79879C'
      }
    });
  }
})();
"""


def build(md_path: Path, out_path: Path) -> None:
    md = md_path.read_text(encoding="utf-8")

    # Strip the source document's own front matter + inline TOC; the page
    # carries those as a masthead and a navigation rail instead.
    start = md.index("\n## 1. What the system does")
    body_md = md[start:]

    body, toc = convert(body_md)

    rail = "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc)

    page = f"""<title>AI-Powered Marketing Content Generation — Technical Documentation</title>
<style>{STYLE}</style>

<div id="progress"></div>

<header class="masthead">
  <div class="masthead-inner">
    <p class="eyebrow"><span>Technical documentation</span><span>v1.0</span>
      <span>7 August 2026</span><span>branch: version2</span></p>
    <h1>AI-Powered Marketing Content Generation</h1>
    <p class="standfirst">A LangGraph multi-agent pipeline that turns one Shopify
      product URL into a complete, reviewable marketing package &mdash; campaign brief,
      voiceover script, caption, hashtags, narration and a rendered 1080&times;1920
      vertical video &mdash; behind a human approve/reject loop and strict
      anti-hallucination guarantees.</p>
    <ul class="stats">
      <li><b>~7,800</b> lines of Python</li>
      <li><b>9</b> pipeline nodes</li>
      <li><b>5</b> LLM agents</li>
      <li><b>6</b> database tables</li>
      <li><b>174</b> tests</li>
      <li><b>3</b> LLM providers</li>
    </ul>
    <details class="toc-mobile">
      <summary>Contents &mdash; 24 sections</summary>
      <ol>{rail}</ol>
    </details>
  </div>
</header>

<div class="shell">
  <nav class="rail" aria-label="Table of contents">
    <h2>Contents</h2>
    <ol>{rail}</ol>
  </nav>
  <main>
{body}
    <footer>
      Source of truth: <code>docs/PROJECT_DOCUMENTATION.md</code> &middot;
      Palette and typography taken from the project&rsquo;s own
      <code>brand/brand.yaml</code>.
    </footer>
  </main>
</div>

<script>{SCRIPT}</script>
"""
    # Escape every non-ASCII character as a numeric entity, so the rupee sign,
    # em dashes and the box-drawing art render correctly whatever charset the
    # host serves the page with.
    page = page.encode("ascii", "xmlcharrefreplace").decode("ascii")
    out_path.write_text(page, encoding="ascii")
    print(f"Wrote {out_path} ({len(page):,} bytes, {len(toc)} sections)")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "PROJECT_DOCUMENTATION.md"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "PROJECT_DOCUMENTATION.html"
    build(source, target)
