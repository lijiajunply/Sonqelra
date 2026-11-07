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

导出使用每四分音符 480 tick，不能精确表示的时间会报错。最多支持 15 条旋律音轨，通道 10 留给打击乐；同一音轨中相同音高的重叠音符以及力度为 0 的音符目前不能导出。导入 MIDI 也有信息损失，例如控制器和踏板不会转换。
