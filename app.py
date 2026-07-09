import streamlit as st
import pandas as pd
import re
import matplotlib.pyplot as plt
import io

st.title("📊 MLS Firm Ranking & Market Share Cleaner")
st.write("Upload your Paragon Firm Ranking spreadsheet (CSV). This tool automatically normalizes major franchises, strips location tags, and merges all multi-office brokerages into clean buckets for true market share!")

uploaded_file = st.file_uploader("Upload your MLS CSV File", type=["csv"])

def clean_money(val):
    if not isinstance(val, str): return val
    val = val.replace('$', '').replace(',', '').strip()
    try:
        return float(val)
    except:
        return 0.0

franchise_map = {
    'RE/MAX': ['RE/MAX', 'REMAX', 'RE MAX', 'R/E MAX'],
    'CENTURY 21': ['CENTURY 21', 'CENTURY21', 'C21'],
    'KELLER WILLIAMS': ['KELLER WILLIAMS', 'KW ', 'KW-'],
    'BERKSHIRE HATHAWAY': ['BERKSHIRE HATHAWAY', 'BHHS'],
    'COLDWELL BANKER': ['COLDWELL BANKER', 'CB '],
    'REAL ESTATE ONE': ['REAL ESTATE ONE', 'REO '],
    'NEXTHOME': ['NEXTHOME', 'NEXT HOME'],
    'FIVE STAR': ['FIVE STAR']
}

def basic_clean(name):
    if not isinstance(name, str): return name
    parts = name.rsplit('-', 1)
    if len(parts) > 1:
        potential_id = parts[1].strip()
        if re.match(r'^[A-Za-z0-9]+$', potential_id) or potential_id.upper() in ['NGL', 'BCRPAL', 'SRE/MAX', 'SCHESREALTY']:
            name = parts[0].strip()
    name = re.sub(r',? LLC\.?|,? INC\.?|,? LTD\.?', '', name, flags=re.IGNORECASE).strip()
    if ' - ' in name:
        name = name.split(' - ')[0].strip()
    return name

def get_bucket_key(clean_name):
    upper_name = clean_name.upper()
    if 'EXP' in upper_name:
        if 'HOLLIS' in upper_name or 'Z REAL' in upper_name: return upper_name
        return 'EXP REALTY'

    for std_franchise, variants in franchise_map.items():
        for variant in variants:
            if variant in upper_name or upper_name.startswith(variant):
                parts = upper_name.split(variant, 1)
                if len(parts) > 1:
                    dba_part = parts[1].strip()
                    dba_part = re.sub(r'^OF\s+', '', dba_part).strip()
                    if dba_part:
                        first_dba_word = dba_part.split()[0]
                        first_dba_word = re.sub(r'[^\w\s]', '', first_dba_word)
                        return f"{std_franchise} {first_dba_word}"
                return std_franchise

    words_to_strip = ['NORTH', 'SOUTH', 'EAST', 'WEST', 'MAIN', 'BRANCH', 'OFFICE', 'REGION', 'GROUP', 'TEAM', 'BAY CITY', 'FENTON', 'FLINT', 'MIDLAND', 'SAGINAW', 'LANSING', 'GRAND RAPIDS']
    bucket_name = upper_name
    for word in words_to_strip:
        pattern = r'\b' + word + r'$'
        bucket_name = re.sub(pattern, '', bucket_name).strip()
    bucket_name = re.sub(r'[^\w\s]$', '', bucket_name).strip()
    return bucket_name

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, skiprows=3, names=['Rank', 'Firm', 'Units', 'Volume', 'Average', 'Median', '% Volume'])
        df['Volume_Num'] = df['Volume'].apply(clean_money)
        df['Units_Num'] = pd.to_numeric(df['Units'], errors='coerce').fillna(0)
        df = df[~df['Firm'].astype(str).str.upper().str.contains('TOTAL', na=False)].copy()
        
        df['Clean_Name'] = df['Firm'].apply(basic_clean)
        df['Bucket_Key'] = df['Clean_Name'].apply(get_bucket_key)
        
        display_names = {}
        for key, group in df.groupby('Bucket_Key'):
            if key == 'EXP REALTY':
                display_names[key] = 'EXP Realty'
                continue
            shortest_name = group['Clean_Name'].loc[group['Clean_Name'].str.len().idxmin()]
            formatted_name = shortest_name.title()
            formatted_name = formatted_name.replace('Re/Max', 'RE/MAX').replace('Remax', 'RE/MAX').replace('Re Max', 'RE/MAX')
            formatted_name = formatted_name.replace('Kw ', 'Keller Williams ')
            formatted_name = formatted_name.replace('Llc', '').replace('Inc', '').strip()
            display_names[key] = formatted_name
            
        df['Final_Firm'] = df['Bucket_Key'].map(display_names)
        
        total_volume = df['Volume_Num'].sum()
        grouped = df.groupby('Final_Firm').agg({'Units_Num': 'sum', 'Volume_Num': 'sum'}).reset_index()
        grouped['Average'] = grouped['Volume_Num'] / grouped['Units_Num']
        grouped['% Volume'] = (grouped['Volume_Num'] / total_volume) * 100
        
        top_15 = grouped.sort_values(by='Volume_Num', ascending=False).head(15).copy()
        top_15.insert(0, 'Rank', range(1, 16))
        
        display_df = top_15.copy()
        display_df['Volume'] = display_df['Volume_Num'].apply(lambda x: f"${x:,.0f}")
        display_df['Average'] = display_df['Average'].apply(lambda x: f"${x:,.0f}")
        display_df['Market Share'] = display_df['% Volume'].apply(lambda x: f"{x:.2f}%")
        display_df['Units'] = display_df['Units_Num'].astype(int)
        display_df = display_df[['Rank', 'Final_Firm', 'Units', 'Volume', 'Average', 'Market Share']]
        display_df.rename(columns={'Final_Firm': 'Firm Name'}, inplace=True)
        
        st.success("Data successfully cleaned and grouped!")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # --- GENERATE PNG IMAGE OF TABLE ---
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('tight')
        ax.axis('off')
        
        # Draw the table
        table = ax.table(cellText=display_df.values, colLabels=display_df.columns, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.5)
        
        # Add alternating row colors and a nice header
        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_text_props(weight='bold', color='white')
                cell.set_facecolor('#1f77b4') # Blue header
            elif i % 2 == 0:
                cell.set_facecolor('#f0f2f6') # Light grey for alternating rows
                
        # Save table to a temporary image buffer
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=300)
        img_buffer.seek(0)
        
        # --- DISPLAY DOWNLOAD BUTTONS SIDE-BY-SIDE ---
        col1, col2 = st.columns(2)
        
        with col1:
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Top 15 CSV",
                data=csv,
                file_name='Cleaned_Top_15_Firms.csv',
                mime='text/csv',
            )
            
        with col2:
            st.download_button(
                label="🖼️ Download Top 15 PNG",
                data=img_buffer,
                file_name='Cleaned_Top_15_Firms.png',
                mime='image/png',
            )
        
    except Exception as e:
        st.error(f"Whoops! There was an error reading the file. Make sure it's the exact format from Paragon. (Error: {e})")
