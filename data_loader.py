import pandas as pd
import os

# --- קבועים ---
ZODIAC_SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 
                'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

PLANET_NAME_FIXES = {
    'Sun / Earth': 'Sun', 'Jupiter': 'Jupiter', 'Mars': 'Mars', 'Venus': 'Venus',
    'Mercury': 'Mercury', 'Moon': 'Moon', 'Saturn': 'Saturn', 'Uranus': 'Uranus',
    'Neptune': 'Neptune', 'Pluto': 'Pluto'
}

def clean_planet_name(raw_name):
    clean = str(raw_name).strip().title()
    return PLANET_NAME_FIXES.get(clean, clean)

def find_file_smart(possible_names):
    for name in possible_names:
        if os.path.exists(name):
            return name
    return None

def load_astro_content():
    content = {
        'signs': {}, 'houses': {}, 'degrees': {} 
    }

    # 1. טעינת הקובץ המקורי
    excel_path = 'planets in signs.xlsx'
    if os.path.exists(excel_path):
        try:
            df_signs = pd.read_excel(excel_path, sheet_name=0, index_col=0)
            for col_name in df_signs.columns:
                planet = clean_planet_name(col_name)
                for row_name in df_signs.index:
                    sign = str(row_name).strip().title()
                    text = str(df_signs.at[row_name, col_name]).strip()
                    if text.lower() != 'nan':
                        content['signs'][(planet, sign)] = text

            df_houses = pd.read_excel(excel_path, sheet_name=1, index_col=0)
            for col_name in df_houses.columns:
                planet = clean_planet_name(col_name)
                for row_name in df_houses.index:
                    try:
                        h_raw = str(row_name).lower().replace('house', '').strip()
                        house_num = int(float(h_raw))
                        text = str(df_houses.at[row_name, col_name]).strip()
                        if text.lower() != 'nan':
                            content['houses'][(planet, house_num)] = text
                    except: continue
            print(f"✅ Loaded Main Excel: signs & houses.")
        except Exception as e:
            print(f"❌ Error loading main excel: {e}")

    # =================================================================
    # 2. טעינת הנתונים החדשים למעלות
    # =================================================================
    
    # א. משפטים קצרים
    possible_names_sentences = [
        'degree sentances.xlsx', 'degree sentences.xlsx', 'Degree Sentences.xlsx'
    ]
    found_sent = find_file_smart(possible_names_sentences)
    
    if found_sent:
        try:
            df_sent = pd.read_excel(found_sent)
            count = 0
            for col_name in df_sent.columns:
                col_clean = str(col_name).strip().title()
                if col_clean in ZODIAC_SIGNS:
                    for idx, val in df_sent[col_name].items():
                        try:
                            degree = idx + 1
                            if degree > 30: continue
                            
                            text = str(val).strip()
                            if text.lower() == 'nan': text = ""
                            
                            key = (col_clean, degree)
                            if key not in content['degrees']:
                                content['degrees'][key] = {'sentence': '', 'header': '', 'body': ''}
                            
                            content['degrees'][key]['sentence'] = text
                            count += 1
                        except: continue
            print(f"✅ Loaded {count} sentences (Matrix Mode) from '{found_sent}'")
        except Exception as e:
            print(f"❌ Error loading sentences file: {e}")
    else:
        print(f"⚠️ Warning: Could not find degree sentences file.")

    # ב. תיאור ארוך
    possible_names_inside = [
        'inside_degrees_final.xlsx', 'Inside_Degrees_Final.xlsx', 'inside degrees final.xlsx'
    ]
    found_inside = find_file_smart(possible_names_inside)

    if found_inside:
        try:
            df_inside = pd.read_excel(found_inside)
            count = 0
            for _, row in df_inside.iterrows():
                try:
                    i_sign = str(row.iloc[0]).strip().title()
                    i_deg = int(row.iloc[1])
                    i_header = str(row.iloc[2]).strip()
                    
                    # --- התיקון כאן: מחיקת הטקסט המיותר ---
                    raw_body = str(row.iloc[3])
                    i_body = raw_body.replace('~ Contents ~', '').strip()

                    if i_header.lower() == 'nan': i_header = ""
                    if i_body.lower() == 'nan': i_body = ""

                    key = (i_sign, i_deg)
                    if key not in content['degrees']:
                        content['degrees'][key] = {'sentence': '', 'header': '', 'body': ''}
                    
                    content['degrees'][key]['header'] = i_header
                    content['degrees'][key]['body'] = i_body
                    count += 1
                except: continue
            print(f"✅ Loaded {count} descriptions from '{found_inside}' (Cleaned)")
        except Exception as e:
            print(f"❌ Error loading inside degrees file: {e}")
    else:
         print(f"⚠️ Warning: Could not find inside degrees file.")

    return content

ASTRO_CONTENT = load_astro_content()