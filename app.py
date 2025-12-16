from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import swisseph as swe
import datetime
import pytz
import os
import math

# ייבוא הנתונים מקובץ הטעינה החיצוני (data_loader.py)
# וודא שהקובץ data_loader.py נמצא באותה תיקייה
from data_loader import ASTRO_CONTENT, ZODIAC_SIGNS

app = Flask(__name__)

# === הגדרת מסד הנתונים ===
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///souls.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# === תיקון גיאוקודר (זמן המתנה ארוך יותר) ===
geolocator = Nominatim(user_agent="inside_time_app_unique_id", timeout=10)

# === הגדרת המודל (הטבלה) ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.String(20), nullable=False)
    birth_time = db.Column(db.String(20), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

# יצירת הטבלאות בפעם הראשונה
with app.app_context():
    db.create_all()

# === פונקציות עזר ===

def get_coordinates_safe(city_name):
    """מנסה להשיג קואורדינטות עם מנגנון ניסיון חוזר"""
    try:
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderServiceError):
        try:
            print(f"⚠️ Timeout for {city_name}, trying again...")
            location = geolocator.geocode(city_name, timeout=15)
            if location:
                return location.latitude, location.longitude
        except:
            pass
    
    # אם נכשלנו לגמרי, נחזיר ערך ריק (או ברירת מחדל אם תרצה)
    return None, None

def calculate_chart_data(name, city, birth_date, birth_time):
    # 1. השגת קואורדינטות
    lat, lon = get_coordinates_safe(city)
    
    # אם לא הצלחנו למצוא מיקום, נשתמש בברירת מחדל כדי למנוע קריסה (למרות שב-Preview יש בדיקה מקדימה)
    if lat is None:
        lat, lon = 32.08, 34.78 # תל אביב כברירת מחדל

    # 2. פענוח תאריך ושעה (התיקון: תומך גם ב-YYYY-MM-DD וגם ב-DD/MM/YYYY)
    try:
        if '-' in birth_date:
            # פורמט שמגיע מהדפדפן (HTML date input): 2000-05-15
            parts = birth_date.split('-')
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        elif '/' in birth_date:
            # פורמט ידני: 15/05/2000
            parts = birth_date.split('/')
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            raise ValueError("Unknown date format")

        hour, minute = map(int, birth_time.split(':'))
        
    except Exception as e:
        print(f"Date Parsing Error: {e} | Input: {birth_date} {birth_time}")
        return [], "Invalid Date/Time Format"

    # 3. חישוב Julian Day (הזמן האסטרונומי)
    # הערה: זה חישוב גס ללא איזור זמן (UTC), לשיפור עתידי אפשר להוסיף timezone
    t_hour = hour + minute / 60.0
    jd = swe.julday(year, month, day, t_hour)

    # 4. רשימת הכוכבים לחישוב
    bodies = [
        ('Sun', swe.SUN), ('Moon', swe.MOON), ('Mercury', swe.MERCURY),
        ('Venus', swe.VENUS), ('Mars', swe.MARS), ('Jupiter', swe.JUPITER),
        ('Saturn', swe.SATURN), ('Uranus', swe.URANUS), ('Neptune', swe.NEPTUNE),
        ('Pluto', swe.PLUTO), ('North Node', swe.MEAN_NODE)
    ]

    chart_data = []
    
    # 5. חישוב בתים (Placidus) ואופק
    houses, ascmc = swe.houses(jd, lat, lon, b'P')
    ascendant_deg = ascmc[0]

    # הוספת אופק (Ascendant) לרשימה
    asc_sign_num = int(ascendant_deg / 30)
    asc_sign_name = ZODIAC_SIGNS[asc_sign_num]
    asc_degree_in_sign = ascendant_deg % 30
    asc_degree_int = int(asc_degree_in_sign) + 1 

    chart_data.append({
        'planet': 'Ascendant',
        'sign': asc_sign_name,
        'degree_total': ascendant_deg,
        'degree_int': asc_degree_int,
        'house': 1 # אופק תמיד בית 1
    })

    # 6. חישוב כל שאר הכוכבים
    for body_name, body_id in bodies:
        res = swe.calc_ut(jd, body_id)
        deg_total = res[0][0]
        
        sign_num = int(deg_total / 30)
        sign_name = ZODIAC_SIGNS[sign_num]
        degree_in_sign = deg_total % 30
        degree_int = int(degree_in_sign) + 1

        # חישוב הבית שבו הכוכב נמצא
        house_num = 1
        for i in range(12):
            h_cusp = houses[i]
            next_h = houses[(i+1)%12]
            
            if h_cusp < next_h:
                # מצב רגיל: הבית מתחיל ב-10 ונגמר ב-40
                if h_cusp <= deg_total < next_h:
                    house_num = i + 1
                    break
            else: 
                # מצב מעבר 360 (למשל בית שמתחיל ב-350 ונגמר ב-20)
                if h_cusp <= deg_total or deg_total < next_h:
                    house_num = i + 1
                    break
        
        chart_data.append({
            'planet': body_name,
            'sign': sign_name,
            'degree_total': deg_total,
            'degree_int': degree_int,
            'house': house_num
        })

    return chart_data, None

def enrich_planet_data(planet_dict):
    """מוסיפה טקסטים ותמונות לכל כוכב"""
    p_name = planet_dict['planet']
    sign = planet_dict['sign']
    house = planet_dict['house']
    degree = planet_dict['degree_int']

    # 1. טקסטים (מהאקסל הראשי)
    planet_dict['sign_text'] = ASTRO_CONTENT['signs'].get((p_name, sign), "")
    planet_dict['house_text'] = ASTRO_CONTENT['houses'].get((p_name, house), "")

    # 2. תמונה למעלה
    sign_lower = sign.lower()
    image_filename = f"{sign_lower}{degree}.jpg"
    image_rel_path = f"degree_images/{sign_lower}/{image_filename}"
    full_path = os.path.join(app.root_path, 'static', image_rel_path)

    if os.path.exists(full_path):
        planet_dict['image_url'] = url_for('static', filename=image_rel_path)
    else:
        planet_dict['image_url'] = "https://via.placeholder.com/400x600?text=No+Image"

# === ROUTES ===

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/database')
def database():
    users = User.query.all()
    return render_template('database.html', users=users)

@app.route('/add')
def add_profile():
    return render_template('add_profile.html')

@app.route('/preview', methods=['POST'])
def preview_profile():
    name = request.form.get('name')
    city = request.form.get('city')
    birth_date = request.form.get('birth_date')
    birth_time = request.form.get('birth_time')

    # השגת מיקום לתצוגה מקדימה
    lat, lon = get_coordinates_safe(city)
    if lat is None:
        return "Error: Could not find city location. Please try again."

    # יצירת אובייקט משתמש זמני (לא נשמר ב-DB)
    temp_user = User(
        name=name, city=city, birth_date=birth_date, birth_time=birth_time,
        latitude=lat, longitude=lon
    )

    chart_data, error = calculate_chart_data(name, city, birth_date, birth_time)
    if error: return error

    for p in chart_data:
        enrich_planet_data(p)

    return render_template('profile.html', user=temp_user, chart_data=chart_data, is_preview=True, back_url=url_for('add_profile'))

@app.route('/save_db', methods=['POST'])
def save_profile_db():
    name = request.form.get('name')
    city = request.form.get('city')
    birth_date = request.form.get('birth_date')
    birth_time = request.form.get('birth_time')
    lat = float(request.form.get('latitude'))
    lon = float(request.form.get('longitude'))

    new_user = User(name=name, city=city, birth_date=birth_date, birth_time=birth_time, latitude=lat, longitude=lon)
    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('profile', user_id=new_user.id))

@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # חישוב המפה מחדש להצגה
    try:
        # --- תיקון: זיהוי חכם של פורמט התאריך (מקפים או לוכסנים) ---
        if '-' in user.birth_date:
            # פורמט דפדפן: YYYY-MM-DD
            parts = user.birth_date.split('-')
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        elif '/' in user.birth_date:
            # פורמט ישן/ידני: DD/MM/YYYY
            parts = user.birth_date.split('/')
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            raise ValueError("Unknown date format stored in DB")

        hour, minute = map(int, user.birth_time.split(':'))
        t_hour = hour + minute / 60.0
        jd = swe.julday(year, month, day, t_hour)
        
        # רשימת גופים
        bodies = [('Sun', swe.SUN), ('Moon', swe.MOON), ('Mercury', swe.MERCURY),
                  ('Venus', swe.VENUS), ('Mars', swe.MARS), ('Jupiter', swe.JUPITER),
                  ('Saturn', swe.SATURN), ('Uranus', swe.URANUS), ('Neptune', swe.NEPTUNE),
                  ('Pluto', swe.PLUTO), ('North Node', swe.MEAN_NODE)]
        
        # חישוב בתים לפי הקואורדינטות השמורות של המשתמש
        houses, ascmc = swe.houses(jd, user.latitude, user.longitude, b'P')
        
        chart_data = []
        
        # 1. חישוב אופק
        asc_deg = ascmc[0]
        asc_s_num = int(asc_deg/30)
        chart_data.append({
            'planet': 'Ascendant', 'sign': ZODIAC_SIGNS[asc_s_num],
            'degree_int': int(asc_deg % 30) + 1, 'house': 1
        })
        
        # 2. חישוב כוכבים
        for b_name, b_id in bodies:
            res = swe.calc_ut(jd, b_id)
            d_tot = res[0][0]
            s_num = int(d_tot/30)
            d_int = int(d_tot%30) + 1
            
            # מציאת הבית
            h_num = 1
            for i in range(12):
                h_cusp = houses[i]
                nxt = houses[(i+1)%12]
                if h_cusp < nxt:
                    if h_cusp <= d_tot < nxt: h_num = i+1; break
                else:
                    if h_cusp <= d_tot or d_tot < nxt: h_num = i+1; break
            
            chart_data.append({
                'planet': b_name, 'sign': ZODIAC_SIGNS[s_num],
                'degree_int': d_int, 'house': h_num
            })
            
    except Exception as e:
        return f"Error calculating chart for profile: {e}"

    # העשרת הנתונים (טקסטים ותמונות)
    for p in chart_data:
        enrich_planet_data(p)

    # לוגיקה לכפתור חזרה
    back_source = request.args.get('back_source')
    back_sign = request.args.get('back_sign')
    back_degree = request.args.get('back_degree')

    if back_source == 'research' and back_sign and back_degree:
        back_url = url_for('research', sign=back_sign, degree=back_degree)
    else:
        back_url = url_for('index')

    return render_template('profile.html', user=user, chart_data=chart_data, is_preview=False, back_url=back_url)
@app.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
def edit_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.name = request.form['name']
        user.birth_date = request.form['birth_date']
        user.birth_time = request.form['birth_time']
        new_city = request.form['city']
        
        # אם העיר השתנתה, נחשב קואורדינטות מחדש
        if new_city != user.city:
            user.city = new_city
            lat, lon = get_coordinates_safe(new_city)
            if lat:
                user.latitude = lat
                user.longitude = lon
        
        db.session.commit()
        return redirect(url_for('profile', user_id=user.id))
        
    return render_template('edit_profile.html', user=user)

@app.route('/delete_profile/<int:user_id>')
def delete_profile(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('database')) # או לדף הבית

# === RESEARCH / ORACLE ===
@app.route('/research', methods=['GET', 'POST'])
def research():
    degree_data = None
    matching_souls = []
    
    search_sign = request.form.get('sign') or request.args.get('sign')
    search_degree = request.form.get('degree') or request.args.get('degree')
    
    next_link = None
    prev_link = None

    if search_sign and search_degree:
        try:
            search_degree = int(search_degree)
        except:
            search_degree = 1

        # 1. שליפת תוכן אומנותי
        content = ASTRO_CONTENT['degrees'].get((search_sign, search_degree), {
            'sentence': '', 'header': '', 'body': ''
        })
        
        sign_lower = search_sign.lower()
        image_filename = f"{sign_lower}{search_degree}.jpg"
        image_rel_path = f"degree_images/{sign_lower}/{image_filename}"
        full_path = os.path.join(app.root_path, 'static', image_rel_path)
        image_url = url_for('static', filename=image_rel_path) if os.path.exists(full_path) else "https://via.placeholder.com/400x600?text=No+Image"

        degree_data = {
            'sign': search_sign, 'degree': search_degree,
            'content': content, 'image_url': image_url
        }

        # 2. חיפוש נשמות תואמות (עם תיקון תאריכים)
        all_users = User.query.all()
        for u in all_users:
            try:
                # --- התיקון כאן: זיהוי חכם של התאריך ---
                if '-' in u.birth_date:
                    parts = u.birth_date.split('-')
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                elif '/' in u.birth_date:
                    parts = u.birth_date.split('/')
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                else:
                    continue # פורמט לא מוכר, מדלגים

                hour, minute = map(int, u.birth_time.split(':'))
                t_hour = hour + minute / 60.0
                jd = swe.julday(year, month, day, t_hour)
                
                # בדיקת כוכבים
                bodies = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, 
                          swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO]
                body_names = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 
                              'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
                
                for b_id, b_name in zip(bodies, body_names):
                    res = swe.calc_ut(jd, b_id)
                    d_tot = res[0][0]
                    s_name = ZODIAC_SIGNS[int(d_tot/30)]
                    d_int = int(d_tot%30) + 1
                    
                    if s_name == search_sign and d_int == search_degree:
                        # אם יש התאמה - נחשב את הבית
                        houses, _ = swe.houses(jd, u.latitude, u.longitude, b'P')
                        h_num = 1
                        for i in range(12):
                             if houses[i] <= d_tot < houses[(i+1)%12]: 
                                 h_num = i+1; break
                             # טיפול במעבר 360-0
                             if houses[i] > houses[(i+1)%12]:
                                 if d_tot >= houses[i] or d_tot < houses[(i+1)%12]: h_num = i+1; break
                        
                        matching_souls.append({
                            'name': u.name, 'id': u.id,
                            'planet': b_name, 'house': h_num
                        })
            except Exception as e:
                # במקרה של שגיאה בחישוב למשתמש ספציפי, נדלג עליו ונמשיך לבא
                continue

        # 3. ניווט (Next/Prev)
        try:
            sign_idx = ZODIAC_SIGNS.index(search_sign)
        except: sign_idx = 0
        
        # Next
        if search_degree == 30:
            n_d, n_s = 1, ZODIAC_SIGNS[(sign_idx + 1) % 12]
        else:
            n_d, n_s = search_degree + 1, search_sign
        
        # Prev
        if search_degree == 1:
            p_d, p_s = 30, ZODIAC_SIGNS[(sign_idx - 1) % 12]
        else:
            p_d, p_s = search_degree - 1, search_sign
            
        next_link = url_for('research', sign=n_s, degree=n_d)
        prev_link = url_for('research', sign=p_s, degree=p_d)

    return render_template('research.html', 
                           degree_data=degree_data, 
                           matching_souls=matching_souls,
                           search_sign=search_sign, 
                           search_degree=search_degree,
                           zodiac_signs=ZODIAC_SIGNS,
                           next_link=next_link, prev_link=prev_link)

# === API למודאל ===
@app.route('/api/degree_data')
def get_degree_data():
    sign = request.args.get('sign')
    try:
        degree = int(request.args.get('degree'))
    except:
        return jsonify({'error': 'Invalid degree'}), 400
        
    content = ASTRO_CONTENT['degrees'].get((sign, degree), {'sentence': '', 'header': '', 'body': ''})
    
    # תמונה
    sign_lower = sign.lower()
    img_name = f"{sign_lower}{degree}.jpg"
    img_path = f"degree_images/{sign_lower}/{img_name}"
    full_path = os.path.join(app.root_path, 'static', img_path)
    img_url = url_for('static', filename=img_path) if os.path.exists(full_path) else "https://via.placeholder.com/400x600?text=No+Image"
    
    # אייקון המזל (למעלה במודאל)
    # אפשר להחזיר נתיב לתמונת SVG או PNG של המזל אם יש
    # כרגע נשאיר ריק או נשתמש בלוגיקה קיימת אם יש לך תיקיית אייקונים
    symbol_url = None 
    
    # ניווט בתוך המודאל
    try: s_idx = ZODIAC_SIGNS.index(sign)
    except: s_idx = 0
    
    if degree == 30: n_d, n_s = 1, ZODIAC_SIGNS[(s_idx+1)%12]
    else: n_d, n_s = degree+1, sign
        
    if degree == 1: p_d, p_s = 30, ZODIAC_SIGNS[(s_idx-1)%12]
    else: p_d, p_s = degree-1, sign

    return jsonify({
        'sign': sign, 'degree': degree,
        'content': content,
        'image_url': img_url,
        'symbol_url': symbol_url,
        'next': {'sign': n_s, 'degree': n_d},
        'prev': {'sign': p_s, 'degree': p_d}
    })

if __name__ == '__main__':
    # הרצת השרת בצורה פתוחה לרשת הביתית (לצפייה מהנייד)
    app.run(debug=True, port=5000, host='0.0.0.0')