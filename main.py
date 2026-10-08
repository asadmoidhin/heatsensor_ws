"""
Cooler Fan Controller - Raspberry Pi Pico H + Grove Shield (3.3V)
Sensor : MCP9701 on A0 (GP26 / ADC0)
OLED   : SSD1306 128x64 on I2C1 (GP6=SDA, GP7=SCL, 0x3C)
Btn +  : D16 (GP16, active-low, pull-up) -> Force Fan ON
Btn -  : D18 (GP18, active-low, pull-up) -> Reset to AUTO
Relay  : D20 (GP20, active-HIGH, drives 5V cooler fan)
"""

from machine import Pin, ADC, I2C
from oled_driver import SSD1306_I2C
import time

# ----------------------------------------------------------------
# Pin Configuration
# ----------------------------------------------------------------
adc_sensor = ADC(26)                                  # MCP9701 on GP26/ADC0

i2c  = I2C(1, sda=Pin(6), scl=Pin(7), freq=400_000)  # I2C1 for OLED
oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)

btn_plus  = Pin(16, Pin.IN, Pin.PULL_UP)              # Button +: Force Fan ON
btn_minus = Pin(18, Pin.IN, Pin.PULL_UP)              # Button -: Reset to AUTO

relay = Pin(20, Pin.OUT)
relay.value(0)                                        # Safety: relay OFF at boot

# ----------------------------------------------------------------
# Hysteresis Thresholds
# ----------------------------------------------------------------
THRESHOLD_ON  = 28.5   # deg C - fan ON at or above
THRESHOLD_OFF = 27.5   # deg C - fan OFF at or below

# ----------------------------------------------------------------
# State
# ----------------------------------------------------------------
mode          = "AUTO"  # "AUTO" or "MANUAL"
fan_on        = False   # current fan state
last_btn_time = 0       # debounce timestamp (ms)

DEBOUNCE_MS      = 200
ADC_SAMPLES      = 10
ADC_SAMPLE_DELAY = 5    # ms between ADC samples
LOOP_PERIOD_MS   = 300  # loop refresh period (200-500 ms range)


# ----------------------------------------------------------------
def read_temperature():
    """Return temperature in deg C from MCP9701 averaged over ADC_SAMPLES."""
    total = 0
    for _ in range(ADC_SAMPLES):
        total += adc_sensor.read_u16()
        time.sleep_ms(ADC_SAMPLE_DELAY)
    avg_adc = total / ADC_SAMPLES
    volts   = (avg_adc * 3.3) / 65535
    celsius = (volts - 0.4) / 0.0195
    return celsius


# ----------------------------------------------------------------
def update_display(temp_c):
    """Render status screen on the OLED (16 chars per line max)."""
    oled.fill(0)
    # 16-char ruler: |1234567890123456|
    oled.text("COOLER SYSTEM", 0, 0)        # 13 chars
    oled.text("Temp: {:.1f} C".format(temp_c), 0, 12)           # 12 chars max
    oled.text("On:{:.1f} Off:{:.1f}".format(THRESHOLD_ON, THRESHOLD_OFF), 0, 24)  # 16 chars
    oled.text("Mode: " + mode, 0, 40)       # 10 (AUTO) or 12 (MANUAL)
    oled.text("Fan:  " + ("ON" if fan_on else "OFF"), 0, 52)    # 8-9 chars
    oled.show()


# ----------------------------------------------------------------
# Main Loop
# ----------------------------------------------------------------
while True:
    now = time.ticks_ms()

    # Button handling (active-low, 200 ms debounce)
    if time.ticks_diff(now, last_btn_time) >= DEBOUNCE_MS:
        if btn_plus.value() == 0:              # Button + pressed -> MANUAL ON
            mode          = "MANUAL"
            fan_on        = True
            relay.value(1)
            last_btn_time = now
        elif btn_minus.value() == 0:           # Button - pressed -> back to AUTO
            mode          = "AUTO"
            last_btn_time = now
            # Fall through: AUTO hysteresis re-evaluates immediately below

    # Temperature reading
    temp_c = read_temperature()

    # Fan control (AUTO only; MANUAL state is latched by button handler above)
    if mode == "AUTO":
        if temp_c >= THRESHOLD_ON:
            fan_on = True
        elif temp_c <= THRESHOLD_OFF:
            fan_on = False
        # Between thresholds -> hold current state (hysteresis dead band)
        relay.value(1 if fan_on else 0)

    # Update OLED
    update_display(temp_c)

    # Pace the loop: wait out the remainder of LOOP_PERIOD_MS
    elapsed   = time.ticks_diff(time.ticks_ms(), now)
    remaining = LOOP_PERIOD_MS - elapsed
    if remaining > 0:
        time.sleep_ms(remaining)
