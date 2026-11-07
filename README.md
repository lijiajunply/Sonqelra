# Muse

Muse 用 Python 组合音符、休止符和多轨作品，并导出 MIDI。

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
