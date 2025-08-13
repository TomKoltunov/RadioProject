# RadioProject
ניתוח מפורט של נגן הרדיו האינטרנטי
סקירה כללית
פרויקט Python מתקדם לנגן רדיו אינטרנטי, בנוי על ארכיטקטורה מודולרית המשלבת ממשק גרפי מתקדם, ניגון אודיו רציף, וניהול בסיס נתונים. הפרויקט מדגים שימוש מיטבי בטכנולוגיות מרובות לבניית אפליקציה מולטימדיה יציבה.
ארכיטקטורת המערכת
רכיבי הליבה
1. StationCard - רכיב כרטיס תחנה
ממשק גרפי אינטראקטיבי לכל תחנת רדיו
עיצוב CSS מתקדם עם אפקטי hover
טיפול באירועי עכבר ושליחת signals
2. RadioAPI - שכבת תקשורת רשת
חוט עיבוד נפרד לאי-חסימת הממשק
חיבור ל-Radio Browser API
סינון וולידציה של נתוני תחנות
3. AudioPlayer - מנוע הניגון
מספר אסטרטגיות ניגון עם fallback
טיפול בזרמי אודיו מרוחקים
ניהול קבצים זמניים והורדה מקבילית
4. FavoritesDB - מערכת מועדפים
בסיס נתונים SQLite מקומי
פעולות CRUD מלאות
שמירת מטאדטה עם timestamps
5. RadioPlayer - ממשק ראשי
תזמור כל הרכיבים
ממשק משתמש מתקדם עם tabs
בקרות ניגון מלאות
ניתוח מפורט של הקוד
אתחול המערכת
python
# בדיקת זמינות אודיו
try:
    import pygame
    pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
    pygame.mixer.init()
    AUDIO_ENABLED = True
except ImportError:
    AUDIO_ENABLED = False
פרמטרי האודיו:
תדירות: 22.05 KHz (איכות טובה, ביצועים מיטביים)
גודל דגימה: 16-bit signed (איכות CD)
ערוצים: 2 (סטריאו)
Buffer: 1024 bytes (איזון השהיה-חלקות)
קלאס StationCard - עיצוב ופונקציונליות
python
class StationCard(QWidget):
    station_clicked = Signal(dict)
    
    def __init__(self, station):
        super().__init__()
        self.station = station
        self.setFixedHeight(80)
        self.setCursor(Qt.PointingHandCursor)
תכונות עיצוב:
גובה קבוע 80px לאחידות ויזואלית
סמן יד למשוב ויזואלי
CSS styling מובנה עם אפקטי hover
פריסה אופקית עם אייקון, פרטים וכפתור
הכנת המידע:
python
info_parts = [station.get('country', 'Unknown')]
if station.get('genre'):
    info_parts.append(station.get('genre'))
if station.get('bitrate', 0) > 0:
    info_parts.append(f"{station.get('bitrate')}k")

info = QLabel(" | ".join(info_parts))
קלאס RadioAPI - תקשורת רשת מתקדמת
python
class RadioAPI(QThread):
    data_ready = Signal(list)
    load_error = Signal(str)
אסטרטגיית הרשת:
עיבוד בחוט נפרד (QThread) למניעת חסימת UI
שני מודי פעולה: תחנות פופולריות וחיפוש ממוקד
ולידציה מקיפה של נתונים נכנסים
בדיקות תקינות:
python
if (url and len(url) > 10 and 
    url.startswith(('http://', 'https://')) and
    'localhost' not in url.lower()):
מנוע הניגון AudioPlayer - טכנולוגיה מתקדמת
שיטות ניגון מרובות:
1. זרימה ישירה:
python
def _try_direct_stream(self, url):
    pygame.mixer.music.load(url)
    pygame.mixer.music.set_volume(self.volume / 100.0)
    pygame.mixer.music.play(-1)  # לולאה אינסופית
2. קובץ זמני עם הורדה מקבילית:
python
def _try_temp_file_stream(self, url):
    # יצירת קובץ זמני ייחודי
    temp_filename = f"radio_stream_{uuid.uuid4().hex[:8]}.mp3"
    
    # Headers מתקדמים לעקיפת הגבלות
    headers = {
        'User-Agent': 'Mozilla/5.0...',
        'Accept': 'audio/*,*/*;q=0.9',
        'Accept-Encoding': 'identity',
        'Connection': 'keep-alive'
    }
מנגנון Keep-Alive:
python
while self.playing and not self.should_stop:
    if not pygame.mixer.music.get_busy():
        if not self.should_stop:
            pygame.mixer.music.play(-1)  # התחלה מחדש
    time.sleep(1)
מערכת המועדפים FavoritesDB
מבנה טבלה:
sql
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY,
    name TEXT,
    url TEXT UNIQUE,
    country TEXT,
    genre TEXT,
    added_when TEXT
)
פעולות מרכזיות:
הוספה עם INSERT OR IGNORE למניעת כפילויות
בדיקת קיום ביעילות גבוהה
מיון לפי תאריך הוספה (DESC)
Row factory לגישה נוחה לנתונים
הממשק הראשי RadioPlayer
אתחול המערכת:
python
def __init__(self):
    super().__init__()
    self.stations = []
    self.current_station = None
    self.audio = AudioPlayer()
    self.db = FavoritesDB()
    self.setup_ui()
    threading.Timer(0.5, self.load_stations).start()  # טעינה מושהית
בניית הממשק המתקדם:
כותרת עם גרדיאנט:
python
header.setStyleSheet(
    "QWidget { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4a90e2, stop:1 #357abd); }"
)
שדה חיפוש מעוצב:
python
self.search_field.setStyleSheet(
    "QLineEdit { padding: 6px 10px; border: none; border-radius: 15px; background: white; }"
)
מערכת כרטיסיות:
Tab מרכזי לתחנות רגילות
Tab נפרד למועדפים
עיצוב CSS מותאם אישית
אלגוריתמים ותהליכים מרכזיים
תהליך הצגת תחנות
python
def display_stations(self, stations, target_layout):
    # ניקוי רכיבים קיימים
    for i in reversed(range(target_layout.count() - 1)):
        item = target_layout.takeAt(i)
        if item.widget():
            item.widget().deleteLater()
    
    # הוספת תחנות חדשות (מקסימום 50)
    for station in stations[:50]:
        card = StationCard(station)
        card.station_clicked.connect(self.play_station)
        target_layout.insertWidget(target_layout.count() - 1, card)
אלגוריתם הפעלת תחנה
python
def play_station(self, station):
    self.current_station = station
    name = station.get('name', 'Unknown')
    info = f"{station.get('country', '')} • {station.get('genre', '')}"
    
    # עדכון ממשק מיידי
    self.now_playing.setText(name)
    self.station_info.setText(info)
    
    # ניסיון הפעלה עם feedback
    if self.audio.play(station.get('url', '')):
        self.play_btn.setText("Pause")
        self.fav_btn.setText("UNFAV" if self.db.is_favorite(station) else "FAV")
        self.statusBar().showMessage(f"Playing: {name}")
    else:
        self.statusBar().showMessage(f"Failed: {name}")
תכונות מתקדמות
ניהול חוטים (Threading Strategy)
1. QThread לרשת:
עיבוד נתוני API ברקע
אי-חסימת הממשק הגרפי
signals לתקשורת עם UI thread
2. Daemon threads לאודיו:
ניגון רציף בחוט נפרד
ניטור מתמיד של סטטוס הזרם
עצירה אוטומטית עם סגירת התוכנית
3. Timer threads:
טעינה מושהית של תחנות
אי-חסימת תהליך ההפעלה
מנגנוני שגיאות וגיבוי
שכבות ההגנה:
בדיקת זמינות אודיו בהפעלה
מצב DEMO כאשר אין אודיו
ניסיון מספר שיטות ניגון
restart אוטומטי של זרמים נפסקים
ניקוי קבצים זמניים
אופטימיזציות ביצועים
ממשק משתמש:
הגבלת תחנות מוצגות ל-50
עיבוד ברקע למניעת קיפאון
deleteLater() לשחרור זיכרון נכון
שימוש ברשת:
timeout מוגדר לבקשות HTTP
streaming של נתונים (chunk-based)
headers מתקדמים לעקיפת הגבלות
ניהול אודיו:
buffer size מותאם
טעינה מקבילית של זרמים
volume control בזמן אמת
פלטפורמות ותאימות
תלויות חיצוניות:
PySide6: ממשק גרפי חוצה פלטפורמות
pygame: ניגון אודיו במגוון פורמטים
requests: תקשורת HTTP מתקדמת
sqlite3: בסיס נתונים מובנה
תאימות:
Windows, Linux, macOS
תמיכה בפורמטי אודיו מרובים
זיהוי אוטומטי של יכולות המערכת

