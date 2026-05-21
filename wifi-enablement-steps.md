# DL24P WiFi Enablement — ESP-02S Module Installation

Adding WiFi support to the DL24P V2 (BW150 hardware) by soldering an ESP-02S/TYWE2S module into the existing PCB slot, enabling full programmatic control via ESPHome and Home Assistant.

## Background

The DL24P V2 PCB has a vertical WiFi module slot next to the buzzer, designed for a Tuya WiFi module. This slot provides 3.3V power, GND, and UART TX/RX connections directly to the STM32 MCU. Populating this slot with an ESP-02S running ESPHome firmware gives full Tuya MCU control over all device functions — far exceeding what Bluetooth SPP offers.

## Hardware Requirements

| Item | Notes |
|---|---|
| ESP-02S or TYWE2S module | ESP8285-based, ~$2 on AliExpress |
| USB-to-serial adapter | FT232, CH340, or CP2102 — must support 3.3V |
| Jumper wires | For pre-solder testing |
| Soldering iron + solder | Fine tip recommended for small pads |
| Optional: 10–47µF cap | For stable power during standalone testing |

### Why ESP-02S / TYWE2S?

- ESP8285 has 1MB flash built into the chip (no external flash IC)
- No pull resistors needed (unlike ESP-12F which requires RST/EN/GPIO15 pulls)
- Pin-compatible with the PCB's vertical WiFi slot
- Cheap and widely available

## Firmware Source

The ESPHome configuration comes from: https://github.com/1RandomDev/atorch-bw150-esphome

- Uses Tuya MCU protocol over internal UART (115200 baud)
- Board type: `esp8285`
- Provides 21 data points for full device control

## Step 1: Compile ESPHome Firmware

```bash
# Clone the config repo
git clone https://github.com/1RandomDev/atorch-bw150-esphome.git
cd atorch-bw150-esphome

# Edit YAML — set your WiFi credentials and HA API key
# Set board: esp8285

# Compile
esphome compile bw150.yaml

# Output binary at: .esphome/build/<name>/.pioenvs/<name>/firmware.bin
```

## Step 2: Flash the ESP-02S

> ⚠️ Flash BEFORE soldering — once in the PCB, the UART lines are hardwired to the STM32 MCU and cannot be used for serial flashing.

### Wiring for Flashing (GPIO0 = LOW)

| Adapter | ESP-02S |
|---|---|
| 3V3 | VCC |
| GND | GND |
| GND | IO0 (GPIO0) — forces bootloader |
| TXD | RXD |
| RXD | TXD |

Also tie EN and GPIO2 to 3.3V.

### Flash Commands

```bash
# Erase flash
esptool.py --port /dev/ttyUSB0 --baud 115200 erase_flash

# Re-enter bootloader (ESP exits after erase — power-cycle with GPIO0 held low)

# Write firmware
esptool.py --port /dev/ttyUSB0 --baud 460800 write_flash \
  --flash_mode dout \
  --flash_freq 40m \
  --flash_size 1MB \
  0x00000 firmware.bin
```

Key flags:
- `--flash_mode dout` — safest for ESP8285's internal flash
- `--flash_size 1MB` — matches ESP8285 built-in flash

## Step 3: Test Before Soldering

### Wiring for Normal Run (GPIO0 = HIGH)

```
3.3V → VCC, EN, GPIO0, GPIO2
GND  → GND
Adapter TX → ESP RXD  (for serial logs)
Adapter RX → ESP TXD  (for serial logs)
```

The only change from flash mode: move GPIO0 from GND to 3.3V, then power-cycle.

### Verification Checklist

- [ ] Serial logs at 115200 show ESPHome boot without crash loops
- [ ] Module connects to WiFi network
- [ ] Device appears in Home Assistant ESPHome integration
- [ ] OTA update works over WiFi (confirms no future physical access needed)

### Power Notes

- ESP8285 draws up to 300–500mA during WiFi TX bursts
- Many USB-serial adapters can't supply this on their 3.3V pin
- If module keeps rebooting: use a separate AMS1117-3.3 regulator from 5V
- Add a 10–47µF cap across VCC-GND to absorb current spikes

## Step 4: Solder into DL24P

1. Power off the DL24P completely
2. Locate the vertical WiFi module slot (right side of the buzzer)
3. Solder the ESP-02S into the slot — no additional resistors or wiring needed
4. The PCB provides: 3.3V, GND, EN pull-up, UART TX/RX to STM32

## Step 5: Verify In-Circuit Operation

1. Power on the DL24P
2. Check WiFi connection (ping, HA discovery, or ESPHome logs via network)
3. Verify Tuya MCU communication — sensor values should populate in HA
4. Test a write command (e.g., toggle load ON/OFF via DP 104)

## Tuya MCU Data Points (Full Control)

| DP | Description | Writable |
|---|---|---|
| 101 | Voltage (V, ÷100) | Read |
| 102 | Current (A, ÷1000) | Read |
| 103 | Power (W, ÷100) | Read |
| 104 | Load ON/OFF | **Write** |
| 105 | Capacity (mAh) | Read |
| 106 | Energy (Wh, ×100) | Read |
| 107 | Screen brightness (1–9) | **Write** |
| 108 | Operating mode (CC/CV/CR/CP/BRT/PT/CT/CDC/CDCDC) | **Write** |
| 109 | Set value (mode-dependent, ÷100) | **Write** |
| 110 | Limit time (h, ÷100) | **Write** |
| 111 | Charge cutoff voltage (V, ÷100) | **Write** |
| 112 | Discharge cutoff voltage (V, ÷100) | **Write** |
| 113 | CPU temperature (°C, ÷10) | Read |
| 114 | MOSFET temperature (°C, ÷10) | Read |
| 116 | Battery number (+1) | **Write** |
| 117 | Temp limit ext. sensor (°C) | **Write** |
| 118 | External sensor temp (°C) | Read |
| 119 | Clear capacity/energy | **Write** |
| 121 | Temp limit MOSFET (°C) | **Write** |

## Key Learnings

- The ESP-02S cannot be flashed in-circuit — UART is shared with the STM32 MCU
- `esptool erase_flash` causes the ESP to exit bootloader — must re-enter (power-cycle with GPIO0 low) before `write_flash`
- No pull resistors needed on ESP-02S (unlike ESP-12F)
- OTA updates work after initial flash, so physical serial access is only needed once
- The Tuya MCU protocol (115200 baud) provides far richer control than Bluetooth SPP (which only offers button emulation and read-only telemetry)

## References

- https://github.com/1RandomDev/atorch-bw150-esphome — ESPHome config for BW150/DL24 V2
- https://github.com/1RandomDev/atorch-bw150-esphome/issues/1 — confirmed working with TYWE2S, no resistors needed
- https://github.com/syssi/esphome-atorch-dl24 — alternative ESPHome BLE approach (ESP32-based, external)
