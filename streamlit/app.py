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
from utils import *

st.set_page_config(layout="wide", page_title="GERM", page_icon='./data/favicon.png')

custom_css = """
<style>
    html, body, [class*="st-"] {
        font-family: 'Josefin Sans', sans-serif;
    }

    header {visibility: hidden;}

    .st-emotion-cache-yc0paw {
        display: none;
    }
    a {
    color: #F3C65B !important;
    }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

with open(f'./data/assets/geo/uk.geojson') as geojson_file:
    uk_geojson_data = json.load(geojson_file)
with open(f'./data/assets/geo/world.geojson') as geojson_file:
    world_geojson_data = json.load(geojson_file)

# 1. Load and preprocess data from latest folder:

directory_path = './data/historic'

df = combine_csv_files(f'{directory_path}/**/risks.csv')
recent_date, oldest_date = find_date_range(df)

df_risk_impacts = pd.read_csv(f'{directory_path}/risk_impacts_spatial.csv')
df_risk_impacts['Datetime'] = pd.to_datetime(df_risk_impacts['Date'], format='mixed')

df = df[['Company', 'Industry', 'Date', 'Risk Type', 'Datetime', 'Risk Description', 'Risk Impact', 'Source Text', 'Link', 'Pass', 'Risk Countries', 'European Electoral Region', 'equity','employees']]
df.rename(columns={'equity': 'Company Equity (£)'}, inplace=True)
df.rename(columns={'employees': 'Number of Employees'}, inplace=True)
df['Number of Employees'] = df['Number of Employees'].replace(0, None)
df = clean_risk_df(df)

all_industries_with_option = ['All Industries'] + sorted(set(
    [item for sublist in df['Industry'] if sublist is not None for item in sublist if item]
))
all_risk_types = ['All Risk Types'] + sorted(df['Risk Type'].unique())

# 2. Add Sidebar

with st.sidebar:
    st.header('Filters')
    selected_industry = st.selectbox('Select Industry', options=all_industries_with_option)
    selected_risk_type = st.selectbox('Select Risk Type', options=all_risk_types)
    date_range = st.slider("Select Date Range",
                           min_value=pd.to_datetime(recent_date).date(),
                           max_value=pd.to_datetime(oldest_date).date(),
                           value=(pd.to_datetime(recent_date).date(), pd.to_datetime(oldest_date).date()),
                           format="YYYY-MM-DD")

start_date, end_date = date_range  # unpacking the selected date range from the slider

filtered_df = df[(df['Datetime'] >= pd.to_datetime(start_date)) & (df['Datetime'] <= pd.to_datetime(end_date))]
filtered_risk_impacts = df_risk_impacts[(df_risk_impacts['Datetime'] >= pd.to_datetime(start_date)) & (df_risk_impacts['Datetime'] <= pd.to_datetime(end_date))]
if selected_industry == 'All Industries' and selected_risk_type == 'All Risk Types':
    pass
elif selected_industry == 'All Industries':
    filtered_df = filtered_df[filtered_df['Risk Type'] == selected_risk_type]
    filtered_risk_impacts = filtered_risk_impacts[filtered_risk_impacts['Risk Type'] == selected_risk_type]
elif selected_risk_type == 'All Risk Types':
    filtered_df = filtered_df.dropna(subset=['Industry'])
    filtered_df = filtered_df[filtered_df['Industry'].apply(lambda x: selected_industry in x)]
    filtered_risk_impacts = filtered_risk_impacts[filtered_risk_impacts['Industry'].apply(lambda x: selected_industry in x)]
else:
    filtered_df = filtered_df.dropna(subset=['Industry'])
    filtered_df = filtered_df[(filtered_df['Industry'].apply(lambda x: selected_industry in x)) & (filtered_df['Risk Type'] == selected_risk_type)]
    filtered_risk_impacts = filtered_risk_impacts[filtered_risk_impacts['Industry'].apply(lambda x: selected_industry in x)]
    filtered_risk_impacts = filtered_risk_impacts[filtered_risk_impacts['Risk Type'] == selected_risk_type]

countries_df = get_risk_count_countries(filtered_df)
uk_region_df = get_risk_count_regions(filtered_df)

color_map = {
    'Interstate Conflict': '#ff0000',  # Bright Red
    'Terrorism': '#8b0000',  # Darker red
    'Subnational Conflict': '#e03131', # Lighter Red
    'Social Unrest': '#a61e4d',  # Purple Red
    'Sanctions': '#ff8c00',  # Orange
    'Criminal Activity': '#ff6b6b',  # Pink
    'Modern Slavery': '#ffac1c',  # Lighter Orange
    'Corruption Deterioration': '#ffd700',  #Yellow
    'Industrial Action': '#868e96',  # Darker Gret
    'Talent Availability': '#adb5bd',  # Mid Grey
    'Logistics Restrictions': '#e9ecef',  # Slightly darker gret
    'Emerging Regulation': '#f8f9fa',  # very light grey
    'Change in Government': '#f76707',  # A vibrant light orange, suggesting the potential for fresh policies
    'Minimum Wage Hike': '#fff4e6',  # A bright yellow, symbolizing the economic prosperity
    'Privatisation': '#ffd8a8',  # Vibrant Light Teal, for economic reform
    'Nationalisation': '#ffe8cc',  # Sky Blue, indicating government control increase
    'Extreme Weather': '#94d82d',  # Dodger Blue, for immediate natural events
    'Environmental Degradation': '#0073e6',  # Bright Strong Blue, for significant environmental impact
    'Natural Resource Deficiency': '#0057b8',  # Vibrant Dark Blue, indicating critical resources issue
    'Climate Change': '#51cf66',  # Bright Green, for long-term environmental challenge
    'Food Security': '#40e0d0',  # Turquoise, related to Climate Change but with a focus on food
    'Space': '#7b68ee',  # Medium Slate Blue, for frontier exploration
    'Geophysical': '#9932cc',  # Dark Orchid, for geophysical events
    }

# 3. Risk Type Chart

risk_type_counts = filtered_df['Risk Type'].value_counts().reset_index()
risk_type_counts.columns = ['Risk Type', 'Count']
fig_title = None
if selected_industry != 'All Industries':
    fig_title = dict(text=f'Risks to {selected_industry}', font=dict(family="'Josefin Sans', sans-serif"))

fig_count = px.bar(risk_type_counts,
                title = None,
             x='Risk Type',
             y='Count',
             labels={'Count': 'Frequency', 'Risk Type': 'Risk Type'},
             color='Risk Type',
           color_discrete_map=color_map)

hovertemplate = '%{x}<br><br>' + \
                'Frequency: %{y}<br>' + \
                '<extra></extra>'

plotly_config = {'displayModeBar': False}
fig_count.update_traces(hovertemplate=hovertemplate)
fig_count.update_layout(xaxis_title="Risk Type",
                  yaxis_title="Frequency",
                  xaxis={'categoryorder':'total descending'})

if fig_title:
    fig_count.update_layout(
                        title=fig_title,
                        font=dict(family="'Josefin Sans', sans-serif"),
                        xaxis=dict(tickangle=45),
        hoverlabel=dict(
        font=dict(
            family="Josefin Sans, Arial",
        ),
        bgcolor='#333333'
    ),
                        xaxis_title="",
                       showlegend=False)
else:
    fig_count.update_layout(
                        font=dict(family="'Josefin Sans', sans-serif"),
                        xaxis=dict(tickangle=45),
        hoverlabel=dict(
        font=dict(
            family="Josefin Sans, Arial",
        ),
        bgcolor='#333333'
    ),
                        xaxis_title="",
                       showlegend=False)
fig_count.update_xaxes( showgrid=True, gridwidth=1, tickmode='auto', mirror=True, showline=True, gridcolor='rgba(68,68,68, 0.25)')
fig_count.update_yaxes(showgrid=True, gridwidth=1, tickmode='auto', mirror=True, showline=True, gridcolor='rgba(68,68,68, 0.25)')
fig_count.update_layout(plot_bgcolor='#222222')

df_industry, industry_counts = preprocess_df(filtered_df)
industry_counts_df = pd.DataFrame(list(industry_counts.items()), columns=['Industry', 'Risk Count'])

fig_industry_title = None
if selected_risk_type != 'All Risk Types':
    fig_industry_title = dict(text=f'Industries Impacted by {selected_risk_type}', font=dict(family="'Josefin Sans', sans-serif"))

fig_industry = px.bar(industry_counts_df, x='Industry', y='Risk Count',
                      title = None,
                      labels={'Risk Count': 'Number of Risks', 'Industry': 'Industry'},
                      color='Industry')

hovertemplate = '%{x}<br><br>' + \
                'Risks: %{y}<br>' + \
                '<extra></extra>'

plotly_config = {'displayModeBar': False}
fig_industry.update_traces(hovertemplate=hovertemplate)
fig_industry.update_layout(xaxis_title=None,
                           yaxis_title="Risks",
                           xaxis={'categoryorder':'total descending'})  # Assuming a dark theme; adjust as necessary

if fig_industry_title:
    fig_industry.update_layout(
                        title=fig_industry_title,
                        font=dict(family="'Josefin Sans', sans-serif"),
                        xaxis=dict(tickangle=45),
        hoverlabel=dict(
        font=dict(
            family="Josefin Sans, Arial",
        ),
        bgcolor='#333333'
    ),
                        xaxis_title="",
                       showlegend=False)
else:
    fig_industry.update_layout(
                        font=dict(family="'Josefin Sans', sans-serif"),
                        xaxis=dict(tickangle=45),
        hoverlabel=dict(
        font=dict(
            family="Josefin Sans, Arial",
        ),
        bgcolor='#333333'
    ),
                        xaxis_title="",
                       showlegend=False)

fig_industry.update_xaxes( showgrid=True, gridwidth=1, tickmode='auto', mirror=True, showline=True, gridcolor='rgba(68,68,68, 0.25)')
fig_industry.update_yaxes(showgrid=True, gridwidth=1, tickmode='auto', mirror=True, showline=True, gridcolor='rgba(68,68,68, 0.25)')
fig_industry.update_layout(plot_bgcolor='#222222')

# 4. Risk Impact Chart

fig = px.scatter(filtered_risk_impacts, x='x', y='y', color='Risk Type',
                 color_discrete_map=color_map,
                 hover_data={'Company': True, 'x': False, 'y': False, 'Risk Type': True, 'Risk_Impact': True},
                 title=None)

hovertemplate = '%{customdata[0]}<br><br>' + \
                'Risk Type: %{customdata[1]}<br>' + \
                'Risk Impact: <span style="color:red;">%{customdata[2]}</span><br>' + \
                '<extra></extra>'

plotly_config = {'displayModeBar': False}

fig.update_traces(marker=dict(size=6), hovertemplate=hovertemplate)
fig.update_layout(height=600, width=800, showlegend=True,
)
fig.update_xaxes(showgrid=True, gridwidth=1, showticklabels=False, title_text=None, tickmode='auto', nticks=25, mirror=True, showline=True, gridcolor='rgba(68,68,68, 0.25)')
fig.update_yaxes(showgrid=True, gridwidth=1, showticklabels=False, title_text=None, tickmode='auto', nticks=25, mirror=True, showline=True, gridcolor='rgba(68,68,68, 0.25)')
fig.update_layout(font=dict(family="'Josefin Sans', sans-serif"),
        hoverlabel=dict(
        font=dict(
            family="Josefin Sans, Arial",
        ),
        bgcolor='#333333'
    ),)
fig.update_layout(
    margin=dict(l=20, r=20, t=20, b=20),  # Try setting left and bottom margins to 0
)
fig.update_xaxes(zeroline=False)
fig.update_yaxes(zeroline=False)
fig.update_layout(plot_bgcolor='#222222')

# 5. UK Map

uk_region_mapping = uk_region_df.set_index('European Electoral Region')[['Risk Descriptions', 'Total Count']].to_dict('index')

for feature in uk_geojson_data['features']:
    uk_region_name = feature['properties']["eer18nm"]
    if uk_region_name in uk_region_mapping:
        uk_region_data = uk_region_mapping[uk_region_name]
        feature['properties']['description'] = uk_region_data['Risk Descriptions']
        feature['properties']['count'] = int(uk_region_data['Total Count'])
    else:
        pass
        feature['properties']['description'] = ''
        feature['properties']['count'] = 0

uk_gdf = gpd.GeoDataFrame.from_features(uk_geojson_data['features'])
uk_max_count = uk_gdf['count'].max()
uk_gdf['alpha'] = uk_gdf['count'].apply(lambda x: 0 if x == 0 else 225)
get_uk_fill_color_str = f"""
[255 - 52 * count / {uk_max_count},
 191 - 167 * count / {uk_max_count},
 0 + 29 * count / {uk_max_count},
 alpha]"""
uk_gdf["formatted_description"] = uk_gdf["description"].apply(format_description)

uk_layer = pdk.Layer(
    'GeoJsonLayer',
    data=uk_gdf,
    opacity=0.8,
    stroked=False,
    filled=True,
    extruded=False,
    get_fill_color = get_uk_fill_color_str,
    pickable=True,
)

uk_tooltip={
    "text": "{eer18nm}\n\n{formatted_description}",
    "style": {
        "backgroundColor": '#333333',
        "color": "white",
        "border": "1px solid white"
    }
}

uk_initial_view_state = pdk.ViewState(
    latitude=55.7,
    longitude=-3,
    zoom=4.1,
    min_zoom=4.1,
    max_zoom=10
)

# 6. World Map
country_mapping = countries_df.set_index('Risk Countries')[['Risk Descriptions', 'Total Count']].to_dict('index')

for feature in world_geojson_data['features']:
    country_name = feature['properties']['name']
    if country_name in country_mapping:
        country_data = country_mapping[country_name]
        feature['properties']['description'] = country_data['Risk Descriptions']
        feature['properties']['count'] = int(country_data['Total Count'])
    else:
        pass
        feature['properties']['description'] = ''
        feature['properties']['count'] = 0

world_gdf = gpd.GeoDataFrame.from_features(world_geojson_data['features'])
world_max_count = world_gdf['count'].max()
world_gdf['alpha'] = world_gdf['count'].apply(lambda x: 0 if x == 0 else 225)
get_world_fill_color_str = f"""
[255 - 52 * count / {world_max_count},
 191 - 167 * count / {world_max_count},
 0 + 29 * count / {world_max_count},
 alpha]"""

world_gdf["formatted_description"] = world_gdf["description"].apply(format_description)
world_layer = pdk.Layer(
    'GeoJsonLayer',
    data=world_gdf,
    opacity=0.8,
    stroked=False,
    filled=True,
    extruded=False,
    get_fill_color = get_world_fill_color_str,
    pickable=True,
)

world_tooltip={
    "text": "{name}\n\n{formatted_description}",
    "style": {
        "backgroundColor": '#333333',
        "color": "white",
        "border": "1px solid white"
    }
}

world_initial_view_state = pdk.ViewState(
    latitude=30,
    longitude=0,
    zoom=1.6,
    min_zoom=1.5,
    max_zoom=5
)

# Streamlit app
st.title('GERM')
st.markdown('''
##### Geopolitical & Environmental Risk Monitor <span style="font-size: large; padding: 5px; margin-left: 10px; background-color: #F3993E; color: white; border-radius: 5px;">Prototype</span>
''', unsafe_allow_html=True)
if recent_date == oldest_date:
    st.markdown(f'Last Updated: **{rewrite_date(recent_date)}**')
else:
    st.markdown(f'Sample Coverage: **{rewrite_date(str(oldest_date))}** - **{rewrite_date(str(recent_date))}**')
st.markdown(f'Sample Reports Processed: **266,989**')
st.markdown('GERM is a tool developed by [Autonomy](https://autonomy.work/) to map geopolitical and environmental risks mentioned within annual reports filed electronically with [Companies House](https://www.gov.uk/government/organisations/companies-house). All risks are classified using risk types adapted from the [Cambridge Taxonomy of Business Risks](https://www.jbs.cam.ac.uk/wp-content/uploads/2021/11/crs-cambridge-taxonomy-of-business-risks.pdf).', unsafe_allow_html=True)
st.markdown("""The content and comprehensiveness of risk disclosures by larger companies in the UK shows considerable variability, posing a challenge for analysis. Most of the companies that file their annual reports electronically are smaller in size and are not required to disclose risks. Larger companies are required to disclose risks, although the format for these disclosures is less standardized than the risk sections found within the 10-K annual reports filed with the SEC by US companies. To overcome this variability, we used advanced language models to extract, classify and summarise some of the key information included within risk disclosures made by UK companies filing within the sample coverage period.""", unsafe_allow_html=True)
st.markdown("""✉️ [Please reach out](mailto:info@autonomy.work) if this research is useful to you and you would like to access the full dataset.""", unsafe_allow_html=True)

filtered_df.rename(columns={'Risk Type': 'Risk Type  ⚙️',
                            'Risk Description': 'Risk Summary  ⚙️',
                   'Risk Impact': 'Noted Impacts  ⚙️',
                    'Risk Countries': 'Risk Countries  ⚙️'},
                   inplace=True)

filtered_df.set_index('Date', inplace=True)
filtered_df.sort_index(inplace=True)
filtered_df = filtered_df.drop(['Datetime'], axis=1)
filtered_df.reset_index(inplace=True)
cols = filtered_df.columns.tolist()  # Get the list of all columns
cols = [c for c in cols if c not in ['Date', 'Link']] + ['Link'] + ['Date']  # Move 'Date' to the end
filtered_df = filtered_df[cols]

# Display filtered data and the map
st.markdown('#### 1. Risk Database')
with st.expander("Details ℹ️"):
    st.write("""The table below contains all of the geopolitical and environmental risks identified in annual reports submitted electronically during the sample period. Columns marked with a ⚙️ symbol contain data that has been partially synthesized by an advanced large language model. This synthesized data represents the language model's interpretation of the original source material rather than objective fact. While this synthetic data can enhance the process of classifying and navigating the database, it is crucial to cross-reference it with the information in the 'Source Text' column for accuracy and reliability. The remainder of the data is derived directly from the annual report, Companies House and [Postcodes.io](https://postcodes.io/). Please note, there may be instances of missing data where absent in the cited sources.

Each row within the table contains a unique risk found within an annual report. Each risk is classified (Risk Type ⚙️) and summarised (Risk Summary ⚙️). The possible/actual impacts of each risk as stated in the company's report are summarised (Noted Impacts ⚙️).""")
st.dataframe(filtered_df, width=1500)

title_3 = '#### 2. Risk Impacts'
title_4 = '#### 3. Worldwide Risks'
title_5 = '#### 4. UK Regional Risks'

if selected_industry == 'All Industries' and selected_risk_type == 'All Risk Types':
    st.markdown('#### 2. Risk Type')
    st.plotly_chart(fig_count, config=plotly_config)
    st.markdown('#### 3. Industries')
    st.plotly_chart(fig_industry, config=plotly_config)
    title_2 = '#### 3. Industries'
    title_3 = '#### 4. Risk Impacts'
    title_4 = '#### 5. Worldwide Risks'
    title_5 = '#### 6. UK Regional Risks'
elif selected_industry == 'All Industries' and selected_risk_type != 'All Risk Types':
    st.markdown('#### 2. Industries')
    st.plotly_chart(fig_industry, config=plotly_config)
    title_3 = '#### 3. Risk Impacts'
    title_4 = '#### 4. Worldwide Risks'
    title_5 = '#### 5. UK Regional Risks'
elif selected_industry != 'All Industries' and selected_risk_type == 'All Risk Types':
    st.markdown('#### 2. Risk Type')
    st.plotly_chart(fig_count, config=plotly_config)
    title_3 = '#### 3. Risk Impacts'
    title_4 = '#### 4. Worldwide Risks'
    title_5 = '#### 5. UK Regional Risks'

st.markdown(title_3)
with st.expander("Details ℹ️"):
    st.write("The visualization below represents a scatter plot mapping the impacts associated with each geopolitical and environmental risk. Each point corresponds to a specific impact identified in the 'Noted Impacts  ⚙️' column of the preceding Risk Database. Impacts that are semantically similar are plotted in proximity to each other. The spatial arrangement of the impacts is the result of applying dimensional reduction techniques to embedding models. **Double-click** on a risk type in the legend to exclusively view the risk type's associated impacts, or **single-click** to conceal the associated impacts.")
st.plotly_chart(fig, theme=None, config=plotly_config)

st.markdown(title_4)
with st.expander("Details ℹ️"):
    st.write("The map below represents the countries mentioned or referenced in company risk disclosures (excluding the UK). These countries are listed within the 'Risk Countries  ⚙️' column of the preceding Risk Database with each colored according to the number of risks where the country is mentioned.")
st.pydeck_chart(pdk.Deck(layers=[world_layer], initial_view_state=world_initial_view_state, tooltip=world_tooltip))

st.markdown(title_5)
with st.expander("Details ℹ️"):
    st.write("The map below represents the UK regions where companies disclosing risks are located. These regions are listed within the 'European Electoral Region' column of the preceding Risk Database with each colored according to the number of unique risks identified by companies with registered addresses in that region.")
st.pydeck_chart(pdk.Deck(layers=[uk_layer], initial_view_state=uk_initial_view_state, tooltip=uk_tooltip))
