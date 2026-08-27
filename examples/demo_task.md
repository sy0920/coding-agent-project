# 演示任务（可直接复制作为命令参数）

## 任务 1：统计数字（推荐，短小适合视频）

在 examples/demo 目录中，data.txt 每行是一个整数。请写一个 Python 程序 stats.py，
读取 data.txt，输出这些数字的个数、平均值、中位数、最大值、最小值；再写一个
test_stats.py 用 unittest 验证结果，并运行测试确保通过。

运行：

```bash
python -m coding_agent "在 examples/demo 目录中，data.txt 每行是一个整数。请写一个 Python 程序 stats.py 读取 data.txt，输出个数、平均值、中位数、最大值、最小值；再写 test_stats.py 用 unittest 验证，并运行测试确保通过。" --workspace examples/demo --verbose
```

## 任务 2：修 bug

写一个「判断闰年」的函数，故意留一个逻辑错误，让 agent 通过测试发现并修复它。

## 任务 3：文件处理

读取 data.txt，过滤掉小于 10 的数，把结果写入 filtered.txt，并打印处理前后的行数。

---

提示：演示前建议先 `pip install -r requirements.txt` 并配置好 `.env`；
用 `--verbose` 能清楚展示每一步工具调用，适合视频讲解。
