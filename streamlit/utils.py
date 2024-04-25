import streamlit as st
import pandas as pd
from collections import defaultdict
import re
import json
import ast
import geopandas as gpd
import io
import os
import pydeck as pdk
import plotly.express as px
from datetime import datetime
import glob

def clean_and_split(industries):
    if isinstance(industries, list):
        return [industry.strip("[]' ") for industry in industries]
    elif isinstance(industries, str):
        clean_str = industries.strip("[]' ")
        return clean_str
    else:
        return industries

def format_description(descriptions):
    if descriptions:
        bullet_point = "•"
        return "\n".join(f"{bullet_point} {desc}" for desc in descriptions.split(','))
    else:
        return ""

def calculate_fill_color(count, max_count):
    return [
        255 - 52 * count / max_count,
        191 - 167 * count / max_count,
        0 + 29 * count / max_count
    ]

def rewrite_date(date_str):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    ordinal = lambda n: "%d%s" % (n, "th" if 4 <= n <= 20 or 24 <= n <= 30 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))
    formatted_date = date_obj.strftime(f"{ordinal(date_obj.day)} %B %Y")
    return formatted_date

def clean_and_split_str(industries_str):
    clean_str = industries_str.strip("[]' ")
    if clean_str != 'None':
        return [item.strip() for item in clean_str.split("', '")]
    else:
        return None

def clean_risk_df(vis_df):
    vis_df['Industry'] = vis_df['Industry'].apply(clean_and_split_str)
    vis_df = vis_df[vis_df['Risk Description'].notna() & vis_df['Risk Impact'].astype(str).apply(lambda x: x.strip("[]' ") != '') & vis_df["Pass"]]
    vis_df = vis_df.drop('Pass', axis=1).reset_index(drop=True)
    return vis_df

def standardize_country_names(countries):
    standardized_countries = []
    for country in countries:
        if country in ['UK', 'United Kingdom', 'Great Britain', 'England', 'Wales', 'Scotland', 'Ireland', 'global', 'La Serra', 'European', 'Europe', 'European Union' ]:
            pass
        elif country == 'USA' or country == 'United States' or country == 'US':
            standardized_countries.append('United States of America')
        elif country == 'Czech Republic':
            standardized_countries.append('Czechia')
        elif country == 'Republic of Cyprus':
            standardized_countries.append('Cyprus')
        elif country == 'Gaza':
            standardized_countries.append('Palestine')
        else:
            standardized_countries.append(country)
    return standardized_countries

def get_risk_count_countries(df):
    df['Risk Countries'] = df['Risk Countries'].apply(ast.literal_eval)
    df['Risk Countries'] = df['Risk Countries'].apply(standardize_country_names)
    df = df.explode('Risk Countries').reset_index(drop=True)
    risk_counts = df.groupby(['Risk Countries', 'Risk Type']).size().reset_index(name='Count')
    risk_counts_pivot = risk_counts.pivot_table(index='Risk Countries', columns='Risk Type', values='Count', fill_value=0).reset_index()
    for col in risk_counts_pivot.columns[1:]:  # Exclude the 'Risk Countries' column
        risk_counts_pivot[col] = risk_counts_pivot[col].astype(int)
    risk_counts_pivot['Total Count'] = risk_counts_pivot.iloc[:, 1:].sum(axis=1)
    risk_counts_pivot['Risk Descriptions'] = risk_counts_pivot.apply(lambda row: ", ".join([f"{col} ({row[col]})" for col in risk_counts_pivot.columns[1:-1] if row[col] > 0]), axis=1)
    final_df = risk_counts_pivot[['Risk Countries', 'Risk Descriptions', 'Total Count']]
    return final_df

def get_risk_count_regions(df):
    region_risk_counts = df.groupby(['European Electoral Region', 'Risk Type']).size().reset_index(name='Count')
    region_risk_counts_pivot = region_risk_counts.pivot_table(index='European Electoral Region', columns='Risk Type', values='Count', fill_value=0).reset_index()
    for col in region_risk_counts_pivot.columns[1:]:
        region_risk_counts_pivot[col] = region_risk_counts_pivot[col].astype(int)
    region_risk_counts_pivot['Total Count'] = region_risk_counts_pivot.iloc[:, 1:].sum(axis=1)
    region_risk_counts_pivot['Risk Descriptions'] = region_risk_counts_pivot.apply(lambda row: ", ".join([f"{col} ({row[col]})" for col in region_risk_counts_pivot.columns[1:-1] if row[col] > 0]), axis=1)
    final_df = region_risk_counts_pivot[['European Electoral Region', 'Risk Descriptions', 'Total Count']]
    return final_df

def find_most_recent_folder(folders):
    most_recent_date = None
    most_recent_folder = None
    for folder in folders:
        try:
            folder_date = datetime.strptime(folder, '%Y-%m-%d')
        except ValueError:
            continue
        if most_recent_date is None or folder_date > most_recent_date:
            most_recent_date = folder_date
            most_recent_folder = folder
    return most_recent_folder

def combine_csv_files(file_pattern):
    file_list = glob.glob(file_pattern, recursive=True)
    dfs = []
    for file in file_list:
        df = pd.read_csv(file)
        dfs.append(df)
    combined_df = pd.concat(dfs, ignore_index=True)
    return combined_df

def find_date_range(df):
    df['Datetime'] = pd.to_datetime(df['Date'], format='mixed')
    most_recent_date = df['Datetime'].max().strftime('%Y-%m-%d')
    oldest_date = df['Datetime'].min().strftime('%Y-%m-%d')

    return most_recent_date, oldest_date

def preprocess_df(vis_df):
    vis_df['Industry'] = vis_df['Industry'].apply(clean_and_split)
    vis_df = vis_df[vis_df['Risk Description'].notna() & vis_df['Risk Impact'].astype(str).apply(lambda x: x.strip("[]' ") != '')]
    industry_counts = defaultdict(int)
    for industries in vis_df['Industry'].dropna():
        for industry in industries:
            if len(industry.split(' ')) > 3:
                industry = f"{' '.join(industry.split(' ')[:3])}"
                if industry[-1] == ";":
                    industry = industry[0:-1]
                industry = f'{industry}...'
            industry_counts[industry] += 1
    return vis_df, industry_counts
