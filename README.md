# README

## 项目简介
本项目包含两个可调用函数：
1. **调用 API 处理数据** - `modify_and_run`
2. **调用 Stata 进行数据分析** - `main`

## 环境要求

本项目需要安装以下依赖库：

### Stata 依赖

本项目需本地安装Stata18，并在 Stata 中安装必要的工具包：

```stata
ssc install reghdfe
ssc install ftools
```

### Python 依赖

此项目依赖以下 Python 库

- stata_setup（用于与 Stata 交互）

  部署pystata请参考官方文档（https://www.stata.com/python/pystata18/notebook/Magic%20Commands1.html）

- pandas（用于数据处理）

- numpy（用于数值计算）

- scipy.stats.binom（用于统计计算）

## 使用示例

### 1. 调用 API 处理数据 (`modify_and_run`)
#### 输入参数格式
- `file_path` (str): 需要修改的 Python 文件路径。
- `new_values` (dict): 需要修改的配置信息，包括：
  - `OPENROUTER_API_KEY` (str)
  - `MODEL_NAME` (str)
  - `API_URL` (str)
  - `providers` (list[str])
  - `output_dir` (str)

#### 调用示例
```python
file_path = "/Users/yuki/Desktop/batch/DeepSeek_R1_Example.py"

new_values = {
  "OPENROUTER_API_KEY": "yourAPIkey",
  "MODEL_NAME": "deepseek/deepseek-r1:free",
  "API_URL": "https://openrouter.ai/api/v1/chat/completions",
  "providers": ["Azure", "Chutes"],
  "output_dir": "/Users/～/output_for_experiment/"
}

modify_and_run(file_path, new_values)
```

调用LLMs得到的判决预测会保存在输入的`output_dir`路径中。

### 2. 调用 Stata 进行数据分析 (`main`)

#### 输入参数格式

- `model` (str): 需要处理的模型名称。
- `path_base` (str): 本地数据集的基础路径。
- `json_path` (str): 标签信息文件路径。
- `output_dir` (str): 结果输出目录。

#### 调用示例

```python
path_base = r"/Users/～/law_ethnics"
json_path = r"/Users/～/params.json"
output_dir = r"/Users/～/output"
model = "NOVALite"

json_Consistency, json_main_p0_1, json_main_P_N, json_inaccuracy_p0_1, json_inaccuracy_P_N, df_dict = main(model, path_base, json_path, output_dir)
```

### 输出格式

- `json_Consistency` ：Part I：Consistency Analysis表格相关json数据

- `json_main_p0_1` ：Part II：Bias Analysis 显著性<0.1的标签表格数据

- `json_main_P_N` ：Part II：Bias Analysis 存在显著偏误的标签具体分类结果表格数据

- `json_inaccuracy_p0_1` ：Part III：Unfair Inaccuracy Analysis 显著性<0.1的标签表格数据

- `json_inaccuracy_P_N` ：Part III：Unfair Inaccuracy Analysis 存在显著偏误的标签具体分类结果表格数据

- `df_dict` ：文字部分需要的数据（json）

  示例

  ```json
  [
      {
          "model": "llama3_1",  //模型名
          "main_p0_1value": 2.1403870629445287e-14,  //Part II：来源于系统性偏差的概率
          "inaccuracy_p0_1value": 2.1403870629445287e-14,  //part III：来源于系统性偏差的概率
          "main_p0_05value": 2.7161306139462403e-17,
          "inaccuracy_p0_05value": 2.7161306139462403e-17,
          "main_p0_01value": 3.812785434269691e-22,
          "inaccuracy_p0_01value": 3.812785434269691e-22,
          "avg_valid_id_ratio": 0.1743215495253777,  //平均每个标签xx%的样本存在不一致性。
          "avg_mae": 61.44939024123505,  //加权平均MAE
          "avg_mape": 142.9436988284994,  //加权平均MAPE 
          "main_total_biased_labels": 31,  //Part II：xx个标签存在显著偏误
          "inaccuracy_total_biased_labels": 21  //Part III：xx个标签存在显著偏误
      }
  ]
  ```
  

stata分析的log文件保存在`path_base/model/log`。

stata分析的图片保存在`path_base/model/figure`。

模型运行得到的分析结果会以csv和json格式保存在`output_dir`中。

- Bias_Analysis_P.csv：主回归显著性<0.1的标签表格
- Bias_Analysis_Pnum.csv：主回归存在显著偏误的标签具体分类结果表格
- crime_clustered_P.csv：罪名聚类的稳健标准误显著性<0.1的标签表格
- crime_clustered_Pnum.csv：罪名聚类的稳健标准误存在显著偏误的标签具体分类结果表格
- df_dict.json：加权平均MAE、MAPE，样本有效率等整体性分析结果
- inaccuracy_p.csv：inaccuracy显著性<0.1的标签表格
- inaccuracy_results_Pnum.csv：inaccuracy存在显著偏误的标签具体分类结果表格
- original_main_P.csv：原始主回归显著性<0.1的标签表格
- original_main_Pnum.csv：原始主回归存在显著偏误的标签具体分类结果表格
- output_Consistency.csv：Consistency Analysis表格
- post_2014_P.csv：post_2014显著性<0.1的标签表格
- post_2014_Pnum.csv：post_2014 存在显著偏误的标签具体分类结果表格
- result.json：stata分析导出的原始数据
- results_special_P.csv：特殊罪名回归显著性<0.1的标签表格
- results_special_Pnum.csv：特殊罪名回归存在显著偏误的标签具体分类结果表格
- robust_standard_errors_P.csv：稳健标准误显著性<0.1的标签表格
- robust_standard_errors_Pnum.csv：稳健标准误存在显著偏误的标签具体分类结果表格
- robustness_lgxq_llm_full_P.csv：robustness_lgxq_llm_full显著性<0.1的标签表格
- robustness_lgxq_llm_full_Pnum.csv：robustness_lgxq_llm_full 存在显著偏误的标签具体分类结果表格
