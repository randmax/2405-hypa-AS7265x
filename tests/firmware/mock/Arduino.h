#pragma once
#include <stdint.h>
#include <math.h>
#include <deque>
#include <iomanip>
#include <sstream>
#include <string>
#include <type_traits>
struct __FlashStringHelper {};
#define F(x) reinterpret_cast<const __FlashStringHelper *>(x)
inline unsigned long mockMicros = 0;
inline unsigned long millis() { return mockMicros / 1000; }
inline void delay(unsigned long ms) { mockMicros += ms * 1000; }
inline void delayMicroseconds(unsigned int us) { mockMicros += us; }
class MockSerial {
 public:
  std::ostringstream output;
  std::deque<char> input;
  void begin(unsigned long) {}
  int available() { return input.size(); }
  int read() { char ch=input.front(); input.pop_front(); return ch; }
  void print(const __FlashStringHelper *text) { output << reinterpret_cast<const char *>(text); }
  void print(char value) { output << value; }
  template<class T> void print(T value) {
    if constexpr (std::is_integral<T>::value) output << +value;
    else output << value;
  }
  void print(double value, int precision) {
    std::ostringstream stream;
    stream << std::fixed << std::setprecision(precision) << value;
    output << stream.str();
  }
  void println() { output << '\n'; }
  template<class T> void println(T value) { print(value); println(); }
};
inline MockSerial Serial;
