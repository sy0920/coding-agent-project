# 演示：基于文件的问答（未指定文件名时主动检索）

真实 API（deepseek-chat）跑通记录，用于视频素材与答辩佐证。

## 任务

> 请统计工作区里数据文件中的数字，计算平均值和中位数

（注意：任务中**没有**出现文件名，agent 需自行定位数据文件。）

## 工作区内容

- `numbers.txt`：内容为 `12 / 7 / 23 / 5 / 19`
- `hello.py`：无关文件

## agent 的工具调用链（关键步骤）

```
▶ list_directory {}                 ← 先看工作区有哪些文件
▶ read_file numbers.txt             ← 定位并读取数据文件
▶ read_file hello.py                ← 确认没有遗漏其他数据
▶ run_command "python3 -c ..."      ← 尝试计算（python3 在 Windows 不存在）
▶ run_command "python numbers.txt"  ← 报错，换思路
▶ run_command "where python ..."    ← 定位可用解释器
▶ run_command "D:\python\python.exe -c ..."  ← 找到正确的 python，算完
✓ finish                            ← 汇报结果
```

## 最终结果（正确）

- 平均值：**13.2**（12+7+23+5+19=66，÷5）
- 中位数：**12**（排序 5,7,12,19,23）

## 佐证的两点能力

1. **主动检索**：未指定文件名时，模型按系统提示词第 2 条走「list_directory → read_file」。
2. **自纠正**：`python3` 不存在时报错，模型把报错回填、换思路，最终定位到 `python` 并跑通——这正是「工具异常反馈给模型自纠正」的循环在真实场景下的表现。
