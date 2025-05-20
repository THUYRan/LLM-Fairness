import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from scipy import stats
import pandas as pd
import numpy as np
from datetime import datetime

def process_excel(file_path, output_path):
    df = pd.read_excel(file_path)

    # 计算距离2025年1月31日的天数
    end_date = datetime(2025, 1, 31)
    df['Days from Release (01/31/25)'] = df['Release Date'].apply(lambda x: (end_date - pd.to_datetime(x)).days)

    # 对Parameter Size取对数
    df['Parameter Size (Logged)'] = np.log(df['Parameter Size'])

    # 保存到新的Excel文件
    df.to_excel(output_path+"overall.xlsx", index=False)
    print(f'Processed file saved at: {output_path}overall.xlsx')
    return df

# 示例调用
# process_excel(r'C:\path\to\input.xlsx', r'C:\path\to\output.xlsx')

plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['grid.color'] = '#e0e0e0'
plt.rcParams['axes.grid'] = True
plt.rcParams['axes.facecolor'] = '#f9f9f9'

def linear_regression_from_csv(file_path, x_col, y_col, save_path, p_x=0.05, p_y=0.9, xlabel=None, ylabel=None):
    df = process_excel(file_path,r"C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\")
    #print("DataFrame列名：", df.columns.tolist())
    if y_col=="Parameter Size (Logged)":
        df = df.dropna(subset=['Parameter Size (Logged)'])
    print(x_col)
    print(df[x_col])
    X = df[x_col].values.reshape(-1, 1)
    Y = df[y_col].values

    model = LinearRegression()
    model.fit(X, Y)
    Y_pred = model.predict(X)

    slope, intercept, r_value, p_value, std_err = stats.linregress(X.flatten(), Y)

    print(f'Slope: {slope}')
    print(f'Intercept: {intercept}')
    print(f'Standard Error: {std_err}')
    print(f'R² Score: {r_value ** 2}')
    print(f'P-value: {p_value}')

    plt.figure(figsize=(7, 5))
    plt.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.1)
    plt.grid(True, linestyle='--', linewidth=0.6, zorder=-1)
    plt.scatter(X, Y, color='#4a90e2', s=70, edgecolor='black', zorder=2)
    plt.plot(X, Y_pred, color='#e94e77', linewidth=2.5, zorder=3)
    plt.xlabel(xlabel if xlabel else x_col)
    plt.ylabel(ylabel if ylabel else y_col)
    plt.text(p_x, p_y, f'p-value = {p_value:.3f}', transform=plt.gca().transAxes, fontsize=16, color='black',
             bbox=dict(facecolor='white', alpha=0.6, edgecolor='gray'))
    plt.savefig(save_path, dpi=500, bbox_inches='tight')
    plt.show()
    #plt.close()


def combine_plots(image_paths, output_path):
    fig, axes = plt.subplots( int(len(image_paths)/2), 2, figsize=(14, 10))
    axes = axes.flatten()
    for idx, img_path in enumerate(image_paths):
        img = plt.imread(img_path)
        axes[idx].imshow(img)
        axes[idx].axis('off')  # 显示坐标轴
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()


linear_regression_from_csv(r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\总表.xlsx',
                           'Bias Number', 'Inconsistency',
                           r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_inconsistency.png',
                           p_x=0.6, p_y=0.6)

linear_regression_from_csv(r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\总表.xlsx',
                           'Bias Number', 'Unfair Inaccuracy Number',
                           r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_inaccuracy.png',
                           p_x=0.7, p_y=0.3)


linear_regression_from_csv(r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\总表.xlsx',
                           'Bias Number', 'Weighted Average MAE',
                           r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_mae.png',
                           p_x=0.6, p_y=0.6)

linear_regression_from_csv(r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\总表.xlsx',
                           'Bias Number', 'Weighted Average MAPE',
                           r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_mape.png',
                           p_x=0.6, p_y=0.6)

linear_regression_from_csv(r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\总表.xlsx',
                           'Bias Number', 'Days from Release (01/31/25)',
                           r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_days.png',
                           p_x=0.6, p_y=0.6)

linear_regression_from_csv(r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\总表.xlsx',
                           'Bias Number', 'Parameter Size (Logged)',
                           r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_size.png',
                           p_x=0.6, p_y=0.6)


combine_plots([
    r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_inconsistency.png',
    r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_inaccuracy.png',
    r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_mae.png',
    r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_mape.png'
], r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\combined_plots.png')

combine_plots([
    r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_days.png',
    r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\bias_size.png'
], r'C:\\Users\\Motick\\OneDrive\\论文\\law ethics\\新汇总表 (2)\\combined_plots2.png')
