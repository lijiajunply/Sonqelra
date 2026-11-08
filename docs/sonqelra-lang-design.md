# Sonqelra 语言设计

## 目标

Sonqelra 以乐谱为中心组织旋律、变奏、音轨和导出。第一版支持下面的写法，并以 [`examples/asdf.sonqelra`](../examples/asdf.sonqelra) 的完整翻译作为另一项验收目标：

```sonqelra
score "First Composition" {
    tempo 120
    meter 4/4
    key C major

    melody theme {
        C4:1/4
        D4:1/4
        E4:1/4
        G4:1/4
    }

    let variation = theme
        |> transpose(7)
        |> repeat(2)

    track piano {
        instrument "Acoustic Grand Piano"
        play theme + variation
    }

    export midi "output.mid"
    export musicxml "output.musicxml"
}
```

还支持在函数或乐谱作用域中构造音高数组：

```sonqelra
let pattern = [root, root + 4st, root + 7st, root + 12st]

// 同时演奏：和弦
let harmony = chord(pattern, duration: 1/2)

// 依次演奏：琶音
let arpeggio = sequence(pattern, duration: 1/8)
```

语言实现位于 `src/sonqelra_lang`。

## 乐谱与音符

`score "标题" { ... }` 定义一个作品。`tempo` 是每分钟四分音符数；`meter` 表示拍号；`key C major` 表示 C 大调，第一版支持自然音、升降号和 `major`、`minor`，只作为调性标记，不自动移调或改变音高拼写。速度、拍号和调性均最多声明一次；省略时分别使用 120、4/4 和无调性标记。

`melody 名称 { ... }` 将其中的音符和休止符按书写顺序串接，绑定为一个 `Music` 片段。空旋律非法。基本记法为 `音高:时值` 和 `rest:时值`：

```sonqelra
melody phrase {
    C4:1/4           // 四分音符，默认力度 80
    F#4:1/8@105      // 八分音符，力度 105
    rest:3/8         // 附点四分休止
}
```

冒号后的分数是**全音符的比例**，因此 `1/4` 是一个四分音符。现有核心 API 以四分音符为 1，编译时乘以 4：`C4:1/4` 映射为 `N("C4", 1, 80)`，`rest:3/8` 映射为 `Rest(Fraction(3, 2))`。分子、分母必须为正整数；记法允许任意正分数，MIDI tick 精度限制由后端在导出时检查。`@` 后是 0–127 的整数力度，仅适用于音符；省略时为 80。导出 MIDI 时，当前后端不接受力度 0。

音高使用科学音高记法，例如 `C4`、`F#2`、`Bb3`、`C##4`、`A-1`。音高不会受 `key` 自动改写。旋律体每行一个元素，不隐式填满小节，也不按拍号切分或校验小节长度。

`track piano` 中的 `piano` 是标识符，也是默认的轨道名称 `"piano"`。需要保留空格和大小写时可写 `track "Lead Guitar"`。音轨内必须恰有一个 `instrument "..."` 和一个 `play 表达式`；可选 `percussion true`，默认为 `false`。乐器名使用现有 General MIDI 名称。`play theme + variation` 将 `+` 两侧的音乐片段串接；`|` 将音乐片段并行叠加，总时长取最长者。

`export midi "output.mid"` 和 `export musicxml "output.musicxml"` 绑定到所在乐谱，生成包含格式名和路径的导出计划。多个导出语句可以出现在同一乐谱；无导出语句时仍可获得 `Score`。编译本身不写文件，单独执行导出计划。格式名为标识符；运行时通过导出器表解析，未知格式会在写入任何文件前报错。Python 调用方可通过 `execute_exports(..., exporters={"格式名": 导出函数})` 扩展或覆盖导出器，函数签名为 `(score, path)`。

## 表达式与作用域

- `let` 创建不可变绑定；乐谱内声明在当前乐谱作用域可见，函数参数及函数体中的 `let` 在函数局部作用域可见。名字按源码顺序先声明后使用，同一作用域不允许重复声明；局部名字可以遮蔽外层用户名字，但不能遮蔽内置名称。
- 支持顶层 `fn` 声明与乐谱内的 `fn` 声明，函数由参数、返回类型、零个或多个局部 `let` 和一个 `return` 组成。调用按位置传参。函数捕获声明时可见的外层绑定，不支持递归和前向引用。
- 类型包括 `Pitch`、`Music`、`Int`、`Number`、`Interval` 和 `List<Pitch>`。`Int` 可用于 `Number`；数组元素均须为 `Pitch`，第一版不支持空数组和其他元素类型。类型注解用于函数参数与返回值，`let` 推断类型。
- `4st` 是 4 个半音的 `Interval`；支持负数，如 `-7st`。`Pitch + Interval` 返回按半音移调的新 `Pitch`，映射至 `Pitch.transpose`；非零移调默认使用升号拼写。`Music + Music` 才表示串接；不支持数字加法或数组加法。
- 数组 `[root, root + 4st, ...]` 表示不可变的非空音高列表。列表自身不会产生声音，也不会隐式转换为音乐；可以通过 `chord` 或 `sequence` 显式转换。
- `chord(pattern, duration: 1/2)` 将音高列表中的各音符同时开始演奏；`sequence(pattern, duration: 1/8)` 按列表顺序依次演奏。两者都返回 `Music`，`duration` 是**每个音符**的时值，按全音符比例解释，与 `C4:1/4` 一致：`1/2` 对应两个四分音符，`1/8` 对应半个四分音符。时值必须为正的精确数值。每个音符默认力度为 80，可通过 `velocity: 100` 指定 0–127 的整数力度。`chord` 总时长为单个音符时值；`sequence` 总时长为单个音符时值乘以音符数量。MIDI 后端不允许同一轨道中同音高重叠，因此含重复音高的和弦可能无法导出。
- 这两个内置函数均要求第一个参数为 `List<Pitch>`，`duration` 必须使用具名参数，`velocity` 是可选具名参数，例如 `sequence(pattern, duration: 1/8, velocity: 100)`。具名参数顺序不限，但必须位于位置参数之后；不允许重复或未知的参数名。第一版其他内置函数与用户函数仍只接受位置参数。
- `music |> transpose(7)` 等价于 `transpose(music, 7)`，映射至 `Music.transpose(7)`，整数单位为半音；`music |> repeat(2)` 映射至 `music.repeat(2)`，次数必须为非负整数。第一版管道只支持这两个内置函数。
- 现有样例中需要可计算的音符与复用函数，因此还提供 `note(pitch, beats, velocity)` 和 `rest(beats)`：它们的时值直接使用核心 API 的**四分音符单位**，与冒号后乐谱记法不同；`velocity` 可省略，默认 80。例如 `note(C4, 1/2, 110)` 对应 `C4:1/8@110`。普通数值分数是精确有理数，分母不能为零。函数调用与管道可使用这些表达式。

## 与现有 API 的边界

| 语言概念 | 映射 |
| --- | --- |
| 乐谱标题、音轨 | `Score(title=..., tracks=...)` |
| `tempo 120` | `TempoMap(tempo=((Fraction(0), 120),))` |
| `meter 4/4` | `MeterMap(meter=((Fraction(0), TimeSignature(4, 4)),))`；不能先约分，否则会丢失拍号原样 |
| `key C major` | 暂存在编译结果的乐谱元数据中；当前 `Score` 和 MIDI 后端没有调性字段，不会写入 MIDI |
| 音符/休止记法 | `Note`/`Rest`，时值按全音符比例乘 4 转为 `Fraction` |
| 旋律串接、并行、重复、移调 | `Music.__add__`、`Music.__or__`、`Music.repeat`、`Music.transpose` |
| `chord` / `sequence` | 对每个音高构造相同时值和力度的 `Note`，分别用 `Parallel` / `Sequence` 组合 |
| 音轨与打击乐 | `Track(name=..., instrument=..., music=..., is_percussion=...)` |
| 导出 | 按格式名将对应 `Score` 交给导出器；内置 MIDI 和 MusicXML |

调性元数据保留在编译结果中，不能默认为已经存在于 `Score` 或导出文件。若以后要让 MIDI 保存调性，应先扩展核心模型和后端，再明确增量兼容行为。音频合成、外部命令、控制器、弯音和速度/拍号变化不在第一版语言范围。

## 前端结构

```text
源码 → lexer → tokens → parser → AST → compiler → 编译结果 → 通过导出器表执行导出
```

- `lexer.py`：词法分析，识别关键字、标识符、音高、数字、`st` 音程、字符串、注释和运算符，给 token 附源位置。
- `ast.py`：定义不可变 AST 和 `Span`，不依赖核心音乐对象。`MeterLiteral` 保留原始分子和分母；`NoteLiteral` 保留谱面时值；数组和管道保留源码结构。
- `parser.py`：构造 AST，不求值或写文件；保留乐谱及轨道内字段顺序，便于发现重复声明。
- `compiler.py`：检查名称、类型及约束，求值并构造核心对象；读取导入模块并生成导出计划，不使用 Python `eval`。
- `__init__.py`：公开 `compile_source(source, *, filename="<string>")` 与结果和错误类型。CLI 读取源码并显式执行导出。

`CompilationResult` 按源顺序保存作品结果和导出计划。每个作品结果包含 `score: Score` 和可选的调性元数据；每条导出计划关联对应作品、路径及源范围。`execute_exports(result, *, base_dir)` 以 `base_dir` 解析相对路径，绝对路径按原样处理；重复输出目标在写入前报错。CLI 以源文件所在目录作为 `base_dir`。多个文件导出不是事务性的，失败时可能已有部分输出。

## 词法与语法规则

源码为 UTF-8；标识符以 ASCII 字母或 `_` 开头，后接 ASCII 字母、数字或 `_`，区分大小写。完整匹配音高格式的单词保留为音高；`e5` 是标识符，`E5` 是音高。`//` 开始行注释；`#` 是音高中的升号。单引号与双引号字符串支持 `\\`、`\"`、`\n`、`\r` 和 `\t`。`|>` 和 `->` 按最长匹配识别。

换行通常结束语句；圆括号和方括号内部的换行忽略。表达式后紧接以 `|>` 开头的行是管道续行，即使不在括号内；续行后表达式的其他部分仍须遵循括号规则。花括号不抑制换行。每条旋律元素占一行。允许空行，最后一条语句可在 `}` 或 EOF 前直接结束。

主要产生式（`NL` 为有效换行，`end` 为 `NL` 或紧接 `}`/EOF）：

```ebnf
program      = NL* (top_stmt NL*)* EOF ;
top_stmt     = fn_decl | score_decl | import_file ;
score_decl   = "score" STRING "{" NL* (score_item NL*)* "}" end ;
score_item   = tempo | meter | key | melody | let_stmt | fn_decl | track | export | import_score ;
import_file  = "import" ("midi" | "musicxml" | "sonqelra") STRING end ;
import_score = "import" "score" STRING end ;
tempo        = "tempo" expr end ;
meter        = "meter" INT "/" INT end ;
key          = "key" KEY_ROOT ("major" | "minor") end ;
melody       = "melody" IDENT "{" NL* (melody_item NL*)+ "}" end ;
melody_item  = (PITCH | "rest") ":" INT "/" INT ("@" INT)? end ;
track        = "track" (IDENT | STRING) "{" NL* (track_item NL*)* "}" end ;
track_item   = "instrument" STRING end | "percussion" BOOL end | "play" expr end ;
export       = "export" IDENT STRING end ;
let_stmt     = "let" IDENT "=" expr end ;
fn_decl      = "fn" IDENT "(" params? ")" "->" type "{" NL*
               (let_stmt NL*)* "return" expr end NL* "}" end ;
params       = param ("," param)* ;
param        = IDENT ":" type ;
type         = "Pitch" | "Music" | "Int" | "Number" | "Interval" | "List" "<" "Pitch" ">" ;
expr         = pipeline ;
pipeline     = parallel ("|>" IDENT "(" args? ")")* ;
parallel     = addition ("|" addition)* ;
addition     = primary ("+" primary)* ;
primary      = PITCH | number | INTERVAL | IDENT | call | list | qualified | "(" expr ")" ;
qualified    = ("module" "(" STRING ")" "." STRING | "score" "(" STRING ")")
               "." ("fn" "." IDENT "(" args? ")" | "track" "." STRING) ;
call         = IDENT "(" args? ")" ;
list         = "[" expr ("," expr)* ","? "]" ;
args         = arg ("," arg)* ;
arg          = (IDENT ":")? expr ;
number       = "-"? INT ("/" INT)? ;
```

`KEY_ROOT` 是无八度的 `A`–`G` 加可选连续同向 `#` 或 `b`；`INTERVAL` 是有符号整数紧接 `st`。`@` 只能用于音符，不能用于 `rest`；这项约束在语义检查中执行。函数调用支持位置参数及上述限定的具名参数，参数顺序和重名约束在语义检查中执行；调用参数不支持末尾逗号，列表允许末尾逗号。运算优先级从高到低为调用、`+`、`|`、`|>`，均左结合。表达式操作数与函数参数按类型检查；普通数值不提供加减乘除运算，`/` 只构成有理数字面量。

## 校验、诊断与验收

所有 token 和 AST 节点携带文件名与 1 起始的行列范围，结束位置为开区间。统一 `SonqelraError`，区分词法、语法、语义和导出错误；错误包含源范围和可选底层原因。第一版遇到首个错误即停止。底层无效音高、非法拍号、未知乐器、无效力度或导出失败均转成带相应源位置的错误。MIDI 后端的重叠同音、力度 0 和 tick 精度等限制在导出阶段报告。乐谱至少包含一条音轨，标题和轨道名非空；每条音轨必须有一个合法乐器和一个 `Music` 类型的 `play`。

建议实现顺序：先实现 lexer/AST/parser 与多行管道，再实现作用域、精确时值换算和核心对象构造，最后实现显式导出及 CLI。将 `sonqelra_lang` 加入 `pyproject.toml` 的 wheel 包列表。测试应覆盖本文首个示例、数组与音程、`chord` 的同时起音和 `sequence` 的依次起音、具名参数及其错误、`4/4` 不被约分、重复字段及错误位置。`asdf.sonqelra` 应与 `asdf.py` 按轨道比较名称、乐器、打击乐标志、速度/拍号、总时长和排序后的全部音符事件；在临时目录验证导出 MIDI 可读取，并确认单独编译不产生文件。FluidSynth 和 WAV 渲染不属于语言验收。

## 导入

文件顶层使用 `import midi "path.mid"`、`import musicxml "path.musicxml"` 或 `import sonqelra "path.sonqelra"` 注册模块，不自动加入轨道。模块名为文件名去除扩展名；模块中的作品按标题区分。同名模块或模块内重复标题报错。使用 `module("模块名")."作品名".fn.函数名(参数)` 调用脚本作品定义的函数，或 `module("模块名")."作品名".track."轨道名"` 获取轨道的 `Music`。MIDI 作品名使用文件名；MusicXML 使用作品标题或文件名。MIDI 和 MusicXML 不包含语言函数。获取轨道音乐时不会带入乐器和控制事件。

`score` 中的 `import score "作品名"` 注册本文件中此前定义的作品，使用 `score("作品名").fn.函数名(参数)` 或 `score("作品名").track."轨道名"` 引用。作品必须唯一，不能前向引用，且导入不会自动增加轨道。函数保留其定义时的闭包，按声明顺序可见。

每个路径相对于包含它的源文件；嵌套脚本按各自路径解析，循环导入报错。模块在编译时读取，脚本的导出计划不会执行。MusicXML 支持未压缩的 partwise 格式，具体限制见 README。
