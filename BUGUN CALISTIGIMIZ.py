import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from pytz import timezone
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QLabel, QGridLayout, QHBoxLayout, QLineEdit, QPushButton,
    QRadioButton, QComboBox, QButtonGroup, QGroupBox, QMessageBox,
    QFrame, QSizePolicy, QStyle
)
from PyQt5.QtChart import (
    QChart, QChartView, QCandlestickSeries, QCandlestickSet,
    QDateTimeAxis, QValueAxis, QLineSeries
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QPointF, QDate, QTime, QMargins
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QBrush, QIcon

# Renk paleti
DARK_BACKGROUND = "#121212"
DARKER_BACKGROUND = "#0a0a0a"
ACCENT_COLOR = "#4e9af1"
GREEN_COLOR = "#4CAF50"
RED_COLOR = "#F44336"
TEXT_COLOR = "#E0E0E0"
HIGHLIGHT_COLOR = "#2a2a2a"

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

class InteractiveChartView(QChartView):
    def __init__(self, chart, series, *labels, parent=None):
        super().__init__(chart, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRubberBand(QChartView.RectangleRubberBand)
        self.setMouseTracking(True)
        self.setInteractive(True)
        self.series = series
        self.candles = []
        self._hover_candle = None  # Bu satırı ekledik
        self._mouse_pressed = False
        self._last_mouse_pos = None

        (self.open_label, self.close_label, self.change_label,
         self.high_label, self.low_label, self.rsi_label,
         self.volume_label, self.total_volume_label,
         self.money_flow_label, self.ma20_label, self.ma50_label,
         self.ma200_label, self.pivot_label, self.support1_label,
         self.support2_label, self.resistance1_label,
         self.resistance2_label) = labels

        self.cross_pen = QPen(Qt.DotLine)
        self.cross_pen.setColor(QColor(ACCENT_COLOR))

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._mouse_pressed = True
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._mouse_pressed = False
            self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._mouse_pressed and self._last_mouse_pos:
            delta = event.pos() - self._last_mouse_pos
            self.chart().scroll(-delta.x(), delta.y())
            self._last_mouse_pos = event.pos()
        else:
            if self.series and self.candles:
                pos = event.pos()
                chart_coords = self.chart().mapToValue(pos, self.series)
                x = chart_coords.x()
                nearest = min(self.candles, key=lambda c: abs(c['timestamp'] - x))
                self._hover_candle = nearest
                self._update_labels(nearest)
            else:
                self._hover_candle = None
                self._update_labels(None)
            self.viewport().update()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        mouse_pos = event.pos()
        chart_pos = self.chart().mapToValue(mouse_pos, self.series)
        self.chart().zoom(factor)
        after_zoom_pos = self.chart().mapToPosition(chart_pos, self.series)
        delta = mouse_pos - after_zoom_pos
        self.chart().scroll(delta.x(), -delta.y())
        super().wheelEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover_candle:
            painter = QPainter(self.viewport())
            painter.setPen(self.cross_pen)
            high_pt = self.chart().mapToPosition(QPointF(self._hover_candle['timestamp'], self._hover_candle['high']), self.series)
            low_pt = self.chart().mapToPosition(QPointF(self._hover_candle['timestamp'], self._hover_candle['low']), self.series)
            painter.drawLine(int(high_pt.x()), int(high_pt.y()), int(low_pt.x()), int(low_pt.y()))
            close_pt = self.chart().mapToPosition(QPointF(self._hover_candle['timestamp'], self._hover_candle['close']), self.series)
            painter.drawLine(0, int(close_pt.y()), self.viewport().width(), int(close_pt.y()))
            painter.setPen(QColor(ACCENT_COLOR))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(self.viewport().width() - 60, int(close_pt.y()), f"{self._hover_candle['close']:.2f}")
            painter.drawText(int(close_pt.x()), self.viewport().height() - 10,
                             QDateTime.fromMSecsSinceEpoch(int(self._hover_candle['timestamp'])).toString("HH:mm"))

    def format_volume(self, value):
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}K"
        else:
            return str(int(value))

    def format_money(self, value):
        abs_val = abs(value)
        if abs_val >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif abs_val >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif abs_val >= 1_000:
            return f"{value / 1_000:.2f}K"
        else:
            return f"{value:.2f}"

    def _update_labels(self, candle):
        labels = [
            self.open_label, self.close_label, self.change_label,
            self.high_label, self.low_label, self.rsi_label,
            self.volume_label, self.total_volume_label, self.money_flow_label,
            self.ma20_label, self.ma50_label, self.ma200_label,
        ]
        if candle is None:
            for lbl in labels:
                lbl.setText(lbl.text().split(":")[0] + ": -")
                lbl.setStyleSheet(f"background-color: {HIGHLIGHT_COLOR}; color: {TEXT_COLOR}; padding: 6px; border-radius: 4px;")
        else:
            self.open_label.setText(f"Açılış: {candle['open']:.2f}")
            self.close_label.setText(f"Kapanış: {candle['close']:.2f}")
            
            change = candle['close'] - candle['open']
            change_color = GREEN_COLOR if change >= 0 else RED_COLOR
            self.change_label.setText(f"Değişim: {change:+.2f}")
            self.change_label.setStyleSheet(f"background-color: {HIGHLIGHT_COLOR}; color: {change_color}; padding: 6px; border-radius: 4px;")
            
            self.high_label.setText(f"Üst Fitil: {candle['high']:.2f}")
            self.low_label.setText(f"Alt Fitil: {candle['low']:.2f}")
            
            rsi_color = RED_COLOR if candle['rsi'] <= 30 else GREEN_COLOR if candle['rsi'] >= 70 else ACCENT_COLOR
            self.rsi_label.setText(f"RSI: {candle['rsi']:.2f} ({candle['rsi_region']})")
            self.rsi_label.setStyleSheet(f"background-color: {HIGHLIGHT_COLOR}; color: {rsi_color}; padding: 6px; border-radius: 4px;")
            
            self.volume_label.setText(f"Hacim: {candle['formatted_volume']}")
            self.total_volume_label.setText(f"Toplam Hacim: {candle['formatted_total_volume']}")
            
            mf = self.format_money(candle['cumulative_money_flow'])
            color = GREEN_COLOR if candle['cumulative_money_flow'] >= 0 else RED_COLOR
            self.money_flow_label.setText(f"Para Akışı: {mf}")
            self.money_flow_label.setStyleSheet(f"background-color: {HIGHLIGHT_COLOR}; color: {color}; padding: 6px; border-radius: 4px;")
            
            self.ma20_label.setText(f"MA20: {candle['ma20']:.2f}" if 'ma20' in candle and pd.notna(candle['ma20']) else "MA20: -")
            self.ma50_label.setText(f"MA50: {candle['ma50']:.2f}" if 'ma50' in candle and pd.notna(candle['ma50']) else "MA50: -")
            self.ma200_label.setText(f"MA200: {candle['ma200']:.2f}" if 'ma200' in candle and pd.notna(candle['ma200']) else "MA200: -")

class StockChartTab(QWidget):
    def __init__(self, name, symbol):
        super().__init__()
        self.name = name
        self.symbol = symbol
        
        # Ana layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # Başlık
        title_label = QLabel(f"{self.name} ({self.symbol})")
        title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {ACCENT_COLOR};")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Kontrol paneli
        control_frame = QFrame()
        control_frame.setStyleSheet(f"background-color: {DARKER_BACKGROUND}; border-radius: 8px;")
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(15, 10, 15, 10)
        control_layout.setSpacing(20)
        
        # Veri Modu Seçimi
        self.mode_group = QGroupBox("Veri Modu")
        self.mode_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {HIGHLIGHT_COLOR};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
                color: {TEXT_COLOR};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
            }}
        """)
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(8)
        
        self.live_radio = QRadioButton("Canlı Veri")
        self.historical_radio = QRadioButton("Geçmiş Veri")
        self.live_radio.setChecked(True)
        
        for radio in [self.live_radio, self.historical_radio]:
            radio.setStyleSheet(f"""
                QRadioButton {{
                    color: {TEXT_COLOR};
                    padding: 4px;
                }}
                QRadioButton::indicator {{
                    width: 16px;
                    height: 16px;
                }}
            """)
            mode_layout.addWidget(radio)
            
        self.mode_group.setLayout(mode_layout)
        control_layout.addWidget(self.mode_group)
        
        # Tarih Seçimi
        self.date_group = QGroupBox("Tarih Seçimi")
        self.date_group.setStyleSheet(self.mode_group.styleSheet())
        date_layout = QHBoxLayout()
        date_layout.setSpacing(10)
        
        self.date_combo = QComboBox()
        self.date_combo.setEnabled(False)
        self.date_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid {HIGHLIGHT_COLOR};
                border-radius: 4px;
                padding: 6px;
                min-width: 120px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                width: 20px;
                border-left: none;
            }}
        """)
        
        self.view_button = QPushButton("Görüntüle")
        self.view_button.setEnabled(False)
        self.view_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:disabled {{
                background-color: {HIGHLIGHT_COLOR};
                color: #888;
            }}
            QPushButton:hover {{
                background-color: #3a7bd5;
            }}
        """)
        self.view_button.clicked.connect(self.update_chart)
        
        date_layout.addWidget(self.date_combo)
        date_layout.addWidget(self.view_button)
        self.date_group.setLayout(date_layout)
        control_layout.addWidget(self.date_group)
        
        control_layout.addStretch()
        main_layout.addWidget(control_frame)
        
        # Radio buton değişikliklerini dinle
        self.live_radio.toggled.connect(self.toggle_data_mode)
        
        # Veri göstergeleri
        indicators_frame = QFrame()
        indicators_frame.setStyleSheet(f"background-color: {DARKER_BACKGROUND}; border-radius: 8px;")
        grid = QGridLayout(indicators_frame)
        grid.setContentsMargins(15, 15, 15, 15)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(10)
        
        def create_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {HIGHLIGHT_COLOR};
                    color: {TEXT_COLOR};
                    padding: 6px;
                    border-radius: 4px;
                    font-family: 'Segoe UI';
                }}
            """)
            lbl.setFont(QFont("Segoe UI", 10))
            return lbl

        labels = [create_label(label + ": -") for label in [
            "Açılış", "Kapanış", "Değişim", "Üst Fitil", "Alt Fitil", "RSI", "Hacim",
            "Toplam Hacim", "Para Akışı", "MA20", "MA50", "MA200",
            "Pivot", "Destek 1", "Destek 2", "Direnç 1", "Direnç 2"
        ]]
        
        (self.open_label, self.close_label, self.change_label, self.high_label, self.low_label,
         self.rsi_label, self.volume_label, self.total_volume_label, self.money_flow_label,
         self.ma20_label, self.ma50_label, self.ma200_label,
         self.pivot_label, self.support1_label, self.support2_label,
         self.resistance1_label, self.resistance2_label) = labels

        # İlk 12 göstergeyi 3x4 grid'e yerleştir
        for i, lbl in enumerate(labels[:12]):
            grid.addWidget(lbl, i // 3, i % 3)
            
        # Pivot göstergeleri için alt kısım
        pivot_frame = QFrame()
        pivot_frame.setStyleSheet(f"background-color: {DARKER_BACKGROUND}; border-radius: 8px;")
        pivot_layout = QHBoxLayout(pivot_frame)
        pivot_layout.setContentsMargins(15, 10, 15, 10)
        pivot_layout.setSpacing(15)
        
        for lbl in labels[12:]:
            pivot_layout.addWidget(lbl)
            
        main_layout.addWidget(indicators_frame)
        main_layout.addWidget(pivot_frame)
        
        # Grafik
        self.chart = QChart()
        self.chart.setTheme(QChart.ChartThemeDark)
        
        # Özel arka plan gradient
        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setColorAt(0, QColor(DARK_BACKGROUND))
        gradient.setColorAt(1, QColor(DARKER_BACKGROUND))
        gradient.setCoordinateMode(QLinearGradient.ObjectMode)
        self.chart.setBackgroundBrush(QBrush(gradient))
        self.chart.setTitleBrush(QColor(TEXT_COLOR))
        self.chart.setTitle(f"{self.name} ({self.symbol})")
        self.chart.legend().setVisible(True)
        self.chart.legend().setLabelColor(QColor(TEXT_COLOR))
        self.chart.setMargins(QMargins(10, 10, 10, 10))

        self.series = QCandlestickSeries()
        self.series.setDecreasingColor(QColor(RED_COLOR))
        self.series.setIncreasingColor(QColor(GREEN_COLOR))
        self.series.setBodyOutlineVisible(False)
        self.series.setBodyWidth(0.8)
        self.chart.addSeries(self.series)

        # Hareketli ortalamalar için seriler
        self.ma20_series = self._create_ma_series(QColor("#FFD700"), "MA20")  # Gold
        self.ma50_series = self._create_ma_series(QColor("#FF69B4"), "MA50")  # Hot Pink
        self.ma200_series = self._create_ma_series(QColor("#00BFFF"), "MA200")  # Deep Sky Blue

        self.axisX = QDateTimeAxis()
        self.axisX.setFormat("HH:mm")
        self.axisX.setLabelsColor(QColor(TEXT_COLOR))
        self.chart.addAxis(self.axisX, Qt.AlignBottom)
        self.series.attachAxis(self.axisX)
        self.ma20_series.attachAxis(self.axisX)
        self.ma50_series.attachAxis(self.axisX)
        self.ma200_series.attachAxis(self.axisX)

        self.axisY = QValueAxis()
        self.axisY.setLabelFormat("%.2f")
        self.axisY.setLabelsColor(QColor(TEXT_COLOR))
        self.chart.addAxis(self.axisY, Qt.AlignLeft)
        self.series.attachAxis(self.axisY)
        self.ma20_series.attachAxis(self.axisY)
        self.ma50_series.attachAxis(self.axisY)
        self.ma200_series.attachAxis(self.axisY)

        self.chart_view = InteractiveChartView(
            self.chart, self.series,
            self.open_label, self.close_label, self.change_label, self.high_label,
            self.low_label, self.rsi_label, self.volume_label, self.total_volume_label,
            self.money_flow_label, self.ma20_label, self.ma50_label, self.ma200_label,
            self.pivot_label, self.support1_label, self.support2_label,
            self.resistance1_label, self.resistance2_label
        )
        self.chart_view.setStyleSheet("border: none;")
        main_layout.addWidget(self.chart_view, 1)
        
        self.setLayout(main_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_chart)
        self.timer.start(60000)
        
        self.load_historical_dates()
        self.update_chart()

    def _create_ma_series(self, color, name):
        series = QLineSeries()
        series.setName(name)
        series.setColor(color)
        pen = QPen(color, 2)
        pen.setCapStyle(Qt.RoundCap)
        series.setPen(pen)
        self.chart.addSeries(series)
        return series

    def toggle_data_mode(self, live_checked):
        self.date_combo.setEnabled(not live_checked)
        self.view_button.setEnabled(not live_checked)
        if live_checked:
            self.timer.start(60000)
            self.axisX.setFormat("HH:mm")
        else:
            self.timer.stop()
            self.axisX.setFormat("dd MMM")
        self.update_chart()

    def load_historical_dates(self):
        try:
            symbol = self.symbol + ".IS"
            stock = yf.Ticker(symbol)
            
            end_date = datetime.now(timezone("Europe/Istanbul"))
            start_date = end_date - timedelta(days=45)
            
            data = stock.history(start=start_date, end=end_date, interval="1d")
            
            if not data.empty:
                valid_dates = []
                for date in data.index:
                    if not pd.isna(data.loc[date, 'Close']):
                        date_str = date.strftime('%Y-%m-%d')
                        valid_dates.append(date_str)
                
                self.date_combo.clear()
                self.date_combo.addItems(valid_dates[-30:])
        
        except Exception as e:
            print(f"Tarih yükleme hatası: {e}")

    def filter_market_hours(self, data):
        if data.empty:
            return data
            
        try:
            if len(data.index.normalize().unique()) < len(data.index):
                if data.index.tz is None:
                    data.index = data.index.tz_localize('UTC')
                data.index = data.index.tz_convert('Europe/Istanbul')
                return data.between_time('09:55', '18:05')
            return data
        except Exception as e:
            print(f"Zaman filtreleme hatası: {e}")
            return data

    def update_chart(self):
        try:
            now = datetime.now(timezone("Europe/Istanbul"))
            symbol = self.symbol + ".IS"
            stock = yf.Ticker(symbol)
            
            if self.live_radio.isChecked():
                try:
                    full_data = stock.history(period="1y", interval="1d")
                    full_data = full_data[~pd.isna(full_data['Close'])]
                    
                    if len(full_data) < 200:
                        full_data = stock.history(period="2y", interval="1d")
                        full_data = full_data[~pd.isna(full_data['Close'])]
                    
                    full_data = full_data.iloc[-200:]
                    
                    data = stock.history(period="1d", interval="1m")
                    if data.empty:
                        data = stock.history(start=(now - timedelta(days=1)).strftime('%Y-%m-%d'), interval="1m")
                    data = self.filter_market_hours(data)
                    
                    full_data["MA20"] = full_data["Close"].rolling(window=20, min_periods=1).mean()
                    full_data["MA50"] = full_data["Close"].rolling(window=50, min_periods=1).mean()
                    full_data["MA200"] = full_data["Close"].rolling(window=200, min_periods=1).mean()
                    full_data["RSI"] = calculate_rsi(full_data)
                    
                    last_ma_values = full_data.iloc[-1][["MA20", "MA50", "MA200", "RSI"]]
                    data = data.assign(**{col: last_ma_values[col] for col in ["MA20", "MA50", "MA200", "RSI"]})
                    
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Canlı veri alınamadı: {str(e)}")
                    return
            else:
                selected_date = self.date_combo.currentText()
                if not selected_date:
                    return
                
                try:
                    target_date = pd.to_datetime(selected_date)
                    
                    data = stock.history(
                        start=target_date - timedelta(days=1),
                        end=target_date + timedelta(days=1),
                        interval="1d"
                    )
                    
                    if data.empty:
                        QMessageBox.warning(self, "Uyarı", f"{selected_date} tarihli veri bulunamadı")
                        return
                    
                    data = data[data.index.normalize() == target_date.normalize()]
                    
                    if data.empty:
                        for days_back in range(1, 6):
                            prev_date = target_date - timedelta(days=days_back)
                            prev_data = stock.history(
                                start=prev_date - timedelta(days=1),
                                end=prev_date + timedelta(days=1),
                                interval="1d"
                            )
                            if not prev_data.empty:
                                data = prev_data[prev_data.index.normalize() == prev_date.normalize()]
                                if not data.empty:
                                    QMessageBox.information(
                                        self, "Bilgi", 
                                        f"{selected_date} tarihinde işlem yok. En yakın işlem günü ({prev_date.date()}) gösteriliyor."
                                    )
                                    target_date = prev_date
                                    break
                        
                        if data.empty:
                            QMessageBox.warning(self, "Uyarı", f"{selected_date} tarihi için veri bulunamadı")
                            return
                    
                    full_data = stock.history(
                        start=target_date - timedelta(days=300),
                        end=target_date + timedelta(days=1),
                        interval="1d"
                    )
                    
                    full_data = full_data[~pd.isna(full_data['Close'])]
                    full_data = full_data.iloc[-200:]
                    
                    full_data["MA20"] = full_data["Close"].rolling(window=20, min_periods=1).mean()
                    full_data["MA50"] = full_data["Close"].rolling(window=50, min_periods=1).mean()
                    full_data["MA200"] = full_data["Close"].rolling(window=200, min_periods=1).mean()
                    full_data["RSI"] = calculate_rsi(full_data)
                    
                    last_ma_values = full_data.iloc[-1][["MA20", "MA50", "MA200", "RSI"]]
                    data = data.assign(**{col: last_ma_values[col] for col in ["MA20", "MA50", "MA200", "RSI"]})
                
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Geçmiş veri alınamadı: {str(e)}")
                    return
            
            if data.empty:
                QMessageBox.warning(self, "Uyarı", f"{symbol} için veri bulunamadı")
                return

            self.series.clear()
            self.ma20_series.clear()
            self.ma50_series.clear()
            self.ma200_series.clear()
            self.chart_view.candles.clear()

            cumulative_money_flow = 0
            min_p, max_p = float("inf"), float("-inf")

            for idx, row in data.iterrows():
                if self.historical_radio.isChecked():
                    dt = datetime.combine(idx.to_pydatetime().date(), datetime.min.time())
                else:
                    dt = idx.to_pydatetime()
                
                ts = QDateTime(dt).toMSecsSinceEpoch()
                o, h, l, c, v = row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]
                rsi = row.get("RSI", float('nan'))
                ma20 = row.get("MA20", float('nan'))
                ma50 = row.get("MA50", float('nan'))
                ma200 = row.get("MA200", float('nan'))
                rsi_region = "Aşırı Alım" if rsi >= 70 else "Aşırı Satım" if rsi <= 30 else "Normal"
                money_flow = c * v
                cumulative_money_flow += money_flow
                formatted_volume = self.chart_view.format_volume(v)
                total_volume = data.loc[:idx, "Volume"].sum()
                formatted_total_volume = self.chart_view.format_volume(total_volume)
                
                self.series.append(QCandlestickSet(o, h, l, c, ts))
                
                if pd.notna(ma20):
                    self.ma20_series.append(ts, ma20)
                if pd.notna(ma50):
                    self.ma50_series.append(ts, ma50)
                if pd.notna(ma200):
                    self.ma200_series.append(ts, ma200)
                
                self.chart_view.candles.append({
                    "timestamp": ts, "open": o, "high": h, "low": l, "close": c,
                    "volume": v, "rsi": rsi, "rsi_region": rsi_region,
                    "formatted_volume": formatted_volume,
                    "total_volume": total_volume,
                    "formatted_total_volume": formatted_total_volume,
                    "cumulative_money_flow": cumulative_money_flow,
                    "ma20": ma20, "ma50": ma50, "ma200": ma200
                })
                min_p = min(min_p, l)
                max_p = max(max_p, h)

            if not data.empty:
                try:
                    if self.historical_radio.isChecked():
                        min_time = QDateTime(data.index[0].to_pydatetime().date(), QTime(0, 0))
                        max_time = QDateTime(data.index[0].to_pydatetime().date(), QTime(23, 59))
                        self.axisX.setRange(min_time, max_time)
                    else:
                        self.axisX.setRange(
                            QDateTime(data.index[0].to_pydatetime()),
                            QDateTime(data.index[-1].to_pydatetime())
                        )
                    self.axisY.setRange(min_p * 0.98, max_p * 1.02)
                except Exception as e:
                    print(f"Eksen ayarlama hatası: {e}")

            # Pivot hesaplamaları
            if self.live_radio.isChecked():
                pivot_data = data[data.index.date == now.date()]
            else:
                selected_date = pd.to_datetime(self.date_combo.currentText()).date()
                pivot_data = data[data.index.date == selected_date]

            if pivot_data.empty:
                pivot_data = data

            high = pivot_data["High"].max()
            low = pivot_data["Low"].min()
            close = pivot_data["Close"].iloc[-1] if not pivot_data.empty else 0
            pivot = (high + low + close) / 3
            s1 = (2 * pivot) - high
            s2 = pivot - (high - low)
            r1 = (2 * pivot) - low
            r2 = pivot + (high - low)

            self.pivot_label.setText(f"Pivot: {pivot:.2f}")
            self.support1_label.setText(f"Destek 1: {s1:.2f}")
            self.support2_label.setText(f"Destek 2: {s2:.2f}")
            self.resistance1_label.setText(f"Direnç 1: {r1:.2f}")
            self.resistance2_label.setText(f"Direnç 2: {r2:.2f}")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Grafik güncellenirken hata oluştu: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BIST Hisse Grafik Analiz Aracı")
        
        # Pencere ikonu ayarı
        try:
            self.setWindowIcon(QIcon('icon.png'))  # Kendi ikon dosyanızı kullanabilirsiniz
        except:
            pass  # İkon ayarlanamazsa hata verme
        
        # Ana pencere stil ayarları
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {DARK_BACKGROUND};
            }}
            QTabWidget::pane {{
                border: none;
                background: {DARK_BACKGROUND};
            }}
            QTabBar::tab {{
                background: {DARKER_BACKGROUND};
                color: {TEXT_COLOR};
                padding: 8px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {ACCENT_COLOR};
                color: white;
            }}
            QTabBar::tab:hover {{
                background: {HIGHLIGHT_COLOR};
            }}
        """)
        
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # Arama paneli
        search_frame = QFrame()
        search_frame.setStyleSheet(f"background-color: {DARKER_BACKGROUND}; border-radius: 8px;")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(15, 10, 15, 10)
        search_layout.setSpacing(15)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Hisse kodu girin (örnek: THYAO, SISE...)")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid {HIGHLIGHT_COLOR};
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT_COLOR};
            }}
        """)
        
        self.search_button = QPushButton("Ara")
        self.search_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 14px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: #3a7bd5;
            }}
        """)
        self.search_button.clicked.connect(self.search_stock)
        self.search_box.returnPressed.connect(self.search_stock)
        
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.search_button)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        main_layout.addWidget(search_frame)
        main_layout.addWidget(self.tabs, 1)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def search_stock(self):
        symbol = self.search_box.text().upper().strip()
        if not symbol:
            return
            
        if symbol not in [self.tabs.tabText(i) for i in range(self.tabs.count())]:
            try:
                # Hisse adını almak için bir sorgu yapalım
                full_symbol = symbol + ".IS"
                stock = yf.Ticker(full_symbol)
                info = stock.info
                name = info.get('shortName', symbol)
                
                new_tab = StockChartTab(name, symbol)
                tab_index = self.tabs.addTab(new_tab, symbol)
                self.tabs.setCurrentIndex(tab_index)
                self.search_box.clear()
                
                # Başarılı ekleme sonrası geçici mesaj
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setText(f"{name} ({symbol}) hissesi eklendi")
                msg.setWindowTitle("Başarılı")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {DARK_BACKGROUND};
                        color: {TEXT_COLOR};
                    }}
                    QLabel {{
                        color: {TEXT_COLOR};
                    }}
                """)
                msg.exec_()
                
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"{symbol} hissesi eklenirken hata oluştu: {str(e)}")
        else:
            # Eğer sekme zaten varsa, o sekmeye geç
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == symbol:
                    self.tabs.setCurrentIndex(i)
                    break

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            QMessageBox.information(self, "Bilgi", "En az bir sekme açık olmalıdır.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Genel uygulama stili
    app.setStyle("Fusion")
    
    # Koyu tema paleti
    palette = app.palette()
    palette.setColor(palette.Window, QColor(DARK_BACKGROUND))
    palette.setColor(palette.WindowText, QColor(TEXT_COLOR))
    palette.setColor(palette.Base, QColor(DARKER_BACKGROUND))
    palette.setColor(palette.AlternateBase, QColor(DARK_BACKGROUND))
    palette.setColor(palette.ToolTipBase, QColor(ACCENT_COLOR))
    palette.setColor(palette.ToolTipText, Qt.white)
    palette.setColor(palette.Text, QColor(TEXT_COLOR))
    palette.setColor(palette.Button, QColor(DARKER_BACKGROUND))
    palette.setColor(palette.ButtonText, QColor(TEXT_COLOR))
    palette.setColor(palette.BrightText, Qt.red)
    palette.setColor(palette.Highlight, QColor(ACCENT_COLOR))
    palette.setColor(palette.HighlightedText, Qt.white)
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())