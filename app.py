import streamlit as st
import pandas as pd
import re

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

# Define master list of franchises to catch messy spelling variations
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
    
    # 1. Strip MLS IDs at the end (e.g. "- MR4127" or "- NGL")
    parts = name.rsplit('-', 1)
    if len(parts) > 1:
        potential_id = parts[1].strip()
        # If it's mostly alphanumeric without spaces, or a known ID string, remove it
        if re.match(r'^[A-Za-z0-9]+$', potential_id) or potential_id.upper() in ['NGL', 'BCRPAL', 'SRE/MAX', 'SCHESREALTY']:
            name = parts[0].strip()
            
    # 2. Remove Corporate Suffixes
    name = re.sub(r',? LLC\.?|,? INC\.?|,? LTD\.?', '', name, flags=re.IGNORECASE).strip()
    
    # 3. Handle explicit hyphenated location tags (e.g., "Knockout Real Estate - Fenton")
    if ' - ' in name:
        name = name.split(' - ')[0].strip()
        
    return name

def get_bucket_key(clean_name):
    upper_name = clean_name.upper()
    
    # --- EXCEPTIONS ---
    # EXP Teams (Keep specific teams separate)
    if 'EXP' in upper_name:
        if 'HOLLIS' in upper_name or 'Z REAL' in upper_name: return upper_name
        return 'EXP REALTY'

    # --- 1. MAJOR FRANCHISE LOGIC ---
    for std_franchise, variants in franchise_map.items():
        for variant in variants:
            if variant in upper_name or upper_name.startswith(variant):
                parts = upper_name.split(variant, 1)
                if len(parts) > 1:
                    dba_part = parts[1].strip()
                    # Strip common junk words like 'OF' (e.g. "RE/MAX of Midland" -> "Midland")
                    dba_part = re.sub(r'^OF\s+', '', dba_part).strip()
                    
                    if dba_part:
                        # Grab the core DBA word (e.g. "PLATINUM" or "EDGE")
                        first_dba_word = dba_part.split()[0]
                        # Remove punctuation from the DBA word (like commas or hyphens)
                        first_dba_word = re.sub(r'[^\w\s]', '', first_dba_word)
                        return f"{std_franchise} {first_dba_word}"
                        
                return std_franchise

    # --- 2. INDEPENDENT MULTI-OFFICE LOGIC ---
    # Strip common geographic/branch words from the end of independent firm names
    # e.g., "Redwood Realty North", "Redwood Realty Main", "Redwood Realty Bay City"
    words_to_strip = [
        'NORTH', 'SOUTH', 'EAST', 'WEST', 'MAIN', 'BRANCH', 'OFFICE', 'REGION', 'GROUP', 'TEAM', 'BAY CITY', 'FENTON', 'FLINT', 'MIDLAND', 'SAGINAW', 'LANSING', 'GRAND RAPIDS'
    ]
    
    bucket_name = upper_name
    for word in words_to_strip:
        # Regex looks for the target word at the very end of the firm name
        pattern = r'\b' + word + r'$'
        bucket_name = re.sub(pattern, '', bucket_name).strip()
        
    # Strip trailing punctuation just in case (e.g. "Redwood Realty,")
    bucket_name = re.sub(r'[^\w\s]$', '', bucket_name).strip()

    return bucket_name

# --- MAIN APP LOGIC ---
if uploaded_file is not None:
    try:
        # Read the file
        df = pd.read_csv(uploaded_file, skiprows=3, names=['Rank', 'Firm', 'Units', 'Volume', 'Average', 'Median', '% Volume'])
        
        # Convert numeric columns
        df['Volume_Num'] = df['Volume'].apply(clean_money)
        df['Units_Num'] = pd.to_numeric(df['Units'], errors='coerce').fillna(0)
        
        # Exclude 'Totals' rows
        df = df[~df['Firm'].astype(str).str.upper().str.contains('TOTAL', na=False)].copy()
        
        # Clean names and assign Buckets
        df['Clean_Name'] = df['Firm'].apply(basic_clean)
        df['Bucket_Key'] = df['Clean_Name'].apply(get_bucket_key)
        
        # Determine Display Names
        display_names = {}
        for key, group in df.groupby('Bucket_Key'):
            if key == 'EXP REALTY':
                display_names[key] = 'EXP Realty'
                continue
                
            # Pick the shortest original name in the bucket for formatting
            shortest_name = group['Clean_Name'].loc[group['Clean_Name'].str.len().idxmin()]
            formatted_name = shortest_name.title()
            
            # Format the known franchises strictly
            formatted_name = formatted_name.replace('Re/Max', 'RE/MAX').replace('Remax', 'RE/MAX').replace('Re Max', 'RE/MAX')
            formatted_name = formatted_name.replace('Kw ', 'Keller Williams ')
            formatted_name = formatted_name.replace('Llc', '').replace('Inc', '').strip()
            
            display_names[key] = formatted_name
            
        # Apply final names
        df['Final_Firm'] = df['Bucket_Key'].map(display_names)
        
        # Recalculate Totals
        total_volume = df['Volume_Num'].sum()
        grouped = df.groupby('Final_Firm').agg({'Units_Num': 'sum', 'Volume_Num': 'sum'}).reset_index()
        grouped['Average'] = grouped['Volume_Num'] / grouped['Units_Num']
        grouped['% Volume'] = (grouped['Volume_Num'] / total_volume) * 100
        
        # Build Top 15
        top_15 = grouped.sort_values(by='Volume_Num', ascending=False).head(15).copy()
        top_15.insert(0, 'Rank', range(1, 16))
        
        # Formatting for UI
        display_df = top_15.copy()
        display_df['Volume'] = display_df['Volume_Num'].apply(lambda x: f"${x:,.0f}")
        display_df['Average'] = display_df['Average'].apply(lambda x: f"${x:,.0f}")
        display_df['Market Share'] = display_df['% Volume'].apply(lambda x: f"{x:.2f}%")
        display_df['Units'] = display_df['Units_Num'].astype(int)
        display_df = display_df[['Rank', 'Final_Firm', 'Units', 'Volume', 'Average', 'Market Share']]
        display_df.rename(columns={'Final_Firm': 'Firm Name'}, inplace=True)
        
        st.success("Data successfully cleaned and all multi-office brokerages grouped!")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Download
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download Top 15 CSV",
            data=csv,
            file_name='Cleaned_Top_15_Firms.csv',
            mime='text/csv',
        )
        
    except Exception as e:
        st.error(f"Whoops! There was an error reading the file. Make sure it's the exact format from Paragon. (Error: {e})")
