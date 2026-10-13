#!/usr/bin/env python3
"""
TFT Shutdown/Reboot Message Handler
Отображает сообщения о выключении/перезагрузке на дисплее ST7789.
"""

import sys
import time
import os
from PIL import Image, ImageDraw, ImageFont

# Импортируем Config и ST7789Display из основного монитора
try:
    from tft_monitor import Config, ST7789Display 
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from tft_monitor import Config, ST7789Display 
    except ImportError:
        print("Error: Could not import Config or ST7789Display from tft_monitor.py")
        sys.exit(1)

# ============================================================================
# ОТРИСОВЩИК СООБЩЕНИЙ
# ============================================================================

class ShutdownRenderer:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.c_bg = (0, 0, 0)
        self.col_crit = (255, 20, 20)
        self.col_cool = (0, 200, 255)

        try:
            self.f_36 = ImageFont.truetype(Config.FONT_BOLD, 36)
            self.f_22 = ImageFont.truetype(Config.FONT_BOLD, 22)
        except:
            self.f_36 = ImageFont.load_default()
            self.f_22 = ImageFont.load_default()

    def render_message(self, message, color):
        img = Image.new("RGB", (self.w, self.h), self.c_bg)
        draw = ImageDraw.Draw(img)

        font = self.f_22
        if len(message) <= 12: 
            font = self.f_36
            
        text_w = draw.textlength(message, font=font)
        
        x = (self.w - text_w) / 2
        y = (self.h - font.size) / 2 

        draw.text((x, y), message, font=font, fill=color)
        return img
        
# ============================================================================
# ГЛАВНАЯ ЛОГИКА
# ============================================================================

def main():
    if os.geteuid() != 0:
        print("Run as sudo!")
        sys.exit(1)
        
    cfg = Config()
    try:
        disp = ST7789Display(cfg)
        renderer = ShutdownRenderer(cfg.WIDTH, cfg.HEIGHT)
    except Exception as e:
        print(f"Failed to initialize display: {e}")
        sys.exit(1)


    if len(sys.argv) > 1 and sys.argv[1] == "poweroff":
        
        # Шаг 1: Shutting down...
        msg1 = "Shutting down..."
        img1 = renderer.render_message(msg1, renderer.col_crit)
        disp.display(img1)
        time.sleep(1.5)

        # Шаг 2: Powered off
        msg2 = "Powered off"
        img2 = renderer.render_message(msg2, renderer.col_cool)
        disp.display(img2)
        time.sleep(3.5) 

        disp.cleanup()

    elif len(sys.argv) > 1 and sys.argv[1] == "reboot":
        
        msg = "Rebooting..."
        img = renderer.render_message(msg, renderer.col_cool)
        disp.display(img)
        time.sleep(3)
        
        disp.cleanup()

    else:
        disp.cleanup()
        pass

if __name__ == "__main__":
    main()
