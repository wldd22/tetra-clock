import os
import time
import rtc
import wifi
import socketpool
import board
import pwmio
import touchio
import digitalio
import displayio
import terminalio
import adafruit_ntp
import adafruit_displayio_ssd1306
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

root = displayio.Group()
display.root_group = root

# Large time, centred on the display
datetime_text = label.Label(
    terminalio.FONT,
    text="XXXX-XX-XX XX:XX:XX",
    color=0xFFFFFF,
    scale=1,
    x=7,
    y=15
)

status_text = label.Label(
    terminalio.FONT,
    text="",
    color=0xFFFFFF,
    scale=1,
    x=0,
    y=27
)

root.append(datetime_text)
root.append(status_text)

# -------------------------
# Network and clock setup
# -------------------------

pool = None
ntp = None

time_is_valid = False
last_wifi_attempt = -WIFI_RETRY_SECONDS
last_ntp_attempt = -NTP_RETRY_SECONDS

status_text.text = "Initialising..."

def synchronize_time():
    """Connect to Wi-Fi if needed and set the RTC from NTP."""
    global pool, ntp, time_is_valid

    try:
        if not wifi.radio.connected:
            print("Connecting to Wi-Fi...")
            status_text.text = "Connecting to Wi-Fi..."

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
        status_text.text = "Requesting NTP time..."

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
        status_text.text = f"Time synchronised"

    except Exception as error:
        print("Synchronisation failed:", error)
        status_text.text = f"Syncing failed"


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

    if time_is_valid:
        now = time.localtime()
        datetime_text.text = f"{now.tm_year:04d}-{now.tm_mon:02d}-{now.tm_mday:02d} "
        f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
    else:
        datetime_text.text = "XXXX-XX-XX XX:XX:XX"

    # Handle touch input and buzzer output
    if touch[0].value:
        buzzer.duty_cycle = 32768  # Buzzer ON
    else:
        buzzer.duty_cycle = 0  # Buzzer OFF

    time.sleep(0.2)
