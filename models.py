from flask_sqlalchemy import SQLAlchemy

# יצירת אובייקט מסד הנתונים (ריק כרגע, יחובר באפליקציה)
db = SQLAlchemy()

class User(db.Model):
    """
    This table stores the profiles of people added to the app.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    
    # We store dates as strings (YYYY-MM-DD) to avoid complexity with SQLite types
    birth_date = db.Column(db.String(20), nullable=False) 
    birth_time = db.Column(db.String(20), nullable=False)
    
    # Coordinates are crucial so we don't need to geocode every time (saves time/API calls)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<User {self.name}>'