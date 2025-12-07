# TFT System Monitor for Raspberry Pi (2.0" ST7789V, 240x320)

Проект Python для отображения ключевых системных метрик на **TFT-дисплее 2.0" ST7789V** с разрешением 240x320 через SPI.

## 📋 Описание

Проект предоставляет систему мониторинга для Raspberry Pi, которая включает:
* **Метрики:** Загрузка CPU, температура, использование RAM, свободное место на диске и сетевой трафик.
* **Графика:** График истории загрузки CPU и цветовая индикация.
* **Надежность:** Сервисы Systemd гарантируют отображение графических сообщений при выключении/перезагрузке.

## 🛠 Требования

### Оборудование
* Raspberry Pi
* TFT-дисплей 2.0" SPI ST7789V (240x320, GMT020-02 VER:1.1)
* Соединительные провода

### Подключение TFT-дисплея

Дисплей **2.0" TFT SPI ST7789V GMT020-02 VER:1.1 (240×320)** использует интерфейс **SPI** Raspberry Pi. Для работы нужно включить **SPI** в `sudo raspi-config`.

| TFT Pin |    Функция   | Raspberry Pi (BCM) | Примечания                                   |
| :-----: | :----------: | :----------------: | :------------------------------------------- |
| **VCC** |    Питание   |        3.3V        |                                              |
| **GND** |     Земля    |         GND        |                                              |
| **SCL** |   SPI Clock  |   GPIO 11 (SCLK)   | SPI0 SCLK                                    |
| **SDA** |   SPI Data   |   GPIO 10 (MOSI)   | SPI0 MOSI                                    |
|  **CS** |  Chip Select |    GPIO 7 (CE0)    | SPI0 CE0                                     |
|  **DC** | Data/Command |     **GPIO 25**    | Указывается в `tft_monitor.py`               |
| **RST** |     Reset    |  **Не подключен**  | Программный сброс                            |

### Программное обеспечение
* Python 3
* Зависимости: `Pillow`, `psutil`, `spidev`, `lgpio`.
* **Системный шрифт:** `ttf-dejavu` (для `DejaVuSans-Bold.ttf`).

## 📥 Установка

Выполните команду для автоматической установки:

```bash
# 1. Обновление и установка системных шрифтов
sudo apt update
sudo apt install -y ttf-dejavu

# 2. Создание рабочей директории
sudo mkdir -p /opt/tftmonitor/
cd /opt/tftmonitor/

# 3. Загрузка Python скриптов и зависимостей
curl -sL "https://raw.githubusercontent.com/LevGamer39/TFT-Monitor/refs/heads/main/tft_shutdown.py" -o tft_shutdown.py
curl -sL "https://raw.githubusercontent.com/LevGamer39/TFT-Monitor/refs/heads/main/tft_monitor.py" -o tft_monitor.py
curl -sL "https://raw.githubusercontent.com/LevGamer39/TFT-Monitor/refs/heads/main/requirements.txt" -o requirements.txt

# Установка зависимостей Python
sudo pip3 install -r requirements.txt --break-system-packages

# 4. Установка Systemd сервисов
cd /etc/systemd/system/
curl -sL "https://raw.githubusercontent.com/LevGamer39/TFT-Monitor/refs/heads/main/tft-shutdown.service" -o tft-shutdown.service
curl -sL "https://raw.githubusercontent.com/LevGamer39/TFT-Monitor/refs/heads/main/tft-reboot.service" -o tft-reboot.service
curl -sL "https://raw.githubusercontent.com/LevGamer39/TFT-Monitor/refs/heads/main/tft-monitor.service" -o tft-monitor.service

# 5. Применение и запуск
sudo systemctl daemon-reload
sudo systemctl enable tft-monitor.service tft-reboot.service tft-shutdown.service
sudo systemctl start tft-monitor.service
````

Включите SPI интерфейс в Raspberry Pi:
```bash
sudo raspi-config
# Выберите: Interface Options → SPI → Yes
```

## 📁 Структура файлов в репозитории

| Файл | Назначение |
| :--- | :--- |
| `tft_monitor.py` | Основной скрипт мониторинга и отрисовки |
| `tft_shutdown.py` | Скрипт для вывода сообщений о выключении/перезагрузке |
| `requirements.txt` | Список зависимостей Python |
| `tft-monitor.service` | Сервис Systemd для автозапуска монитора |
| `tft-shutdown.service` | Сервис Systemd для вывода сообщения о выключении |
| `tft-reboot.service` | Сервис Systemd для вывода сообщения о перезагрузке |

## 🔍 Диагностика

  * **Проверка статуса:** `systemctl status tft-monitor.service`
  * **Просмотр логов:** `journalctl -u tft-monitor.service -f`
  * **Проверка выключения (для ошибки):** `journalctl -u tft-shutdown.service -b --no-pager`