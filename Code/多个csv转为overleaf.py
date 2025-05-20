import pandas as pd
import re
import os

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

def csv_to_latex(csv_file, output_file=None):
    """
    Converts a CSV file into LaTeX table format and writes it to the output file.
    
    Parameters:
    - csv_file: The path to the CSV file.
    - output_file: The path to the output LaTeX file (optional).
    """
    # 读取CSV文件
    df = pd.read_csv(csv_file)
    
    # 获取列名
    column_names = df.columns.tolist()
    
    # 生成表格的LaTeX代码
    latex_code = "\\begin{sidewaystable}\n\\centering\n"  # 使用 sidewaystable 让表格横向
    
    latex_code += "\\resizebox{\\textwidth}{!}{\n"  # 设置纵向的自适应
    latex_code += "\\begin{tabular}{" + " ".join(["l"] * len(column_names)) + "}\n"
    
    # 加载booktabs包
    latex_code += "\\hline\n"
    
    # 添加列名作为表头
    latex_code += " & ".join([escape_latex_special_characters(col) for col in column_names]) + " \\\\ \n"
    
    latex_code += "\\hline\n"
    
    # 添加每一行的数据
    for index, row in df.iterrows():
        latex_code += " & ".join([escape_latex_special_characters(str(cell)) for cell in row]) + " \\\\ \n"
    
    latex_code += "\\hline\n"
    
    # 结束LaTeX表格环境
    latex_code += "\\end{tabular}\n"
    
    # 结束自动缩放
    latex_code += "}\n"
    
    latex_code += "\\caption{Table Caption}\n\\end{sidewaystable}"

    # 如果没有指定输出文件路径，则返回 LaTeX 代码
    if output_file:
        with open(output_file, 'w') as f:
            f.write(latex_code)
        print(f"Overleaf LaTeX table code has been written to {output_file}")
    else:
        return latex_code

def convert_csvs_in_folder(folder_path, output_folder=None):
    """
    Converts all CSV files in the specified folder to LaTeX code.

    Parameters:
    - folder_path: The path to the folder containing CSV files.
    - output_folder: The folder where the output LaTeX files will be saved (optional).
    """
    # 获取文件夹中的所有CSV文件
    csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    
    # 遍历每个CSV文件进行转换
    for csv_file in csv_files:
        csv_file_path = os.path.join(folder_path, csv_file)
        
        # 如果没有指定输出文件夹，则使用原始文件名作为输出文件名
        if output_folder:
            output_file_path = os.path.join(output_folder, os.path.splitext(csv_file)[0] + '_output.tex')
        else:
            output_file_path = os.path.splitext(csv_file_path)[0] + '_output.tex'
        
        # 将CSV文件转换为LaTeX表格
        csv_to_latex(csv_file_path, output_file_path)

# 使用示例
folder_path = r"C:\Users\86158\Desktop\新汇总表"  # 你的CSV文件夹路径
output_folder = r"C:\Users\86158\Desktop\新汇总overleaf"  # 输出的LaTeX文件夹路径

# 转换文件夹中的所有CSV文件
convert_csvs_in_folder(folder_path, output_folder)
