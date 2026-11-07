# Muse Language for VS Code

为 `.muse` 文件提供语法高亮、括号配对、行注释和编译命令。

## 安装

1. 安装 Python 3.11+，并在用于编译的 Python 环境中安装 Muse 项目：在仓库根目录执行 `python -m pip install -e .`。
2. 使用 Node.js 和 VS Code 扩展打包工具，在本目录执行 `npx @vscode/vsce package`，然后在 VS Code 扩展视图的 `...` 菜单中选择“从 VSIX 安装”，选中生成的 `.vsix`。也可以在本目录按 F5 启动扩展开发宿主进行调试。
3. 设置 `muse.pythonPath` 为安装了 Muse 的 Python 可执行文件路径。默认值为 `python3`；例如在 macOS/Linux 上可使用仓库中 `.venv/bin/python` 的绝对路径，Windows 则使用 `.venv\\Scripts\\python.exe` 的绝对路径。

## 使用

打开 `.muse` 文件，在编辑器标题栏点击编译按钮，或通过命令面板运行 **Muse: Compile and Export**。扩展先保存修改，再在终端运行 `python -m muse_lang`；源码内的 `export` 声明会实际写入文件，相对导出路径以源文件所在目录为基准。同名目标可能被覆盖。带源位置的错误会显示在“问题”面板。没有 `export` 声明时只检查并编译，不会产生输出文件。

编译器和依赖需要单独安装，扩展本身不包含 Python 运行时或 Muse 编译器。
