import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from pytz import timezone
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QLabel, QGridLayout, QHBoxLayout, QLineEdit, QPushButton,
    QRadioButton, QComboBox, QButtonGroup, QGroupBox, QMessageBox
)
from PyQt5.QtChart import (
    QChart, QChartView, QCandlestickSeries, QCandlestickSet,
    QDateTimeAxis, QValueAxis
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QPointF, QDate
from PyQt5.QtGui import QPainter, QColor, QPen, QFont

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

        (self.open_label, self.close_label, self.change_label,
         self.high_label, self.low_label, self.rsi_label,
         self.volume_label, self.total_volume_label,
         self.money_flow_label, self.ma20_label, self.ma50_label,
         self.ma200_label, self.pivot_label, self.support1_label,
         self.support2_label, self.resistance1_label,
         self.resistance2_label) = labels

        self.cross_pen = QPen(Qt.DotLine)
        self.cross_pen.setColor(QColor("white"))

        self._hover_candle = None
        self._mouse_pressed = False
        self._last_mouse_pos = None

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
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Consolas", 9))
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
                lbl.setStyleSheet("background-color: white; color: black; padding: 4px; border: 1px solid gray;")
        else:
            self.open_label.setText(f"Açılış: {candle['open']:.2f}")
            self.close_label.setText(f"Kapanış: {candle['close']:.2f}")
            self.change_label.setText(f"Değişim: {(candle['close'] - candle['open']):+.2f}")
            self.high_label.setText(f"Üst Fitil: {candle['high']:.2f}")
            self.low_label.setText(f"Alt Fitil: {candle['low']:.2f}")
            self.rsi_label.setText(f"RSI: {candle['rsi']:.2f} ({candle['rsi_region']})")
            self.volume_label.setText(f"Hacim: {candle['formatted_volume']}")
            self.total_volume_label.setText(f"Toplam Hacim: {candle['formatted_total_volume']}")
            mf = self.format_money(candle['cumulative_money_flow'])
            color = "green" if candle['cumulative_money_flow'] >= 0 else "red"
            self.money_flow_label.setText(f"Para Giriş+Çıkışı: {mf}")
            self.money_flow_label.setStyleSheet(f"background-color: white; color: {color}; padding: 4px; border: 1px solid gray;")
            self.ma20_label.setText(f"MA20: {candle['ma20']:.2f}" if pd.notna(candle['ma20']) else "MA20: -")
            self.ma50_label.setText(f"MA50: {candle['ma50']:.2f}" if pd.notna(candle['ma50']) else "MA50: -")
            self.ma200_label.setText(f"MA200: {candle['ma200']:.2f}" if pd.notna(candle['ma200']) else "MA200: -")

class StockChartTab(QWidget):
    def __init__(self, name, symbol):
        super().__init__()
        self.name = name
        self.symbol = symbol
        layout = QVBoxLayout()

        def create_label(text): 
            lbl = QLabel(text)
            lbl.setStyleSheet("background-color: white; color: black; padding: 4px; border: 1px solid gray;")
            lbl.setFont(QFont("Consolas", 10))
            return lbl

        labels = [create_label(label + ": -") for label in [
            "Açılış", "Kapanış", "Değişim", "Üst Fitil", "Alt Fitil", "RSI", "Hacim",
            "Toplam Hacim", "Para Giriş+Çıkışı", "MA20", "MA50", "MA200",
            "Pivot", "Destek 1", "Destek 2", "Direnç 1", "Direnç 2"
        ]]
        (self.open_label, self.close_label, self.change_label, self.high_label, self.low_label,
         self.rsi_label, self.volume_label, self.total_volume_label, self.money_flow_label,
         self.ma20_label, self.ma50_label, self.ma200_label,
         self.pivot_label, self.support1_label, self.support2_label,
         self.resistance1_label, self.resistance2_label) = labels

        # Kontrol paneli
        control_layout = QHBoxLayout()
        
        # Veri Modu Seçimi
        self.mode_group = QGroupBox("Veri Modu")
        mode_layout = QVBoxLayout()
        self.live_radio = QRadioButton("Canlı Veri")
        self.historical_radio = QRadioButton("Geçmiş Veri")
        self.live_radio.setChecked(True)
        mode_layout.addWidget(self.live_radio)
        mode_layout.addWidget(self.historical_radio)
        self.mode_group.setLayout(mode_layout)
        control_layout.addWidget(self.mode_group)
        
        # Tarih Seçimi
        self.date_group = QGroupBox("Tarih Seçimi")
        date_layout = QHBoxLayout()
        self.date_combo = QComboBox()
        self.date_combo.setEnabled(False)
        self.view_button = QPushButton("Görüntüle")
        self.view_button.setEnabled(False)
        self.view_button.clicked.connect(self.update_chart)
        date_layout.addWidget(self.date_combo)
        date_layout.addWidget(self.view_button)
        self.date_group.setLayout(date_layout)
        control_layout.addWidget(self.date_group)
        
        # Radio buton değişikliklerini dinle
        self.live_radio.toggled.connect(self.toggle_data_mode)
        layout.addLayout(control_layout)

        grid = QGridLayout()
        for i, lbl in enumerate(labels):
            grid.addWidget(lbl, i // 3, i % 3)
        layout.addLayout(grid)

        self.chart = QChart()
        self.chart.setTheme(QChart.ChartThemeDark)
        self.chart.setBackgroundBrush(QColor("#1e1e1e"))
        self.chart.setTitleBrush(QColor("white"))
        self.chart.setTitle(f"{self.name} ({self.symbol})")

        self.series = QCandlestickSeries()
        self.series.setDecreasingColor(QColor("red"))
        self.series.setIncreasingColor(QColor("green"))
        self.chart.addSeries(self.series)

        self.axisX = QDateTimeAxis()
        self.axisX.setFormat("HH:mm")
        self.chart.addAxis(self.axisX, Qt.AlignBottom)
        self.series.attachAxis(self.axisX)

        self.axisY = QValueAxis()
        self.axisY.setLabelFormat("%.2f")
        self.chart.addAxis(self.axisY, Qt.AlignLeft)
        self.series.attachAxis(self.axisY)

        self.chart_view = InteractiveChartView(
            self.chart, self.series,
            self.open_label, self.close_label, self.change_label, self.high_label,
            self.low_label, self.rsi_label, self.volume_label, self.total_volume_label,
            self.money_flow_label, self.ma20_label, self.ma50_label, self.ma200_label,
            self.pivot_label, self.support1_label, self.support2_label,
            self.resistance1_label, self.resistance2_label
        )
        layout.addWidget(self.chart_view)
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_chart)
        self.timer.start(60000)
        
        self.load_historical_dates()
        self.update_chart()

    def toggle_data_mode(self, live_checked):
        self.date_combo.setEnabled(not live_checked)
        self.view_button.setEnabled(not live_checked)
        if live_checked:
            self.timer.start(60000)
        else:
            self.timer.stop()
        self.update_chart()

    def load_historical_dates(self):
        try:
            symbol = self.symbol + ".IS"
            stock = yf.Ticker(symbol)
            
            end_date = datetime.now(timezone("Europe/Istanbul"))
            start_date = end_date - timedelta(days=365)
            
            # 1d'lik verileri çek (1 yıllık günlük veri)
            data = stock.history(start=start_date, end=end_date, interval="1d")
            
            if not data.empty:
                dates = [str(date.date()) for date in data.index]
                self.date_combo.clear()
                self.date_combo.addItems(dates)
            
        except Exception as e:
            print(f"Tarih yükleme hatası: {e}")

    def filter_market_hours(self, data):
        if data.empty:
            return data
            
        try:
            if data.index.tz is None:
                data.index = data.index.tz_localize('UTC')
            data.index = data.index.tz_convert('Europe/Istanbul')
            
            return data.between_time('09:55', '18:05')
        except Exception as e:
            print(f"Zaman filtreleme hatası: {e}")
            return data

    def update_chart(self):
        try:
            now = datetime.now(timezone("Europe/Istanbul"))
            symbol = self.symbol + ".IS"
            stock = yf.Ticker(symbol)
            
            if self.live_radio.isChecked():
                # Canlı veri modu - son 1 günün 1m'lik verisini çek
                try:
                    data = stock.history(period="1d", interval="1m")
                    if data.empty:
                        data = stock.history(start=(now - timedelta(days=1)).strftime('%Y-%m-%d'), interval="1m")
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Canlı veri alınamadı: {str(e)}")
                    return
            else:
                # Geçmiş veri modu
                selected_date = self.date_combo.currentText()
                if not selected_date:
                    return
                
                target_date = pd.to_datetime(selected_date)
                
                # Geçmiş tarihler için günlük veri çek
                try:
                    data = stock.history(start=target_date, end=target_date + timedelta(days=1), interval="1d")
                    
                    # Eğer 1d verisi de yoksa uyarı ver
                    if data.empty:
                        QMessageBox.warning(self, "Uyarı", f"{selected_date} tarihli veri bulunamadı")
                        return
                    
                    # Günlük veriyi mum grafiğine uygun hale getir
                    if not data.empty:
                        data = data.resample('1T').ffill()  # 1 dakikalık aralıklarla doldur
                
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Geçmiş veri alınamadı: {str(e)}")
                    return
            
            if data.empty:
                QMessageBox.warning(self, "Uyarı", f"{symbol} için veri bulunamadı")
                return

            # Zaman filtrelemesi uygula
            data = self.filter_market_hours(data)
            
            if data.empty:
                QMessageBox.warning(self, "Uyarı", "Filtrelenmiş veri boş")
                return

            self.series.clear()
            self.chart_view.candles.clear()

            data["RSI"] = calculate_rsi(data)
            data["MA20"] = data["Close"].rolling(window=20).mean()
            data["MA50"] = data["Close"].rolling(window=50).mean()
            data["MA200"] = data["Close"].rolling(window=200).mean()

            cumulative_money_flow = 0
            min_p, max_p = float("inf"), float("-inf")

            for idx, row in data.iterrows():
                ts = QDateTime(idx.to_pydatetime()).toMSecsSinceEpoch()
                o, h, l, c, v = row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]
                rsi = row["RSI"]
                ma20, ma50, ma200 = row["MA20"], row["MA50"], row["MA200"]
                rsi_region = "Aşırı Alım" if rsi >= 70 else "Aşırı Satım" if rsi <= 30 else "Normal"
                money_flow = c * v
                cumulative_money_flow += money_flow
                formatted_volume = self.chart_view.format_volume(v)
                total_volume = data.loc[:idx, "Volume"].sum()
                formatted_total_volume = self.chart_view.format_volume(total_volume)
                self.series.append(QCandlestickSet(o, h, l, c, ts))
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
                    self.axisX.setRange(QDateTime(data.index[0].to_pydatetime()), 
                                      QDateTime(data.index[-1].to_pydatetime()))
                    self.axisY.setRange(min_p * 0.995, max_p * 1.005)
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
            close = pivot_data["Close"].iloc[-1] if not pivot_data.empty else 0  # .iloc kullanıldı
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
        self.setWindowTitle("İnteraktif BIST Grafik (Arama + RSI + MA + Pivot)")

        self.resize(1200, 800)

        self.tabs = QTabWidget(self)

        # Arama kutusu ve butonu
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Hisse kodu girin (örnek: THYAO)...")
        self.search_button = QPushButton("Ara")
        self.search_button.clicked.connect(self.search_stock)
        self.search_box.returnPressed.connect(self.search_stock)
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.search_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def search_stock(self):
        symbol = self.search_box.text().upper()
        if symbol and symbol not in [self.tabs.tabText(i) for i in range(self.tabs.count())]:
            try:
                new_tab = StockChartTab(symbol, symbol)
                self.tabs.addTab(new_tab, symbol)
                self.search_box.clear()
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"{symbol} hissesi eklenirken hata oluştu: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

    """
    1. ComboBox'da sadece geçmiş 30 günün verisi sunulacak. Çünkü Yahoo sadece 30 günlük veri sağlıyor.
    2. Kanal destek ve direnci
    3. MACD
    """