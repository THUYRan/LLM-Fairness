import pandas as pd
import re
import os
import math


def escape_latex_special_characters(text):
    """
    Escapes special LaTeX characters in the given text.
    """
    special_chars = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde",
        "^": r"\^",
        "\\": r"\textbackslash"
    }
    return re.sub(r'([&%$#_{}~^\\])', lambda match: special_chars[match.group(0)], text)


def csv_to_latex_chunked(csv_file, output_file=None, rows_per_table=20):
    """
    读取单个 CSV 文件，根据给定的行数(rows_per_table)拆分并输出到同一个 LaTeX 文件中。

    Parameters:
    - csv_file: CSV 文件的路径
    - output_file: 输出的 LaTeX 文件路径（可选，不传则返回字符串）
    - rows_per_table: 每张表所含的最大行数
    """
    # 读取CSV文件
    df = pd.read_csv(csv_file)

    # 获取列名
    column_names = df.columns.tolist()

    # 计算需要多少个 chunk
    total_rows = len(df)
    num_chunks = math.ceil(total_rows / rows_per_table)

    # 准备存放所有表格的 LaTeX 代码
    latex_code = ""

    # 遍历每一个 chunk
    for chunk_idx in range(num_chunks):
        # 当前chunk的起止行
        start_index = chunk_idx * rows_per_table
        end_index = min((chunk_idx + 1) * rows_per_table, total_rows)

        # 取出对应的子 DataFrame
        df_chunk = df.iloc[start_index:end_index]

        # =============== 生成单个表格的 LaTeX 代码 ===============

        # 1) 开始一个新的 sidewaystable 环境
        latex_code += "\\begin{sidewaystable}\n\\centering\n"
        latex_code += "\\resizebox{\\textwidth}{!}{\n"

        # 2) 表格列格式，假设所有列都是左对齐
        latex_code += "\\begin{tabular}{" + " ".join(["l"] * len(column_names)) + "}\n"
        latex_code += "\\hline\n"

        # 3) 表头
        header_line = " & ".join([escape_latex_special_characters(col) for col in column_names])
        latex_code += header_line + " \\\\ \n"
        latex_code += "\\hline\n"

        # 4) 表格内容（每行）
        for index, row in df_chunk.iterrows():
            row_line = " & ".join([escape_latex_special_characters(str(cell)) for cell in row])
            latex_code += row_line + " \\\\ \n"

        # 加一条横线
        latex_code += "\\hline\n"

        # 5) 结束 tabular、结束 resizebox
        latex_code += "\\end{tabular}\n"
        latex_code += "}\n"

        # 6) 标题、结束当前 sidewaystable
        latex_code += f"\\caption{{Table Part {chunk_idx + 1} (rows {start_index + 1}-{end_index})}}\n"
        latex_code += "\\end{sidewaystable}\n\n"
        # =============== 单个表格结束 ===============

    # 如果不指定输出文件，则直接返回 latex_code
    if not output_file:
        return latex_code

    # 写出到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(latex_code)

    print(f"Overleaf LaTeX table code has been written to {output_file}")


def convert_csvs_in_folder_chunked(folder_path, output_folder=None, rows_per_table=20):
    """
    将指定文件夹下所有 CSV 文件，按照每 rows_per_table 行分割成多张表并生成 LaTeX 代码。
    默认输出到同名 _output.tex 文件（可指定输出文件夹）。

    Parameters:
    - folder_path: 包含 CSV 文件的文件夹路径
    - output_folder: 输出的 LaTeX 文件夹路径（可选）。若不指定，则在原CSV同级目录下生成。
    - rows_per_table: 每张表的最大行数
    """
    csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

    for csv_file in csv_files:
        csv_file_path = os.path.join(folder_path, csv_file)

        if output_folder:
            output_file_path = os.path.join(output_folder, os.path.splitext(csv_file)[0] + '_output.tex')
        else:
            output_file_path = os.path.splitext(csv_file_path)[0] + '_output.tex'

        csv_to_latex_chunked(csv_file_path, output_file_path, rows_per_table=rows_per_table)


# 示例用法
if __name__ == "__main__":
    folder_path = r"C:\Users\86158\Desktop\新汇总表"  # 放置 CSV 文件的文件夹
    output_folder = r"C:\Users\86158\Desktop\新汇总overleaf"  # 输出 LaTeX 文件夹
    rows_per_table = 20  # 每 20 行拆分成一张表，按需调整

    convert_csvs_in_folder_chunked(folder_path, output_folder, rows_per_table)
