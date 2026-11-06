# Kindle 本地文本处理脚本

这是一组 macOS 命令行脚本。流程为截图、Vision OCR、清理、分块、人工或外部翻译、合并、PDF。项目没有自动翻译入口，也没有 Node 依赖或依赖锁文件。

## 分块与合并

需要 Python 3.9 或以上，只使用标准库。下面的命令应在本目录执行。

```sh
# 按页标记分成最多四块；没有页标记时保留完整正文为一块。
python3 chunk-md.py --work output/my-book

# 按目标词数分块。单页不拆开，所以一块可能超过目标词数。
python3 chunk-noid.py --work output/my-book --target 11000

# 将翻译文件放在同一工作目录的 chunks-zh/ 后合并。
python3 merge-zh.py --work output/my-book
```

输入文件为工作目录中的 `clean.md`。两个分块脚本输出 `chunks/chunk-01.md` 等文件。它们是两种可选分块方式，不需要依次执行。合并脚本读取 `chunks-zh/chunk-01.md` 等文件，按数字排序，输出 `clean-zh.md`。

三个 Python 脚本都支持环境变量 `WORK`，命令行 `--work` 优先。`chunk-noid.py` 也支持 `TARGET`，命令行 `--target` 优先。无参数时，`chunk-md.py` 和 `merge-zh.py` 使用脚本所在目录下的 `output/half-second`；`chunk-noid.py` 使用 `output/no-one-did-it`。

分块脚本会覆盖同名分块。如果新分块数量少于旧分块数量，脚本会先报错，避免残留块被误合并。需要重新分块时，先备份旧结果，或使用新的工作目录。合并脚本在检查成功后覆盖 `clean-zh.md`，运行前应备份原译文。

合并要求编号从 1 开始且连续，正文不能为空。如果 `chunks/` 存在，源文与译文块数必须相同。译文保留的 `chunk: 1/N` 或 `<!-- chunk 1/N | ... -->` 头也会接受检查。请保留源分块或这些头：两者都缺失时，程序无法判断最后几块是否遗漏。合并不会删除重复的正文行。重新合并时保留原 `clean-zh.md` 的 YAML 元数据，包括手写标题、副标题、作者和自定义字段，仅刷新 `translated_chars` 与 `translated_at`；未闭合的元数据会阻止覆盖。首次合并时标题默认为工作目录名；`half-second` 使用原有书名。作者、原文字数和翻译模型不由程序猜测。

## 其他脚本与限制

- `auto-capture.sh [--resume] <页数> [书名] [间隔秒数]` 控制 Chrome 翻页并截取整个屏幕，需要屏幕录制和辅助功能权限。页数必须为正整数，间隔为非负整数秒。运行前应将对应书页置于前台。激活或翻页失败会立即停止，成功后接着调用 OCR。默认拒绝已有截图的目录；如需重新截图，使用新的书名目录。
- 显式续跑时将 `--resume` 放在页数前，例如 `./auto-capture.sh --resume 320 my-book 6`。运行前必须将 Kindle 定位到本次截图序列的第 1 页，保持原来的窗口与排版设置；页数填写总页数（示例为 320），不是剩余页数。脚本从第 1 页开始，保留并跳过已有的 `page_0001.png` 等截图，只补截缺失页；跳过截图时仍会翻到下一页，最后一页不翻页。脚本不会自动定位书页或校验现有截图是否对应当前排版。
- `ocr-pages.sh [书名]` 使用 Swift 与 macOS Vision；`ocr-smart.sh [书名] [语言]` 使用已有的 `livetext_ocr_smart` 可执行文件。更改 Swift 源码后需要手动重新编译该可执行文件。
- `clean-md.sh` 为《半秒》定制；`clean-noid.sh` 为《No One Did It》定制。清理规则会删除指定行或页，不能直接视为适用于所有书籍。
- `build-pdf.sh [书名]` 需要 `pandoc`、`xelatex` 和指定的 macOS 字体；PDF 标题和作者来自 `clean-zh.md` 的 YAML 元数据。渲染失败或生成空文件时保留旧 PDF。
- OCR 脚本需要 Python 3 生成转义正确的元数据。没有图片、页文件名不合法、识别失败或识别为空白时返回失败，不覆盖旧 `full.md` 和 `manifest.json`。所有页面通过后才替换输出；这两个文件依次替换，中途断电仍可能导致二者不同步。空白页也需人工确认，脚本不会自动跳过。
- 四个截图、OCR、PDF shell 入口的书名参数必须是单个目录名，支持中文、空格和引号，拒绝路径与换行。OCR 的 `manifest.json` 中 `full_md_path` 为相对该清单所在目录的 `full.md`，不再写入本机绝对路径。

## 本地验证

```sh
python3 -B -m unittest discover -s tests -v
for f in *.sh; do bash -n "$f" || exit; done
shellcheck *.sh
```

测试只使用临时目录中的合成文字，并给子进程设置隔离的 `HOME` 与环境变量。截图、AppleScript、OCR 和 PDF 渲染命令全部用模拟命令替代。测试覆盖元数据保留、识别失败保护、默认拒绝已有截图、显式续跑跳过截图并继续翻页、翻页失败停止、路径拒绝与 PDF 失败保护，不读取现有书稿、不启动浏览器、不调用 OCR、翻译服务或其他付费 API。真实截图顺序、双栏 OCR 阅读顺序、翻译质量和 PDF 排版需要另外验收。
