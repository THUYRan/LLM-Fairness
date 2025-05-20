#!/usr/bin/env python
# coding: utf-8

# In[19]:


import pandas as pd
import json
import os

# File paths
assessor_folder = r"D:\bias model\gpt4o\gpt4o"
changed_id_file = r"D:\bias model\gpt4o\changedID_触发词版ID_list.json"
data_file = r"D:\bias model\gpt4o\有触发词数据集.xlsx"
output_folder = r"D:\bias model\gpt4o\merged"

def clean_response(response):
    """清理response中的所有空格"""
    return json.loads(json.dumps(response).replace(" ", ""))

# Load the changed ID data
with open(changed_id_file, 'r', encoding='utf-8') as f:
    changed_id_list = json.load(f)
changed_id_df = pd.DataFrame({'ID': range(len(changed_id_list)), 'LEEC_ID': changed_id_list})

# Load the dataset
data_df = pd.read_excel(data_file)
data_df.rename(columns={'ID': 'LEEC_ID'}, inplace=True)

# Process each JSON file in the assessor folder
for file_name in os.listdir(assessor_folder):
    if file_name.endswith('.json'):
        # Load and process the assessor data
        with open(os.path.join(assessor_folder, file_name), 'r', encoding='utf-8') as f:
            assessor_df = pd.DataFrame(json.load(f))
            
        # Clean response column
        assessor_df['response'] = assessor_df['response'].apply(clean_response)
        
        # Expand response column
        if 'response' in assessor_df.columns:
            response_expanded = assessor_df['response'].apply(pd.Series)
            response_expanded = response_expanded.add_prefix('llm_')
            assessor_df = pd.concat([assessor_df.drop(columns=['response']), response_expanded], axis=1)
        
        # Merge datasets
        merged_df = assessor_df.merge(changed_id_df, on='ID', how='left').merge(data_df, on='LEEC_ID', how='left')
        
        # Remove empty llm columns
        llm_columns = [col for col in merged_df.columns if col.startswith('llm_')]
        #empty_llm_columns = [col for col in llm_columns if merged_df[col].apply(lambda x: pd.isna(x) or str(x).strip() == '').all()]
        empty_llm_columns = []
        for col in llm_columns:
           if merged_df[col].isna().all() or merged_df[col].astype(str).str.strip().eq('').all():
            empty_llm_columns.append(col)
        
        if empty_llm_columns:
            print(f"\n删除的空列: {empty_llm_columns}")
            merged_df = merged_df.drop(columns=empty_llm_columns)
            
        # Save results
        output_path = os.path.join(output_folder, f"merged_{os.path.splitext(file_name)[0]}.xlsx")
        merged_df.to_excel(output_path, index=False)
        print(f"保存文件: {output_path}")


# In[ ]:




