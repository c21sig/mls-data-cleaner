import streamlit as st
import pandas as pd
import re

# Set up the website text
st.title("📊 Saginaw MLS Firm Ranking Cleaner")
st.write("Upload your Paragon Firm Ranking spreadsheet (CSV) to automatically clean the data and generate the Top 15 Firms by Volume.")

# Create a drag-and-drop file uploader
uploaded_file = st.file_uploader("Upload your MLS CSV File", type=["csv"])

# Define our cleaning rules
def remove_id(name):
    if not isinstance(name, str): return name
    parts = name.rsplit('-', 1)
    if len(parts) > 1:
        potential_id = parts[1].strip()
        if re.match(r'^[A-Za-z0-9]+$', potential_id) and not potential_id.isalpha():
            return parts[0].strip()
        if potential_id in ['NGL', 'BCRPAL', 'SRE/MAX', 'SChesrealty']:
            return parts[0].strip()
    return name.strip()

def standardize_firm(name):
    if not isinstance(name, str): return name
    upper = name.upper()
    
    if 'EXP' in upper:
        if 'HOLLIS' in upper or 'Z REAL ESTATE' in upper: return name
        return 'EXP Realty'
    if 'REAL ESTATE ONE' in upper:
        if 'GREAT LAKES BAY' in upper: return 'Real Estate One Great Lakes Bay'
        return 'Real Estate One'
    if 'CHESANING' in upper: return 'Chesaning Realty'
    if 'BELLABAY' in upper: return 'Bellabay Realty'
    
    if 'CENTURY 21' in upper:
        if 'SIGNATURE' in upper: return 'Century 21 Signature Realty'
        if 'PROFESSIONALS' in upper: return 'Century 21 Professionals'
        if 'METRO' in upper: return 'Century 21 Metro Brokers'
        if 'AFFILIATED' in upper: return 'Century 21 Affiliated'
        if 'HOWARD' in upper: return 'Century 21 C. Howard'
        return name

    if 'RE/MAX' in upper or 'REMAX' in upper:
        if 'NEW IMAGE' in upper: return 'RE/MAX New Image'
        if 'MIDLAND' in upper: return 'RE/MAX of Midland'
        if 'RESULTS' in upper: return 'RE/MAX Results'
        if 'TRI COUNTY' in upper or 'TRICOUNTY' in upper: return 'RE/MAX TriCounty'
        if 'PLATINUM' in upper: return 'RE/MAX Platinum'
        if 'SELECT' in upper: return 'RE/MAX Select'
        if 'PROFESSIONALS' in upper: return 'RE/MAX Real Estate Professionals'
        if 'DREAM' in upper: return 'RE/MAX Dream Properties'
        if 'OWOSSO' in upper: return 'RE/MAX of Owosso'
        if 'HIGGINS LAKE' in upper: return 'RE/MAX of Higgins Lake'
        if 'CENTRAL' in upper: return 'RE/MAX Central'
        if 'TOWN & COUNTRY' in upper: return 'RE/MAX Town & Country'
        if 'RIGHT CHOICE' in upper: return 'RE/MAX Right Choice'
        if 'PRIME PROPERTIES' in upper: return 'RE/MAX Prime Properties'
        if 'EDGE' in upper: return 'RE/MAX Edge'
        return name

    if 'BERKSHIRE' in upper:
        if 'KEE' in upper: return 'Berkshire Hathaway HomeServices Kee Realty'
        return 'Berkshire Hathaway HomeServices'
    if 'FIVE STAR' in upper: return 'Five Star Real Estate'
        
    if 'KELLER WILLIAMS' in upper or name.startswith('KW '):
        if 'PREFERRED' in upper: return 'Keller Williams Preferred'
        if 'FIRST' in upper: return 'Keller Williams First'
        if 'GREAT LAKES' in upper: return 'Keller Williams Realty Great Lakes'
        if 'PROFESSIONALS' in upper: return 'Keller Williams Professionals'
        if 'SIGNATURE' in upper: return 'Keller Williams of NM Signature Group'
        if 'NORTHERN MICHIGAN' in upper: return 'Keller Williams Northern Michigan'
        if 'LEGACY' in upper: return 'Keller Williams Legacy'
        if 'LANSING' in upper: return 'Keller Williams Lansing'
        if upper.startswith('KW PROFESSIONALS'): return 'KW Professionals'
        if upper.startswith('KW METRO'): return 'KW Metro'
        if upper.startswith('KW SHOWCASE'): return 'KW Showcase Realty'
        if upper.startswith('KW PLATINUM'): return 'KW Platinum'
        return name
        
    if 'REAL BROKER' in upper: return 'Real Broker LLC'
    if 'NEXTHOME' in upper:
        if 'GREATER TRI-CITIES' in upper: return 'NextHome Greater Tri-cities'
        if 'PARK PLACE' in upper: return 'NextHome Park Place'
        if 'LEGACY' in upper: return 'NextHome Legacy Real Estate'

    name = re.sub(r', LLC| LLC', '', name, flags=re.IGNORECASE)
    name = re.sub(r', Inc| Inc.', '', name, flags=re.IGNORECASE)
    parts = name.split(' - ')
    if len(parts) > 1: return parts[0].strip()
        
    return name.strip()

def clean_money(val):
    if not isinstance(val, str): return val
    val = val.replace('$', '').replace(',', '').strip()
    try:
        return float(val)
    except:
        return 0.0

# When a file is uploaded, process it!
if uploaded_file is not None:
    try:
        # Read the file
        df = pd.read_csv(uploaded_file, skiprows=3, names=['Rank', 'Firm', 'Units', 'Volume', 'Average', 'Median', '% Volume'])
        
        # Clean the data
        df['Clean_Firm'] = df['Firm'].apply(remove_id)
        df['Final_Firm'] = df['Clean_Firm'].apply(standardize_firm)
        
        # Remove Totals row
        df = df[df['Final_Firm'] != 'Totals'].copy()
        df = df[df['Final_Firm'] != 'Total'].copy()
        
        # Convert to numbers
        df['Volume_Num'] = df['Volume'].apply(clean_money)
        df['Units_Num'] = pd.to_numeric(df['Units'], errors='coerce').fillna(0)
        
        # Group and do math
        total_volume = df['Volume_Num'].sum()
        grouped = df.groupby('Final_Firm').agg({'Units_Num': 'sum', 'Volume_Num': 'sum'}).reset_index()
        grouped['Average'] = grouped['Volume_Num'] / grouped['Units_Num']
        grouped['% Volume'] = (grouped['Volume_Num'] / total_volume) * 100
        
        # Get Top 15
        top_15 = grouped.sort_values(by='Volume_Num', ascending=False).head(15).copy()
        top_15.insert(0, 'Rank', range(1, 16))
        
        # Format cleanly for display
        display_df = top_15.copy()
        display_df['Volume'] = display_df['Volume_Num'].apply(lambda x: f"${x:,.0f}")
        display_df['Average'] = display_df['Average'].apply(lambda x: f"${x:,.0f}")
        display_df['Market Share'] = display_df['% Volume'].apply(lambda x: f"{x:.2f}%")
        display_df['Units'] = display_df['Units_Num'].astype(int)
        display_df = display_df[['Rank', 'Final_Firm', 'Units', 'Volume', 'Average', 'Market Share']]
        display_df.rename(columns={'Final_Firm': 'Firm Name'}, inplace=True)
        
        st.success("Data successfully cleaned and processed!")
        
        # Show the table on the website
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Create a download button for the user
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download Top 15 CSV",
            data=csv,
            file_name='Cleaned_Top_15_Firms.csv',
            mime='text/csv',
        )
        
    except Exception as e:
        st.error(f"Whoops! There was an error reading the file. Make sure it's the exact format from Paragon. (Error: {e})")
