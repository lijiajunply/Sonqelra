# Sonqelra

Sonqelra 用 Python 组合音符、休止符和多轨作品，并导出 MIDI 和 MusicXML。

项目原名 Muse。升级时请将 Python 导入 `muse`、`muse_lang` 分别改为 `sonqelra`、`sonqelra_lang`，并将相关 API 名称中的 `muse` 改为 `sonqelra`。语言源文件扩展名由 `.muse` 改为 `.sonqelra`；VS Code 设置 `muse.pythonPath` 也改为 `sonqelra.pythonPath`。旧名称不再提供兼容入口。

## 安装与运行

需要 Python 3.11 或更高版本。在项目目录中运行：

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e . pytest
python examples/multitrack.py
python -m pytest -q
```

示例生成 `multitrack.mid`，可用支持 MIDI 的播放器或数字音频工作站打开；实际音色取决于播放器使用的音源。示例包含钢琴旋律、小提琴和弦及休止符。

## 时间与 MIDI

时间以四分音符为 1，八分音符为 `Fraction(1, 2)`；速度以每分钟四分音符数表示。乐器使用 General MIDI 名称，例如 `Piano` 或 `Violin`。

`Track` 的 `controls` 可以包含 `ControlChange(start, control, value)` 和 `PitchBend(start, pitch)`，分别表示控制器（包括 64 号延音踏板）和弯音；`is_percussion=True` 将轨道输出到 MIDI 通道 10。导入时按原通道将控制事件分配给相应轨道。速度可使用 `Fraction` 表示非整数 BPM，导入时精确保留 MIDI 的微秒速度值。导出会写入 General MIDI 乐器程序号。

导出使用每四分音符 480 tick，不能精确表示的时间会报错。最多支持 15 条旋律音轨；打击乐轨道共用通道 10，必须使用相同的程序号。同一音轨中相同音高的重叠音符以及力度为 0 的音符目前不能导出。导入支持 MIDI type 0 和 1 的四分音符时间格式，不支持 type 2 和 SMPTE。并非所有 MIDI 数据都会转换，例如触后、系统专属消息、音符释放力度和其他元数据会丢失；同一通道分配到多个乐器轨道时，控制事件会复制到这些轨道。

### MusicXML 导出 API

将已有的 `Score` 导出为 MusicXML 文件，可用 MuseScore 等记谱软件打开：

```python
from sonqelra.backends import sonqelra_to_musicxml
from sonqelra.core import N, Score, Track

score = Score((Track(N("C4", 1) + N("D4", 1), "Piano", "旋律"),), "示例")
sonqelra_to_musicxml(score, "example.musicxml")
```

也可以先用 `midi_to_sonqelra("input.mid")` 导入 MIDI，再将结果传给 `sonqelra_to_musicxml`。导出支持多轨、重叠声部、休止、跨小节连音、速度和拍号变化，使用精确时值。拍号变化必须位于小节边界，否则会报错。乐谱默认使用高音谱号；打击乐按有音高音符记谱。音符力度、MIDI 控制器和弯音不会写入 MusicXML，复杂时值会以连音时值表示。

### Sonqelra 语言

Sonqelra 源文件可编译为现有的 `Score`，编译阶段不会写文件。显式执行导出计划时，相对路径以指定目录为基准：

```python
from pathlib import Path
from sonqelra_lang import compile_source, execute_exports

path = Path("examples/asdf.sonqelra")
result = compile_source(path.read_text(encoding="utf-8"), filename=str(path))
score = result.scores[0].score
execute_exports(result, base_dir=path.parent)
```

在文件顶层导入模块，在作品中按需引用函数或轨道：

```sonqelra
import sonqelra "parts/guitar.sonqelra"
import midi "melody.mid"

score "组合" {
    track "Guitar" {
        instrument "Distortion Guitar"
        play module("guitar")."Electric Road".fn.power_chord(E3, B3)
    }
    track "Melody" {
        instrument "Piano"
        play module("melody")."melody".track."原轨道名"
    }
}
```

模块名是文件名（不含扩展名），作品和轨道按原名称查找。MIDI 的作品名为文件名（不含扩展名）；MusicXML 使用作品标题，没有标题时使用文件名。MIDI 和 MusicXML 不含 Sonqelra 函数，可以通过 `.track."轨道名"` 取得 `Music`；此操作取出音乐片段，当前 `track` 的乐器及打击乐设置由当前代码指定，不带入原轨道的控制器。

同一文件中可以定义多个作品。在后面的作品内用 `import score "作品名"` 注册前面定义的作品，然后使用 `score("作品名").fn.函数名(...)` 或 `score("作品名").track."轨道名"`。导入只注册引用，不会自动增加轨道；模块在编译时读取，导入脚本的导出计划不会执行。脚本函数保留其声明时的作用域。路径相对于包含导入语句的源文件；从字符串编译相对路径时须传入 `filename`。支持嵌套导入和循环依赖检测，同名模块或模块内同名作品会报错。

MusicXML 导入支持未压缩的 `score-partwise` 文件，包含音符、休止、和弦、多声部、连音和 MIDI 乐器；力度默认为 80。暂不支持装饰音、微分音和无音高打击乐音符，反复记号、歌词及其他记谱信息不会转换。Python 代码也可以使用 `musicxml_to_sonqelra(path)` 读取 MusicXML。

在 Sonqelra 源文件的 `score` 内可以直接声明导出格式：

```sonqelra
export midi "output.mid"
export musicxml "output.musicxml"
```

运行 `python -m sonqelra_lang examples/asdf.sonqelra` 执行导出；相对路径以源文件所在目录为基准。编译不会写文件。除内置的 `midi` 和 `musicxml` 外，Python 调用方可在执行时注入其他导出器：

```python
def export_custom(score, path):
    ...  # 将 score 写入 path

execute_exports(result, base_dir=path.parent, exporters={"custom": export_custom})
```

这样源文件即可使用 `export custom "output.ext"`。注入的同名导出器会覆盖内置实现；未知格式在写入任何文件前报错。语言语法和语义见 [Sonqelra 语言设计](docs/sonqelra-lang-design.md)。

### VS Code 扩展

仓库中的 [Sonqelra Language 扩展](vscode-sonqelra/README.md) 支持 `.sonqelra` 语法高亮和运行编译及导出命令。安装方法及 Python 解释器设置见扩展说明。
