import RPi.GPIO as GPIO
import time
import math
import busio
import digitalio
import board
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from threading import Thread
from adafruit_mcp3008.analog_in import AnalogIn
from adafruit_mcp3008 import MCP3008 as MCP

# GPIO to LCD, RGB LED, and Buzzer mapping
LCD_RS = 7
LCD_E  = 8
LCD_D4 = 25
LCD_D5 = 24
LCD_D6 = 23
LCD_D7 = 18
LED_RED = 20
LED_GREEN = 21
LED_BLUE = 22
BUZZER_PIN = 26

# Device constants
LCD_CHR = True
LCD_CMD = False
LCD_CHARS = 16
LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0

# SPI setup for MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D22)
mcp = MCP(spi, cs)
thermistor_channel = AnalogIn(mcp, MCP.P0)

# Global variables for temperature unit and data
temperature_unit = "C"  # Start with Celsius
temperature_data = []

def main():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([LCD_E, LCD_RS, LCD_D4, LCD_D5, LCD_D6, LCD_D7, LED_RED, LED_GREEN, LED_BLUE, BUZZER_PIN], GPIO.OUT)
    
    lcd_init()
    GPIO.output([LED_RED, LED_GREEN, LED_BLUE], GPIO.LOW)
    buzzer = GPIO.PWM(BUZZER_PIN, 1000)

    thread = Thread(target=run_gui)
    thread.daemon = True
    thread.start()

    try:
        while True:
            temp = read_temperature()
            lcd_display_temperature(temp)
            control_led(temp)
            control_buzzer(temp, buzzer)
            log_temperature(temp)
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        buzzer.stop()
        GPIO.cleanup()

def run_gui():
    global fig, ax, canvas
    root = tk.Tk()
    root.title("Temperature Monitoring and Control")

    fig, ax = plt.subplots(figsize=(5, 3))
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    button_frame = tk.Frame(root)
    button_frame.pack(side=tk.BOTTOM, fill=tk.X)

    toggle_button = tk.Button(button_frame, text="C/F", command=toggle_unit)
    toggle_button.pack(side=tk.LEFT, padx=5, pady=5)

    root.mainloop()

def toggle_unit():
    global temperature_unit
    if temperature_unit == "C":
        temperature_unit = "F"
    else:
        temperature_unit = "C"
    plot_temperature()

def log_temperature(temp):
    temperature_data.append(temp)
    if len(temperature_data) > 50:
        temperature_data.pop(0)
    plot_temperature()

def plot_temperature():
    ax.clear()
    temps = temperature_data if temperature_unit == "C" else [t * 9 / 5 + 32 for t in temperature_data]
    ax.plot(temps, '-o', label='Temperature')
    ax.set_title("Temperature Over Time")
    ax.set_ylabel(f"Temperature ({temperature_unit})")
    ax.legend()
    canvas.draw()

def lcd_display_temperature(temp):
    if temperature_unit == "C":
        message = "Temp: {:.2f}C".format(temp)
    else:
        temp_f = temp * 9 / 5 + 32
        message = "Temp: {:.2f}F".format(temp_f)
    lcd_text(message, LCD_LINE_1)

def lcd_init():
    lcd_write(0x33, LCD_CMD) # Initialize
    lcd_write(0x32, LCD_CMD) # Set to 4-bit mode
    lcd_write(0x06, LCD_CMD) # Cursor move direction
    lcd_write(0x0C, LCD_CMD) # Turn cursor off
    lcd_write(0x28, LCD_CMD) # 2 line display
    lcd_write(0x01, LCD_CMD) # Clear display
    time.sleep(0.0005)

def lcd_write(bits, mode):
    GPIO.output(LCD_RS, mode)
    GPIO.output(LCD_D4, bits & 0x10 == 0x10)
    GPIO.output(LCD_D5, bits & 0x20 == 0x20)
    GPIO.output(LCD_D6, bits & 0x40 == 0x40)
    GPIO.output(LCD_D7, bits & 0x80 == 0x80)
    lcd_toggle_enable()
    GPIO.output(LCD_D4, bits & 0x01 == 0x01)
    GPIO.output(LCD_D5, bits & 0x02 == 0x02)
    GPIO.output(LCD_D6, bits & 0x04 == 0x04)
    GPIO.output(LCD_D7, bits & 0x08 == 0x08)
    lcd_toggle_enable()

def lcd_toggle_enable():
    GPIO.output(LCD_E, False)
    time.sleep(0.001)
    GPIO.output(LCD_E, True)
    time.sleep(0.001)
    GPIO.output(LCD_E, False)
    time.sleep(0.001)

def lcd_text(message, line):
    message = message.ljust(LCD_CHARS, " ")
    lcd_write(line, LCD_CMD)
    for char in message:
        lcd_write(ord(char), LCD_CHR)

def read_temperature():
    V = thermistor_channel.voltage
    R = 10000 * (3.3 - V) / V
    B = 3950
    R0 = 10000
    T0 = 298.15
    T = 1 / (1/T0 + (1/B) * math.log(R/R0))
    return T - 273.15

def control_led(temp):
    human_body_temp = 37.0
    tolerance = 0.10 * human_body_temp
    if abs(temp - human_body_temp) <= tolerance:
        GPIO.output(LED_GREEN, GPIO.HIGH)
        GPIO.output([LED_RED, LED_BLUE], GPIO.LOW)
    elif temp < human_body_temp:
        GPIO.output(LED_BLUE, GPIO.HIGH)
        GPIO.output([LED_RED, LED_GREEN], GPIO.LOW)
    else:
        GPIO.output(LED_RED, GPIO.HIGH)
        GPIO.output([LED_GREEN, LED_BLUE], GPIO.LOW)

def control_buzzer(temp, buzzer):
    human_body_temp = 37.0
    tolerance = 0.10 * human_body_temp
    if abs(temp - human_body_temp) <= tolerance:
        buzzer.start(50)
        buzzer.ChangeFrequency(440)
        time.sleep(0.5)
        buzzer.stop()
    else:
        buzzer.start(50)
        buzzer.ChangeFrequency(220)
        time.sleep(0.25)
        buzzer.stop()
        time.sleep(0.1)
        buzzer.start(50)
        buzzer.ChangeFrequency(220)
        time.sleep(0.25)
        buzzer.stop()

if __name__ == "__main__":
    main()

