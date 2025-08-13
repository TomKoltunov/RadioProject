import sys
import requests
import threading
import sqlite3
import os
import tempfile
import uuid
import time
from datetime import datetime

# Audio initialization
try:
    import pygame

    pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
    pygame.mixer.init()
    AUDIO_ENABLED = True
    print("Audio system loaded")
except ImportError:
    AUDIO_ENABLED = False
    print("Audio not available")

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


class StationCard(QWidget):
    station_clicked = Signal(dict)

    def __init__(self, station):
        super().__init__()
        self.station = station
        self.setFixedHeight(80)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QWidget {
                background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; margin: 2px;
            }
            QWidget:hover { background: #e9ecef; border-color: #007bff; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        # Icon
        icon = QLabel("RADIO")
        icon.setFont(QFont("Arial", 10, QFont.Bold))
        icon.setFixedSize(40, 40)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background: #007bff; border-radius: 20px; color: white;")

        # Details
        details = QVBoxLayout()
        name = QLabel(station.get('name', 'Unknown'))
        name.setFont(QFont("Arial", 11, QFont.Bold))
        name.setStyleSheet("color: #212529;")

        info_parts = [station.get('country', 'Unknown')]
        if station.get('genre'):
            info_parts.append(station.get('genre'))
        if station.get('bitrate', 0) > 0:
            info_parts.append(f"{station.get('bitrate')}k")

        info = QLabel(" | ".join(info_parts))
        info.setFont(QFont("Arial", 9))
        info.setStyleSheet("color: #6c757d;")

        details.addWidget(name)
        details.addWidget(info)

        # Play button
        play_btn = QPushButton("Play")
        play_btn.setFixedSize(45, 28)
        play_btn.setStyleSheet("""
            QPushButton { background: #28a745; color: white; border: none; border-radius: 4px; font-size: 10px; font-weight: bold; }
            QPushButton:hover { background: #218838; }
        """)
        play_btn.clicked.connect(lambda: self.station_clicked.emit(self.station))

        layout.addWidget(icon)
        layout.addLayout(details)
        layout.addStretch()
        layout.addWidget(play_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.station_clicked.emit(self.station)


class RadioAPI(QThread):
    data_ready = Signal(list)
    load_error = Signal(str)

    def __init__(self, search=""):
        super().__init__()
        self.search = search

    def run(self):
        try:
            if self.search:
                url = "https://all.api.radio-browser.info/json/stations/search"
                params = {'name': self.search, 'limit': 40}
            else:
                url = "https://all.api.radio-browser.info/json/stations/topvote/50"
                params = {}

            response = requests.get(url, params=params, timeout=10, headers={'User-Agent': 'RadioPlayer/1.0'})
            if response.status_code == 200:
                stations = response.json()
                valid = []
                for s in stations:
                    url = s.get('url', '')
                    if (url and len(url) > 10 and url.startswith(('http://', 'https://')) and
                            'localhost' not in url.lower()):
                        valid.append({
                            'name': s.get('name', '').strip(),
                            'url': url.strip(),
                            'country': s.get('country', 'Unknown').strip(),
                            'genre': s.get('tags', 'Music').split(',')[0].strip().title() or 'Music',
                            'bitrate': int(s.get('bitrate', 0) or 0)
                        })
                self.data_ready.emit(valid)
            else:
                self.load_error.emit("API request failed")
        except Exception as e:
            self.load_error.emit(str(e))


class AudioPlayer:
    def __init__(self):
        self.playing = False
        self.volume = 75
        self.should_stop = False
        self.current_url = None
        self.stream_thread = None

    def play(self, url):
        try:
            self.stop()
            self.current_url = url
            self.should_stop = False

            print(f"Attempting to play: {url}")

            if AUDIO_ENABLED:
                self.stream_thread = threading.Thread(target=self._play_with_fallback, args=(url,), daemon=True)
                self.stream_thread.start()
                return True
            else:
                print("Audio not available - demo mode")
                self.playing = True
                return True
        except Exception as e:
            print(f"Play failed: {e}")
            return False

    def _play_with_fallback(self, url):
        """Try multiple methods to play the stream"""
        try:
            # Method 1: Try direct streaming
            if self._try_direct_stream(url):
                return

            # Method 2: Try with temp file download
            if self._try_temp_file_stream(url):
                return

            print("All playback methods failed")
            self.playing = False

        except Exception as e:
            print(f"Playback error: {e}")
            self.playing = False

    def _try_direct_stream(self, url):
        """Try to stream directly"""
        try:
            print("Trying direct stream...")
            pygame.mixer.music.load(url)
            pygame.mixer.music.set_volume(self.volume / 100.0)
            pygame.mixer.music.play(-1)
            self.playing = True
            print("Direct streaming successful!")

            # Keep alive
            while self.playing and not self.should_stop:
                if not pygame.mixer.music.get_busy():
                    print("Stream interrupted, restarting...")
                    if not self.should_stop:
                        pygame.mixer.music.play(-1)
                    else:
                        break
                time.sleep(1)

            return True

        except Exception as e:
            print(f"Direct streaming failed: {e}")
            return False

    def _try_temp_file_stream(self, url):
        """Download to temp file and play"""
        try:
            print("Trying temp file method...")

            # Create temp file
            temp_dir = tempfile.gettempdir()
            temp_filename = f"radio_stream_{uuid.uuid4().hex[:8]}.mp3"
            temp_path = os.path.join(temp_dir, temp_filename)

            # Download with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'audio/*,*/*;q=0.9',
                'Accept-Encoding': 'identity',
                'Connection': 'keep-alive'
            }

            print("Downloading stream data...")
            response = requests.get(url, headers=headers, stream=True, timeout=15)

            if response.status_code == 200:
                # Write initial data to temp file
                with open(temp_path, 'wb') as f:
                    chunk_count = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.should_stop:
                            break
                        if chunk:
                            f.write(chunk)
                            chunk_count += 1
                            # Get enough data to start playing (~256KB)
                            if chunk_count > 32:
                                break

                # Try to play the temp file
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1024:
                    print(f"Playing from temp file: {temp_path}")
                    pygame.mixer.music.load(temp_path)
                    pygame.mixer.music.set_volume(self.volume / 100.0)
                    pygame.mixer.music.play(-1)
                    self.playing = True
                    print("Temp file playback successful!")

                    # Continue downloading in background
                    threading.Thread(target=self._continue_download,
                                     args=(response, temp_path), daemon=True).start()

                    # Monitor playback
                    while self.playing and not self.should_stop:
                        if not pygame.mixer.music.get_busy():
                            if not self.should_stop:
                                pygame.mixer.music.play(-1)
                            else:
                                break
                        time.sleep(1)

                    # Cleanup
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except:
                        pass

                    return True

            return False

        except Exception as e:
            print(f"Temp file streaming failed: {e}")
            return False

    def _continue_download(self, response, temp_path):
        """Continue downloading stream data"""
        try:
            with open(temp_path, 'ab') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.should_stop:
                        break
                    if chunk:
                        f.write(chunk)
        except:
            pass

    def stop(self):
        print("Stopping audio...")
        self.should_stop = True
        self.playing = False

        if AUDIO_ENABLED:
            try:
                pygame.mixer.music.stop()
            except:
                pass

        self.current_url = None

    def set_volume(self, volume):
        self.volume = volume
        if AUDIO_ENABLED and self.playing:
            try:
                pygame.mixer.music.set_volume(volume / 100.0)
            except:
                pass


class FavoritesDB:
    def __init__(self):
        self.db = "favorites.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS favorites
                            (
                                id
                                INTEGER
                                PRIMARY
                                KEY,
                                name
                                TEXT,
                                url
                                TEXT
                                UNIQUE,
                                country
                                TEXT,
                                genre
                                TEXT,
                                added_when
                                TEXT
                            )""")

    def add(self, station):
        try:
            with sqlite3.connect(self.db) as conn:
                conn.execute("INSERT OR IGNORE INTO favorites VALUES (NULL,?,?,?,?,?)",
                             (station['name'], station['url'], station['country'],
                              station['genre'], datetime.now().strftime('%Y-%m-%d %H:%M')))
            return True
        except:
            return False

    def remove(self, station):
        try:
            with sqlite3.connect(self.db) as conn:
                conn.execute("DELETE FROM favorites WHERE url=?", (station['url'],))
            return True
        except:
            return False

    def is_favorite(self, station):
        try:
            with sqlite3.connect(self.db) as conn:
                return conn.execute("SELECT 1 FROM favorites WHERE url=?", (station['url'],)).fetchone() is not None
        except:
            return False

    def get_all(self):
        try:
            with sqlite3.connect(self.db) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM favorites ORDER BY added_when DESC").fetchall()
                return [{'name': r['name'], 'url': r['url'], 'country': r['country'], 'genre': r['genre']} for r in
                        rows]
        except:
            return []


class RadioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.stations = []
        self.current_station = None
        self.audio = AudioPlayer()
        self.db = FavoritesDB()
        self.setup_ui()
        threading.Timer(0.5, self.load_stations).start()

    def setup_ui(self):
        self.setWindowTitle("Radio Player")
        self.showMaximized()
        self.setStyleSheet("QMainWindow { background: #f5f5f5; }")

        main = QWidget()
        self.setCentralWidget(main)
        layout = QVBoxLayout(main)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet(
            "QWidget { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4a90e2, stop:1 #357abd); }")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)

        title = QLabel("Radio Player")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: white;")

        audio_status = QLabel(f"[Audio: {'ON' if AUDIO_ENABLED else 'OFF'}]")
        audio_status.setFont(QFont("Arial", 10))
        audio_status.setStyleSheet("color: #e6f3ff; margin-left: 15px;")

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search stations...")
        self.search_field.setFixedWidth(200)
        self.search_field.setStyleSheet(
            "QLineEdit { padding: 6px 10px; border: none; border-radius: 15px; background: white; }")
        self.search_field.returnPressed.connect(self.search_stations)

        search_btn = QPushButton("Search")
        search_btn.setFixedSize(60, 30)
        search_btn.setStyleSheet(
            "QPushButton { background: #2c5282; color: white; border: none; border-radius: 15px; font-weight: bold; }")
        search_btn.clicked.connect(self.search_stations)

        header_layout.addWidget(title)
        header_layout.addWidget(audio_status)
        header_layout.addStretch()
        header_layout.addWidget(self.search_field)
        header_layout.addWidget(search_btn)

        # Content
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #d1d5db; background: white; }
            QTabBar::tab { background: #f3f4f6; color: #374151; padding: 10px 15px; margin-right: 1px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #4a90e2; color: white; }
        """)

        # Stations tab
        stations_tab = QWidget()
        stations_layout = QVBoxLayout(stations_tab)
        stations_layout.setContentsMargins(15, 15, 15, 15)

        stations_header = QHBoxLayout()
        stations_title = QLabel("Radio Stations")
        stations_title.setFont(QFont("Arial", 16, QFont.Bold))
        stations_title.setStyleSheet("color: #1f2937;")

        self.station_counter = QLabel("0 stations")
        self.station_counter.setStyleSheet("color: #6b7280;")

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(
            "QPushButton { background: #10b981; color: white; border: none; border-radius: 5px; padding: 6px 12px; font-weight: bold; }")
        refresh_btn.clicked.connect(self.load_stations)

        random_btn = QPushButton("Random")
        random_btn.setStyleSheet(
            "QPushButton { background: #f59e0b; color: white; border: none; border-radius: 5px; padding: 6px 12px; font-weight: bold; }")
        random_btn.clicked.connect(self.play_random)

        stations_header.addWidget(stations_title)
        stations_header.addWidget(self.station_counter)
        stations_header.addStretch()
        stations_header.addWidget(refresh_btn)
        stations_header.addWidget(random_btn)

        self.stations_scroll = QScrollArea()
        self.stations_scroll.setWidgetResizable(True)
        self.stations_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stations_scroll.setStyleSheet("border: none; background: white;")

        self.stations_widget = QWidget()
        self.stations_layout = QVBoxLayout(self.stations_widget)
        self.stations_layout.setSpacing(5)
        self.stations_layout.addStretch()
        self.stations_scroll.setWidget(self.stations_widget)

        stations_layout.addLayout(stations_header)
        stations_layout.addWidget(self.stations_scroll)

        # Favorites tab
        favorites_tab = QWidget()
        favorites_layout = QVBoxLayout(favorites_tab)
        favorites_layout.setContentsMargins(15, 15, 15, 15)

        favorites_title = QLabel("My Favorites")
        favorites_title.setFont(QFont("Arial", 16, QFont.Bold))
        favorites_title.setStyleSheet("color: #1f2937;")

        self.favorites_scroll = QScrollArea()
        self.favorites_scroll.setWidgetResizable(True)
        self.favorites_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.favorites_scroll.setStyleSheet("border: none; background: white;")

        self.favorites_widget = QWidget()
        self.favorites_layout = QVBoxLayout(self.favorites_widget)
        self.favorites_layout.setSpacing(5)
        self.favorites_layout.addStretch()
        self.favorites_scroll.setWidget(self.favorites_widget)

        favorites_layout.addWidget(favorites_title)
        favorites_layout.addWidget(self.favorites_scroll)

        self.tabs.addTab(stations_tab, "Stations")
        self.tabs.addTab(favorites_tab, "Favorites")

        # Player controls
        player = QWidget()
        player.setFixedHeight(80)
        player.setStyleSheet("QWidget { background: #1f2937; border-top: 2px solid #4a90e2; }")

        player_layout = QHBoxLayout(player)
        player_layout.setContentsMargins(15, 10, 15, 10)

        # Now playing
        info_layout = QVBoxLayout()
        self.now_playing = QLabel("No station selected")
        self.now_playing.setFont(QFont("Arial", 13, QFont.Bold))
        self.now_playing.setStyleSheet("color: white;")

        self.station_info = QLabel("Click on a station to start listening")
        self.station_info.setStyleSheet("color: #9ca3af;")

        info_layout.addWidget(self.now_playing)
        info_layout.addWidget(self.station_info)

        # Controls
        self.play_btn = QPushButton("Play")
        self.play_btn.setFixedSize(60, 32)
        self.play_btn.setStyleSheet(
            "QPushButton { background: #10b981; color: white; border: none; border-radius: 16px; font-weight: bold; }")
        self.play_btn.clicked.connect(self.toggle_playback)

        stop_btn = QPushButton("Stop")
        stop_btn.setFixedSize(60, 32)
        stop_btn.setStyleSheet(
            "QPushButton { background: #ef4444; color: white; border: none; border-radius: 16px; font-weight: bold; }")
        stop_btn.clicked.connect(self.stop_playback)

        self.fav_btn = QPushButton("FAV")
        self.fav_btn.setFixedSize(60, 32)
        self.fav_btn.setStyleSheet(
            "QPushButton { background: #f59e0b; color: white; border: none; border-radius: 16px; font-weight: bold; }")
        self.fav_btn.clicked.connect(self.toggle_favorite)

        # Volume
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(75)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #4b5563; height: 5px; background: #374151; border-radius: 2px; }
            QSlider::handle:horizontal { background: #4a90e2; border: 1px solid #2563eb; width: 14px; margin: -4px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #4a90e2; border-radius: 2px; }
        """)
        self.volume_slider.valueChanged.connect(self.volume_changed)

        self.vol_label = QLabel("75%")
        self.vol_label.setStyleSheet("color: white; font-size: 10px;")

        player_layout.addLayout(info_layout)
        player_layout.addStretch()
        player_layout.addWidget(self.play_btn)
        player_layout.addWidget(stop_btn)
        player_layout.addWidget(self.fav_btn)
        player_layout.addWidget(self.volume_slider)
        player_layout.addWidget(self.vol_label)

        layout.addWidget(header)
        layout.addWidget(self.tabs)
        layout.addWidget(player)

        self.statusBar().showMessage("Ready!")

    def display_stations(self, stations, target_layout):
        # Clear existing
        for i in reversed(range(target_layout.count() - 1)):
            item = target_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()

        # Add new stations
        for station in stations[:50]:  # Limit to 50
            card = StationCard(station)
            card.station_clicked.connect(self.play_station)
            target_layout.insertWidget(target_layout.count() - 1, card)

    def load_stations(self):
        self.statusBar().showMessage("Loading...")
        self.api = RadioAPI()
        self.api.data_ready.connect(self.on_stations_loaded)
        self.api.load_error.connect(lambda e: self.statusBar().showMessage(f"Error: {e}"))
        self.api.start()

    def search_stations(self):
        query = self.search_field.text().strip()
        if not query:
            return
        self.statusBar().showMessage(f"Searching: {query}")
        self.search_api = RadioAPI(query)
        self.search_api.data_ready.connect(self.on_search_results)
        self.search_api.load_error.connect(lambda e: self.statusBar().showMessage(f"Error: {e}"))
        self.search_api.start()

    def on_stations_loaded(self, stations):
        self.stations = stations
        self.display_stations(stations, self.stations_layout)
        self.station_counter.setText(f"{len(stations)} stations")
        self.statusBar().showMessage(f"Loaded {len(stations)} stations")

    def on_search_results(self, stations):
        self.display_stations(stations, self.stations_layout)
        self.station_counter.setText(f"{len(stations)} results")
        self.statusBar().showMessage(f"Found {len(stations)} stations")

    def play_station(self, station):
        self.current_station = station
        name = station.get('name', 'Unknown')
        info = f"{station.get('country', '')} • {station.get('genre', '')}"

        self.now_playing.setText(name)
        self.station_info.setText(info)

        print(f"Playing station: {name}")
        print(f"URL: {station.get('url', '')}")

        if self.audio.play(station.get('url', '')):
            self.play_btn.setText("Pause")
            self.fav_btn.setText("UNFAV" if self.db.is_favorite(station) else "FAV")
            self.statusBar().showMessage(f"Playing: {name}")
        else:
            self.statusBar().showMessage(f"Failed: {name}")

    def toggle_playback(self):
        if self.audio.playing:
            self.audio.stop()
            self.play_btn.setText("Play")
            self.statusBar().showMessage("Stopped")
        else:
            if self.current_station:
                self.play_station(self.current_station)

    def stop_playback(self):
        self.audio.stop()
        self.play_btn.setText("Play")
        self.now_playing.setText("No station selected")
        self.station_info.setText("Click on a station to start listening")
        self.fav_btn.setText("FAV")
        self.current_station = None
        self.statusBar().showMessage("Stopped")

    def volume_changed(self, value):
        self.vol_label.setText(f"{value}%")
        self.audio.set_volume(value)

    def toggle_favorite(self):
        if not self.current_station:
            return
        if self.db.is_favorite(self.current_station):
            self.db.remove(self.current_station)
            self.fav_btn.setText("FAV")
            self.statusBar().showMessage("Removed from favorites")
        else:
            self.db.add(self.current_station)
            self.fav_btn.setText("UNFAV")
            self.statusBar().showMessage("Added to favorites")
        self.load_favorites()

    def load_favorites(self):
        favorites = self.db.get_all()
        self.display_stations(favorites, self.favorites_layout)

    def play_random(self):
        if self.stations:
            import random
            self.play_station(random.choice(self.stations))

    def closeEvent(self, event):
        try:
            self.audio.stop()
            event.accept()
        except:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Radio Player")

    player = RadioPlayer()
    player.show()
    player.load_favorites()

    print("Radio Player started!")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())