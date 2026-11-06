#pragma once
#include "Arduino.h"
#include <vector>
#include <cstring>
class MockWire {
 public:
  uint8_t leds[3] = {0,0,0};
  uint8_t selected=0, config=0, cycles=0, physical=0, virtualAddress=0, rx=0;
  bool rxValid=false, writeValue=false, fail=false;
  unsigned long conversionDue=0;
  std::vector<uint8_t> tx;
  void begin() {}
  void setClock(unsigned long) {}
  void beginTransmission(uint8_t) { tx.clear(); }
  void write(uint8_t value) { tx.push_back(value); }
  uint8_t endTransmission() {
    if (fail) return 4;
    if (tx.size()==1) physical=tx[0];
    if (tx.size()==2 && tx[0]==1) {
      uint8_t value=tx[1];
      if (writeValue) {
        if (virtualAddress==0x4F) selected=value & 3;
        else if (virtualAddress==7) leds[selected]=value;
        else if (virtualAddress==5) cycles=value;
        else if (virtualAddress==4) { config=value; conversionDue=millis()+1; }
        writeValue=false;
      } else if (value & 0x80) { virtualAddress=value & 0x7F; writeValue=true; }
      else { rx=virtualRead(value); rxValid=true; }
    }
    return 0;
  }
  uint8_t requestFrom(uint8_t, uint8_t) { return fail ? 0 : 1; }
  int read() {
    if (physical==0) return rxValid ? 1 : 0;
    rxValid=false;
    return rx;
  }
  uint8_t virtualRead(uint8_t address) {
    if (address==0x4F) return 0x30 | selected;
    if (address==4) return config | (millis() >= conversionDue ? 2 : 0);
    if (address==6) return selected==2 ? (uint8_t)-12 : 25 + selected;
    if (address==7) return leds[selected];
    if (address>=0x14 && address<=0x2B) {
      uint8_t channel=(address-0x14)/4, byte=(address-0x14)%4;
      float value=selected*10 + channel + 0.5f;
      uint32_t bits; memcpy(&bits,&value,4);
      return (bits >> (8*(3-byte))) & 0xFF;
    }
    if (address>=8 && address<=0x13) {
      uint8_t channel=(address-8)/2, byte=(address-8)%2;
      uint16_t value=selected*100 + channel;
      return byte ? value & 0xFF : value >> 8;
    }
    return 0;
  }
};
inline MockWire Wire;
