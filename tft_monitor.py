#!/usr/bin/env python3
"""
TFT System Monitor
Отображает основной монитор.
"""

import sys
import time
import os
import psutil
import numpy as np
from collections import deque
from PIL import Image, ImageDraw, ImageFont
import spidev
import lgpio

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

class Config:
    WIDTH = 240
    HEIGHT = 320
    
    PIN_DC = 25
    PIN_BL = 22 
    SPI_BUS = 0
    SPI_DEVICE = 0 
    SPI_SPEED = 60000000
    
    UPDATE_INTERVAL = 0.5
    GRAPH_HISTORY = 60
    
    FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ============================================================================
# ДРАЙВЕР ДИСПЛЕЯ
# ============================================================================

class ST7789Display:
    def __init__(self, config: Config):
        self.config = config
        self.width = config.WIDTH
        self.height = config.HEIGHT
        
        try:
            self.h = lgpio.gpiochip_open(0)
        except:
            try:
                self.h = lgpio.gpiochip_open(4)
            except:
                sys.exit(1)

        lgpio.gpio_claim_output(self.h, config.PIN_DC)
        lgpio.gpio_claim_output(self.h, config.PIN_BL) 
        
        self.spi = spidev.SpiDev()
        self.spi.open(config.SPI_BUS, config.SPI_DEVICE)
        self.spi.max_speed_hz = config.SPI_SPEED
        self.spi.mode = 0b00
        
        self.init_display()
        lgpio.gpio_write(self.h, config.PIN_BL, 1)

    def write_cmd(self, cmd):
        lgpio.gpio_write(self.h, self.config.PIN_DC, 0)
        self.spi.xfer2([cmd])

    def write_data(self, data):
        lgpio.gpio_write(self.h, self.config.PIN_DC, 1)
        if isinstance(data, list) or isinstance(data, bytes):
            self.spi.xfer2(list(data))
        else:
            self.spi.xfer2([data])

    def init_display(self):
        self.write_cmd(0x01); time.sleep(0.150)
        self.write_cmd(0x11); time.sleep(0.050)
        self.write_cmd(0x3A); self.write_data(0x55)
        self.write_cmd(0x36); self.write_data(0x00)
        self.write_cmd(0x21)
        self.write_cmd(0x29)

    def display(self, image):
        if image.width != self.width or image.height != self.height:
            image = image.resize((self.width, self.height))

        pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)

        r = pixels[:, :, 0].astype(np.uint16)
        g = pixels[:, :, 1].astype(np.uint16)
        b = pixels[:, :, 2].astype(np.uint16)

        rgb565 = (
            ((r & 0xF8) << 8)
            | ((g & 0xFC) << 3)
            | (b >> 3)
        )

        rgb565 = rgb565.astype(">u2").tobytes()

        self.set_window(0, 0, self.width, self.height)
        lgpio.gpio_write(self.h, self.config.PIN_DC, 1)
        
        chunk = 4096
        for i in range(0, len(rgb565), chunk):
            self.spi.xfer2(rgb565[i:i + chunk])

    def set_window(self, x, y, w, h):
        self.write_cmd(0x2A); self.write_data([x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF])
        self.write_cmd(0x2B); self.write_data([y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF])
        self.write_cmd(0x2C)
        
    def cleanup(self):
        self.spi.close()
        lgpio.gpiochip_close(self.h)

# ============================================================================
# ЛОГИКА И ОТРИСОВКА
# ============================================================================

class SystemMonitor:
    def __init__(self):
        self.last_net = psutil.net_io_counters()
        self.last_time = time.time()

        self.cached_ip = None
        self.last_ip_update = 0.0

        self.cached_disk = psutil.disk_usage("/")
        self.last_disk_update = 0.0
        
    def get_ip(self):
        try:
            with open("/proc/net/route") as f:
                for line in f.readlines()[1:]:
                    fields = line.split()

                    if len(fields) < 3:
                        continue

                    interface = fields[0]
                    destination = fields[1]
                    flags = int(fields[3], 16)

                    if destination == "00000000" and flags & 0x1:
                        for address in psutil.net_if_addrs().get(interface, []):
                            if address.family == 2:
                                return address.address
        except (OSError, ValueError):
            pass

        return "No IP"

    def get_data(self):
        now = time.time()

        cpu = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
        
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read()) / 1000.0
        except:
            temp = 0.0

        mem = psutil.virtual_memory()

        if now - self.last_disk_update >= 5.0:
            self.cached_disk = psutil.disk_usage("/")
            self.last_disk_update = now

        disk = self.cached_disk
        
        net = psutil.net_io_counters()
        dt = now - self.last_time
        tx = (net.bytes_sent - self.last_net.bytes_sent) / dt
        rx = (net.bytes_recv - self.last_net.bytes_recv) / dt
        self.last_net = net
        self.last_time = now

        if now - self.last_ip_update >= 30.0 or self.cached_ip is None:
            self.cached_ip = self.get_ip()
            self.last_ip_update = now

        return {
            "cpu": cpu, "cpu_cores": cpu_cores, "temp": temp,
            "mem_p": mem.percent, "mem_u": mem.used/1024**3, "mem_t": mem.total/1024**3,
            "disk_free": disk.free/1024**3,
            "net_tx": tx, "net_rx": rx, "ip": self.cached_ip
        }

class Dashboard:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cpu_hist = deque([0]*Config.GRAPH_HISTORY, maxlen=Config.GRAPH_HISTORY)
        
        self.c_bg = (0, 0, 0)
        self.c_dim = (100, 100, 100)
        self.c_wht = (255, 255, 255)
        
        self.col_ok = (0, 255, 100)      
        self.col_warm = (255, 200, 0)    
        self.col_hot = (255, 100, 0)     
        self.col_crit = (255, 20, 20)    
        self.col_cool = (0, 200, 255)    

        try:
            self.f_48 = ImageFont.truetype(Config.FONT_BOLD, 48)
            self.f_42 = ImageFont.truetype(Config.FONT_BOLD, 42)
            self.f_28 = ImageFont.truetype(Config.FONT_BOLD, 28)
            self.f_22 = ImageFont.truetype(Config.FONT_BOLD, 22)
            self.f_18 = ImageFont.truetype(Config.FONT_BOLD, 18)
            self.f_14 = ImageFont.truetype(Config.FONT_BOLD, 14)
        except:
            self.f_48 = ImageFont.load_default()
            self.f_42 = ImageFont.load_default()
            self.f_28 = ImageFont.load_default()
            self.f_22 = ImageFont.load_default()
            self.f_18 = ImageFont.load_default()
            self.f_14 = ImageFont.load_default()

    def get_color(self, val, limit_warn, limit_crit):
        if val >= limit_crit: return self.col_crit
        if val >= limit_warn: return self.col_hot
        if val >= (limit_warn * 0.7): return self.col_warm
        return self.col_ok

    def get_temp_color(self, val):
        if val >= 75: return self.col_crit
        if val >= 60: return self.col_hot
        if val >= 45: return self.col_ok
        return self.col_cool

    def fmt_bytes(self, b):
        if b > 1024**3: return f"{b/1024**3:.1f}G"
        if b > 1024**2: return f"{b/1024**2:.1f}M"
        if b > 1024: return f"{b/1024:.0f}K"
        return f"{b:.0f}"

    def render(self, d):
        img = Image.new("RGB", (self.w, self.h), self.c_bg)
        draw = ImageDraw.Draw(img)
        
        self.cpu_hist.append(d['cpu'])
        
        # --- 1. HEADER (IP & Time) ---
        ip_text = d['ip']
        ip_color = self.col_cool
        ip_font = self.f_14
        
        if ip_text == "No IP":
            ip_color = self.col_crit
            ip_font = self.f_18
            
        draw.text((5, 5), ip_text, font=ip_font, fill=ip_color)
        
        t_str = time.strftime("%H:%M")
        t_w = draw.textlength(t_str, font=self.f_28)
        draw.text((self.w - t_w - 2, 0), t_str, font=self.f_28, fill=self.c_wht)
        draw.line((0, 32, self.w, 32), fill=(50,50,50))

        # --- 2. CPU ---
        y = 40
        cpu_col = self.get_color(d['cpu'], 50, 80)
        draw.text((5, y), "CPU", font=self.f_14, fill=self.c_dim)
        cpu_text = f"{int(d['cpu'])}%"
        if d['cpu'] >= 100:
            draw.text((5, y+15), cpu_text, font=self.f_42, fill=cpu_col)
        else:
            draw.text((5, y+15), cpu_text, font=self.f_48, fill=cpu_col)
        
        tmp_col = self.get_temp_color(d['temp'])
        temp_text = f"{d['temp']:.1f}°"
        draw.text((160, y+25), temp_text, font=self.f_28, fill=tmp_col)
        
        y_graph = y + 65
        self.draw_graph(draw, 5, y_graph, self.w-10, 40, self.cpu_hist, cpu_col)
        
        y_cores_start = y_graph + 45
        y_cores_end = y_cores_start + 5
        
        core_count = len(d['cpu_cores'])
        core_w = (self.w - 10) // core_count
        
        for i, core_load in enumerate(d['cpu_cores']):
            x_start = 5 + i * core_w
            x_end = x_start + core_w - 2
            core_col = self.get_color(core_load, 50, 80)
            draw.rectangle((x_start, y_cores_start, x_end, y_cores_start + 5), fill=(15,15,20))
            fill_w = int((x_end - x_start) * (core_load / 100))
            draw.rectangle((x_start, y_cores_start, x_start + fill_w, y_cores_start + 5), fill=core_col)


        # --- 3. RAM ---
        y = y_cores_end + 10 
        ram_col = self.get_color(d['mem_p'], 70, 90)
        
        draw.text((5, y), "RAM", font=self.f_14, fill=self.c_dim)
        draw.text((5, y+18), f"{d['mem_u']:.1f} / {d['mem_t']:.0f} GB", font=self.f_18, fill=self.c_wht)
        
        bar_w = self.w - 10
        draw.rectangle((5, y+42, 5+bar_w, y+50), fill=(30,30,30))
        fill_w = int(bar_w * (d['mem_p'] / 100))
        draw.rectangle((5, y+42, 5+fill_w, y+50), fill=ram_col)

        # --- 4. DISK ---
        y = y + 60
        draw.line((0, y-5, self.w, y-5), fill=(50,50,50))
        
        draw.text((5, y), "DISK Free:", font=self.f_18, fill=self.c_dim)
        
        if d['disk_free'] >= 1000:
            disk_txt = f"{d['disk_free']/1024:.2f} TB"
        else:
            disk_txt = f"{d['disk_free']:.1f} GB"
            
        x_disk_val = draw.textlength("DISK Free:", font=self.f_18) + 10
        draw.text((x_disk_val, y - 3), disk_txt, font=self.f_22, fill=self.c_wht)

        # --- 5. NETWORK ---
        y_net = 280
        
        if ip_text == "No IP":
            # Отображаем "No Network"
            msg = "No Network"
            font = self.f_28
            text_w = draw.textlength(msg, font=font)
            x_center = (self.w - text_w) / 2
            draw.text((x_center, y_net), msg, font=font, fill=self.col_crit)
        else:
            # Отображаем UP/DN трафик
            draw.text((5, y_net), "UP:", font=self.f_14, fill=self.col_warm)
            tx_str = f"{self.fmt_bytes(d['net_tx'])}B/s"
            draw.text((35, y_net), tx_str, font=self.f_18, fill=self.c_wht)
            
            draw.text((120, y_net), "DN:", font=self.f_14, fill=self.col_ok)
            rx_str = f"{self.fmt_bytes(d['net_rx'])}B/s"
            draw.text((150, y_net), rx_str, font=self.f_18, fill=self.c_wht)

        return img

    def draw_graph(self, draw, x, y, w, h, data, color):
        if not data: return
        draw.rectangle((x, y, x+w, y+h), fill=(10,10,15), outline=(40,40,40))
        
        step = w / (len(data) - 1) if len(data) > 1 else w
        max_val = 100
        
        pts = []
        for i, val in enumerate(data):
            px = x + i * step
            py = y + h - (val / max_val * h)
            py = max(y+1, min(y+h-1, py))
            pts.append((px, py))
            
        if len(pts) > 1:
            draw.line(pts, fill=color, width=2)

# ============================================================================
# ЗАПУСК
# ============================================================================

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run as sudo!")
        sys.exit(1)
        
    cfg = Config()
    disp = ST7789Display(cfg)
    mon = SystemMonitor()
    dash = Dashboard(cfg.WIDTH, cfg.HEIGHT)
    
    try:
        while True:
            t0 = time.time()
            data = mon.get_data()
            img = dash.render(data)
            disp.display(img)
            
            wait = cfg.UPDATE_INTERVAL - (time.time() - t0)
            time.sleep(max(0, wait))
            
    except KeyboardInterrupt:
        disp.cleanup()
