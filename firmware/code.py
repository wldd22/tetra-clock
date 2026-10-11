import os
import time
from dataclasses import dataclass
from threading import main_thread
from urllib.parse import scheme_chars

import rtc
import wifi
import socketpool
import board
import pwmio
import touchio
import vectorio
import digitalio
import displayio
import terminalio
import adafruit_ntp
import adafruit_displayio_ssd1306
from adafruit_display_shapes.line import Line
from i2cdisplaybus import I2CDisplayBus
from adafruit_display_text import label

# -------------------------
# Configuration
# -------------------------

WIDTH = 128
HEIGHT = 32
OLED_ADDRESS = 0x3C

TIME_OFFSET_SECONDS = 5 * 3600 + 30 * 60
WIFI_RETRY_SECONDS = 30
NTP_RETRY_SECONDS = 3600

MONTHS = (
    "Jan", "Feb", "Mar", "Apr",
    "May", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec"
)

# -------------------------
# Capacitive touch and buzzer setup
# -------------------------

TOUCH_PINS = [board.D0, board.D1, board.D2, board.D3] # D0-D3
BUZZER_PIN = board.D7

touch = [touchio.TouchIn(TOUCH_PIN) for TOUCH_PIN in TOUCH_PINS]

buzzer = pwmio.PWMOut(
    BUZZER_PIN,
    frequency=2000,
    duty_cycle=0
)

# -------------------------
# OLED setup
# -------------------------

displayio.release_displays()

i2c = board.I2C()

display_bus = I2CDisplayBus(
    i2c,
    device_address=OLED_ADDRESS
)

display = adafruit_displayio_ssd1306.SSD1306(
    display_bus,
    width=WIDTH,
    height=HEIGHT
)

# -------------------------
# Screen setup
# -------------------------

ALARM_ICON_BITS = displayio.OnDiskBitmap("/alarm_icon.bmp")
EDIT_ICON_BITS = displayio.OnDiskBitmap("/edit_icon.bmp")
ARROWS_BITS = displayio.OnDiskBitmap("/arrows.bmp")
CHECKMARK_BITS = displayio.OnDiskBitmap("/checkmark.bmp")

alarm_data = {
    "enabled": False,
    "snooze_enabled": False,
    "alarm_time": (7, 0)  # Hour, Minute
}

class Screen:
    def __init__(self):
        self.active = False
        self.group = displayio.Group()
        self.layers = {}
        self.create_layers()
        for name, group in self.layers.items():
            self.group.append(group)

    def create_layers(self):
        pass

    def on_enter(self):
        self.active = True
        display.root_group = self.group

    def on_exit(self):
        self.active = False

    def handle_input(self, button_idx):
        pass

    def update(self):
        pass

class HomeScreen(Screen):
    def __init__(self):
        super().__init__()

    def create_layers(self):
        # ISO timestamp, centred on the display
        self.layers["datetime_text"] = label.Label(
            terminalio.FONT,
            text="XXXX-XX-XX XX:XX:XX",
            color=0xFFFFFF,
            scale=1,
            x=7,
            y=15
        )

        # Status text, below datetime
        self.layers["status_text"] = label.Label(
            terminalio.FONT,
            text="",
            color=0xFFFFFF,
            scale=1,
            x=0,
            y=27
        )

        # Alarm icon
        self.layers["alarm_icon"] = displayio.TileGrid(
            bitmap=ALARM_ICON_BITS,
            pixel_shader=ALARM_ICON_BITS.pixel_shader,
            x=118,
            y=0
        )
        self.layers["alarm_icon"].hidden = not alarm_data["enabled"]

        # Edit icon
        self.layers["edit_icon"] = displayio.TileGrid(
            bitmap=EDIT_ICON_BITS,
            pixel_shader=EDIT_ICON_BITS.pixel_shader,
            x=118,
            y=23
        )

    def handle_input(self, button_idx: int):
        if button_idx == 0: # Toggle alarm
            if alarm_data["enabled"]:
                alarm_data["enabled"] = False
            else:
                alarm_data["enabled"] = True
        elif button_idx == 1:
            pass
        elif button_idx == 2: # Edit alarm
            screens["home_screen"].on_exit()
            screens["alarm_screen"].on_enter()
        elif button_idx == 3:
            pass

    def update(self):
        if time_is_valid:
            now = time.localtime()
            self.layers["datetime_text"].text = f"{now.tm_year:04d}-{now.tm_mon:02d}-{now.tm_mday:02d} "
            f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
        else:
            self.layers["datetime_text"].text = "XXXX-XX-XX XX:XX:XX"
        self.layers["alarm_icon"].hidden = not alarm_data["enabled"]

class AlarmScreen(Screen):
    def __init__(self):
        super().__init__()
        self.selected_field = 0  # 0: hour, 1: minute
        self.mode = 0

    def create_layers(self):
        # Time display
        self.layers["alarm_time_text"] = label.Label(
            terminalio.FONT,
            text=f"{alarm_data['alarm_time'][0]:02d}:{alarm_data['alarm_time'][1]:02d}",
            color=0xFFFFFF,
            scale=2,
            x=7,
            y=17
        )

        # Arrow indicators
        self.layers["arrows"] = displayio.TileGrid(
            bitmap=ARROWS_BITS,
            pixel_shader=ARROWS_BITS.pixel_shader,
            x=16,
            y=1
        )
        self.layers["arrows"].hidden = self.mode != 0

        # Selection indicators (underline the selected field)
        self.layers["hour_selection"] = Line(7, 29, 28, 29, color=0xFFFFFF)
        self.layers["hour_selection"].hidden = self.selected_field != 0
        self.layers["minute_selection"] = Line(43, 29, 64, 29, color=0xFFFFFF)
        self.layers["minute_selection"].hidden = self.selected_field != 1

        # Alarm enabled/disabled status
        self.layers["alarm_status_text"] = label.Label(
            terminalio.FONT,
            text="Alarm: " + ("ON" if alarm_data["enabled"] else "OFF"),
            color=0xFFFFFF,
            scale=1,
            x=80 if alarm_data["enabled"] else 74,
            y=5
        )

        # Snooze enabled/disabled status
        self.layers["snooze_status_text"] = label.Label(
            terminalio.FONT,
            text="Snooze: " + ("ON" if alarm_data["snooze_enabled"] else "OFF"),
            color=0xFFFFFF,
            scale=1,
            x=74 if alarm_data["snooze_enabled"] else 68,
            y=15
        )

        # Checkmark icon
        self.layers["checkmark"] = displayio.TileGrid(
            bitmap=CHECKMARK_BITS,
            pixel_shader=CHECKMARK_BITS.pixel_shader,
            x=119,
            y=24
        )

    def handle_input(self, button_idx: int):
        # Buttons:
        # 10
        # 32
        # Mode 0:
        # 0 - Decrease selection
        # 1 - Increase selection
        # 2 - Move to mode 1
        # 3 - Switch selected_field (H/M)
        # Mode 1:
        # 0 - Toggle snooze enabled
        # 1 - Toggle alarm enabled
        # 2 - Exit alarm view
        # 3 - Move to mode 0
        if self.mode == 0:
            if button_idx == 0:
                # Decrease the selected field (hour or minute)
                # Wrap around if it goes below 0
                current_value = alarm_data["alarm_time"][self.selected_field]
                alarm_data["alarm_time"][self.selected_field] = (current_value - 1) % (24 if self.selected_field == 0 else 60)
            elif button_idx == 1:
                # Increase the selected field (hour or minute)
                # Wrap around if it goes above 23/59
                current_value = alarm_data["alarm_time"][self.selected_field]
                alarm_data["alarm_time"][self.selected_field] = (current_value + 1) % (24 if self.selected_field == 0 else 60)
            elif button_idx == 2:
                # Move to mode 1
                self.mode = 1
            elif button_idx == 3:
                # Switch selected field (hour <-> minute)
                self.selected_field = 1 - self.selected_field
        elif self.mode == 1:
            if button_idx == 0:
                # Toggle snooze enabled
                alarm_data["snooze_enabled"] = not alarm_data["snooze_enabled"]
            elif button_idx == 1:
                # Toggle alarm enabled
                alarm_data["enabled"] = not alarm_data["enabled"]
            elif button_idx == 2:
                # Exit alarm view
                self.mode = 0
                screens["alarm_screen"].on_exit()
                screens["home_screen"].on_enter()
            elif button_idx == 3:
                # Move to mode 0
                self.mode = 0

    def update(self):
        self.layers["arrows"].hidden = self.mode != 0

        self.layers["hour_selection"].hidden = self.selected_field != 0 or self.mode == 0
        self.layers["minute_selection"].hidden = self.selected_field != 1 or self.mode == 0

        self.layers["alarm_time_text"].text = f"{alarm_data['alarm_time'][0]:02d}:{alarm_data['alarm_time'][1]:02d}"

        self.layers["alarm_status_text"].text = "Alarm: " + ("ON" if alarm_data["enabled"] else "OFF")
        self.layers["alarm_status_text"].x = 80 if alarm_data["enabled"] else 74
        self.layers["snooze_status_text"].text = "Snooze: " + ("ON" if alarm_data["snooze_enabled"] else "OFF")
        self.layers["snooze_status_text"].x = 74 if alarm_data["snooze_enabled"] else 68

screens = {
    "home_screen": HomeScreen(),
    "alarm_screen": AlarmScreen()
}

screens["home_screen"].on_enter()

# -------------------------
# Network and clock setup
# -------------------------

pool = None
ntp = None

time_is_valid = False
last_wifi_attempt = -WIFI_RETRY_SECONDS
last_ntp_attempt = -NTP_RETRY_SECONDS

screens["home_screen"].layers["status_text"].text = "Initialising..."

def synchronize_time():
    """Connect to Wi-Fi if needed and set the RTC from NTP."""
    global pool, ntp, time_is_valid

    try:
        if not wifi.radio.connected:
            print("Connecting to Wi-Fi...")
            screens["home_screen"].layers["status_text"].text = "Connecting to Wi-Fi..."

            ssid = os.getenv("CIRCUITPY_WIFI_SSID")
            password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

            if not ssid or not password:
                raise RuntimeError(
                    "Set Wi-Fi credentials in settings.toml"
                )

            wifi.radio.connect(ssid, password)
        if pool is None:
            pool = socketpool.SocketPool(wifi.radio)

        if ntp is None:
            ntp = adafruit_ntp.NTP(
                pool,
                tz_offset=0,
                cache_seconds=0
            )

        print("Requesting NTP time...")
        screens["home_screen"].layers["status_text"].text = "Requesting NTP time..."

        # NTP supplies UTC.
        utc = ntp.datetime

        # Convert UTC calendar time to an epoch, then apply local timezone.
        utc_seconds = time.mktime(utc)
        local_time = time.localtime(
            utc_seconds + TIME_OFFSET_SECONDS
        )

        # CircuitPython's system RTC now holds local wall-clock time.
        rtc.RTC().datetime = local_time

        time_is_valid = True

        print("Time synchronised:", local_time)
        screens["home_screen"].layers["status_text"].text = f"Time synchronised"

    except Exception as error:
        print("Synchronisation failed:", error)
        screens["home_screen"].layers["status_text"].text = f"Syncing failed"


# -------------------------
# Main loop
# -------------------------

while True:
    now_ticks = time.monotonic()

    # Attempt synchronization on startup and retry after failure.
    if not time_is_valid:
        if now_ticks - last_wifi_attempt >= WIFI_RETRY_SECONDS:
            last_wifi_attempt = now_ticks
            last_ntp_attempt = now_ticks
            synchronize_time()

    # Refresh from NTP periodically after the first success.
    elif now_ticks - last_ntp_attempt >= NTP_RETRY_SECONDS:
        last_ntp_attempt = now_ticks
        synchronize_time()

    # Alarm screen's touch input is handled and it is updated, if it is active
    if screens["alarm_screen"].active:
        for button_idx, touch_input in enumerate(touch):
            if touch_input.value:
                screens["alarm_screen"].handle_input(button_idx)
        screens["alarm_screen"].update()

    # Home screen's touch input is handled if it is active, and it is updated either way
    if screens["home_screen"].active:
        for button_idx, touch_input in enumerate(touch):
            if touch_input.value:
                screens["home_screen"].handle_input(button_idx)
    screens["home_screen"].update()

    # # Handle touch input and buzzer output
    # if touch[0].value:
    #     buzzer.duty_cycle = 32768  # Buzzer ON
    # else:
    #     buzzer.duty_cycle = 0  # Buzzer OFF

    time.sleep(0.2)
