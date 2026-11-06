// AS7265x virtual I2C register transport. Based on ams DS000612 v1-04,
// sections I2C Slave Interface and Detailed Register Descriptions.
// Original implementation for this project; no external sensor library required.
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <string.h>

class FastAS7265x {
 public:
  bool begin() {
    Wire.begin();
    Wire.setClock(400000UL);
#if defined(WIRE_HAS_TIMEOUT)
    Wire.setWireTimeout(25000UL, true);
#endif
    uint8_t devices;
    return read(0x4F, devices) && (devices & 0x30) == 0x30;
  }

  bool select(uint8_t device) {
    // Only SELECT_DATA bits are writable; the slave-presence flags are read-only.
    return write(0x4F, device & 3);
  }

  bool read(uint8_t address, uint8_t &value) {
    uint8_t status, ignored;
    if (!physicalRead(0, status)) return false;
    if ((status & 1) && !physicalRead(2, ignored)) return false;
    if (!wait(2, false) || !physicalWrite(1, address & 0x7F) || !wait(1, true)) return false;
    return physicalRead(2, value);
  }

  bool write(uint8_t address, uint8_t value) {
    return wait(2, false) && physicalWrite(1, address | 0x80) &&
           wait(2, false) && physicalWrite(1, value);
  }

  bool configure(uint8_t gain, uint16_t cycles) {
    // Figure 30 maps register 0..255 to 1..256 integration cycles.
    return write(5, (uint8_t)(cycles - 1)) && write(4, (gain << 4) | 0x0C);
  }

  bool start(uint8_t gain) { return write(4, (gain << 4) | 0x0C); }
  bool ready(bool &available) {
    uint8_t value;
    if (!read(4, value)) return false;
    available = value & 2;
    return true;
  }

  bool led(uint8_t device, bool driver, uint8_t current, bool indicator, uint8_t indCurrent) {
    return select(device) && write(7, (current << 4) | (driver ? 8 : 0) |
                                  (indCurrent << 1) | (indicator ? 1 : 0));
  }

  bool temperature(uint8_t device, int8_t &result) {
    uint8_t value;
    if (!select(device) || !read(6, value)) return false;
    result = (int8_t)value;
    return value != 0x80;
  }

  bool spectrum(float values[18], bool calibrated) {
    // One-shot conversion is complete before reading, so all three chips stay
    // on the same conversion while the entire frame is copied.
    float channels[3][6];
    for (uint8_t device = 0; device < 3; ++device) {
      if (!select(device)) return false;
      for (uint8_t channel = 0; channel < 6; ++channel) {
        uint32_t bits = 0;
        uint8_t count = calibrated ? 4 : 2;
        uint8_t base = calibrated ? 0x14 : 0x08;
        for (uint8_t byte = 0; byte < count; ++byte) {
          uint8_t value;
          if (!read(base + count * channel + byte, value)) return false;
          bits = (bits << 8) | value;
        }
        if (calibrated) memcpy(&channels[device][channel], &bits, 4);
        else channels[device][channel] = (float)bits;
      }
    }
    // Wavelength order: A B C D E F G H R I S J T U V W K L.
    for (uint8_t i = 0; i < 6; ++i) values[i] = channels[2][i];
    values[6] = channels[1][0]; values[7] = channels[1][1];
    values[8] = channels[0][0]; values[9] = channels[1][2];
    values[10] = channels[0][1]; values[11] = channels[1][3];
    for (uint8_t i = 2; i < 6; ++i) values[10 + i] = channels[0][i];
    values[16] = channels[1][4]; values[17] = channels[1][5];
    return true;
  }

 private:
  bool physicalRead(uint8_t reg, uint8_t &value) {
    Wire.beginTransmission(0x49);
    Wire.write(reg);
    if (Wire.endTransmission() != 0) return false;
    if (Wire.requestFrom((uint8_t)0x49, (uint8_t)1) != 1) return false;
    value = Wire.read();
    return true;
  }
  bool physicalWrite(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(0x49);
    Wire.write(reg); Wire.write(value);
    return Wire.endTransmission() == 0;
  }
  bool wait(uint8_t mask, bool set) {
    unsigned long started = millis();
    do {
      uint8_t status;
      if (!physicalRead(0, status)) return false;
      if (((status & mask) != 0) == set) return true;
      delayMicroseconds(100);
    } while (millis() - started < 100);
    return false;
  }
};
