// AS7265xController 1.0.0 -- 115200 baud, 18-channel CSV + versioned control.
// Arduino Uno / classic Nano / Mega 2560. See ../README.md for wiring,
// protocol, combined bootloader images and UART upload instructions.
#include "FastAS7265x.h"
#include <math.h>
#include <stdlib.h>

FastAS7265x sensor;
uint8_t gainCode = 2;
uint16_t integrationCycles = 10;
bool calibrated = true, streaming = true, measuring = false, sensorOK = false;
bool drivers[3] = {false, false, false};
bool indicators[3] = {false, false, false};
uint8_t driverCurrent[3] = {0, 0, 0}, indicatorCurrent[3] = {0, 0, 0};
unsigned long conversionStarted = 0, lastPoll = 0, lastTelemetry = 0;
unsigned long lastHost = 0;
char commandLine[96];
uint8_t commandLength = 0;
bool discardCommand = false;

void errorReply(unsigned long id, const __FlashStringHelper *message) {
  Serial.print(F("#{\"type\":\"error\",\"id\":")); Serial.print(id);
  Serial.print(F(",\"message\":\"")); Serial.print(message); Serial.println(F("\"}"));
}

void hello(unsigned long id) {
  Serial.print(F("#{\"type\":\"hello\",\"id\":")); Serial.print(id);
  Serial.print(F(",\"protocol\":1,\"firmware\":\"1.0.0\",\"device\":\"AS7265x\",\"board\":\""));
#if defined(__AVR_ATmega2560__)
  Serial.print(F("ATmega2560"));
#elif defined(__AVR_ATmega328P__)
  Serial.print(F("ATmega328P"));
#else
  Serial.print(F("Arduino"));
#endif
  Serial.print(F("\",\"sensor_ok\":")); Serial.print(sensorOK ? 1 : 0);
  Serial.println(F(",\"caps\":[\"LED\",\"IND\",\"SET\",\"TEMP\",\"RUN\",\"SHOT\",\"OFF\",\"PING\"]}"));
}

void state(unsigned long id) {
  Serial.print(F("#{\"type\":\"state\",\"id\":")); Serial.print(id);
  Serial.print(F(",\"gain\":")); Serial.print(gainCode);
  Serial.print(F(",\"cycles\":")); Serial.print(integrationCycles);
  Serial.print(F(",\"format\":\"")); Serial.print(calibrated ? F("calibrated") : F("raw"));
  Serial.print(F("\",\"stream\":")); Serial.print(streaming ? 1 : 0);
  Serial.print(F(",\"led\":["));
  for (uint8_t i=0; i<3; ++i) { if(i) Serial.print(','); Serial.print(drivers[i] ? 1 : 0); }
  Serial.print(F("],\"current\":["));
  for (uint8_t i=0; i<3; ++i) { if(i) Serial.print(','); Serial.print(driverCurrent[i]); }
  Serial.print(F("],\"indicator\":["));
  for (uint8_t i=0; i<3; ++i) { if(i) Serial.print(','); Serial.print(indicators[i] ? 1 : 0); }
  Serial.print(F("],\"indicator_current\":["));
  for (uint8_t i=0; i<3; ++i) { if(i) Serial.print(','); Serial.print(indicatorCurrent[i]); }
  Serial.println(F("]}"));
}

bool applyLED(uint8_t device) {
  return sensor.led(device, drivers[device], driverCurrent[device],
                    indicators[device], indicatorCurrent[device]);
}

bool allOff() {
  bool ok = true;
  for (uint8_t i=0; i<3; ++i) {
    bool oldDriver=drivers[i], oldIndicator=indicators[i];
    drivers[i] = indicators[i] = false;
    if (!applyLED(i)) { drivers[i]=oldDriver; indicators[i]=oldIndicator; ok=false; }
  }
  return ok;
}

void temperatures(unsigned long id) {
  int8_t values[3];
  for (uint8_t i=0; i<3; ++i) {
    if (!sensor.temperature(i, values[i])) { errorReply(id, F("temperature_read_failed")); return; }
  }
  Serial.print(F("#{\"type\":\"temperature\",\"id\":")); Serial.print(id);
  Serial.print(F(",\"values\":["));
  for (uint8_t i=0; i<3; ++i) { if(i) Serial.print(','); Serial.print(values[i]); }
  Serial.println(F("]}"));
}

bool number(char *text, unsigned long &value, unsigned long maximum) {
  if (!text || !*text) return false;
  for (char *p=text; *p; ++p) if (*p<'0' || *p>'9') return false;
  char *end;
  value = strtoul(text, &end, 10);
  return !*end && value <= maximum;
}

void executeCommand(char *line) {
  if (line[0] != '@') return;
  char *save;
  char *idText = strtok_r(line+1, " ", &save);
  char *op = strtok_r(NULL, " ", &save);
  unsigned long id = 0, a = 0, b = 0, c = 0;
  if (!number(idText, id, 65535) || !op) { errorReply(0, F("invalid_request")); return; }
  lastHost=millis();
  char *args[4]; uint8_t argc = 0;
  while (argc < 4 && (args[argc] = strtok_r(NULL, " ", &save))) ++argc;
  if (!strcmp(op,"INFO") && argc==0) { hello(id); state(0); return; }
  if (!strcmp(op,"STATE") && argc==0) { state(id); return; }
  if (!strcmp(op,"PING") && argc==0) {
    Serial.print(F("#{\"type\":\"pong\",\"id\":")); Serial.print(id); Serial.println(F("}")); return;
  }
  if (!sensorOK) { errorReply(id, F("sensor_not_ready")); return; }
  if (!strcmp(op,"TEMP") && argc==0) { temperatures(id); return; }
  if (!strcmp(op,"OFF") && argc==0) {
    if (!allOff()) { errorReply(id, F("i2c_led_failed")); return; }
  } else if ((!strcmp(op,"LED") || !strcmp(op,"IND")) && argc==3 &&
             number(args[0],a,2) && number(args[1],b,1) && number(args[2],c,3)) {
    bool oldEnabled; uint8_t oldCurrent;
    bool driver = !strcmp(op,"LED");
    if (driver) { oldEnabled=drivers[a]; oldCurrent=driverCurrent[a]; drivers[a]=b; driverCurrent[a]=c; }
    else { oldEnabled=indicators[a]; oldCurrent=indicatorCurrent[a]; indicators[a]=b; indicatorCurrent[a]=c; }
    if (!applyLED(a)) {
      if (driver) { drivers[a]=oldEnabled; driverCurrent[a]=oldCurrent; }
      else { indicators[a]=oldEnabled; indicatorCurrent[a]=oldCurrent; }
      errorReply(id,F("i2c_led_failed")); return;
    }
  } else if (!strcmp(op,"SET") && argc==3 && number(args[0],a,3) &&
             number(args[1],b,256) && b>=1 && (!strcmp(args[2],"raw") || !strcmp(args[2],"calibrated"))) {
    if (!sensor.configure(a,b)) {
      // A multi-register update may have been only partly applied. Do not emit
      // samples labelled with the previous gain/exposure after this failure.
      errorReply(id,F("i2c_settings_failed")); allOff();
      sensorOK=false; streaming=false; measuring=false; hello(0); return;
    }
    gainCode=a; integrationCycles=b; calibrated=!strcmp(args[2],"calibrated");
    measuring=true; conversionStarted=millis();
  } else if (!strcmp(op,"RUN") && argc==1 && number(args[0],a,1)) {
    streaming=a;
  } else if (!strcmp(op,"SHOT") && argc==0) {
    if (streaming || measuring) { errorReply(id,F("pause_before_single_shot")); return; }
    if (!sensor.start(gainCode)) { errorReply(id,F("i2c_start_failed")); return; }
    measuring=true; conversionStarted=millis();
  } else { errorReply(id,F("invalid_command_or_range")); return; }
  state(id);
}

void serialCommands() {
  // Bound work per loop; no blocking readString/readUntil or heap-allocated String.
  for (uint8_t budget=0; budget<64 && Serial.available(); ++budget) {
    char ch=Serial.read();
    if (ch=='\r') continue;
    if (ch=='\n') {
      if (discardCommand) errorReply(0,F("command_too_long"));
      else if (commandLength) { commandLine[commandLength]=0; executeCommand(commandLine); }
      commandLength=0; discardCommand=false;
    } else if (!discardCommand) {
      if (commandLength < sizeof(commandLine)-1) commandLine[commandLength++]=ch;
      else { commandLength=0; discardCommand=true; }
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000); // AS72651 serial-flash boot; once at startup only.
  sensorOK=sensor.begin();
  if (sensorOK) sensorOK=allOff() && sensor.configure(gainCode,integrationCycles);
  hello(0); state(0);
  measuring=sensorOK; conversionStarted=millis();
  lastHost=millis();
}

void loop() {
  serialCommands();
  if (!sensorOK) return;
  if (millis()-lastHost > 6000UL) {
    bool illuminated=false;
    for (uint8_t i=0; i<3; ++i) if (drivers[i] || indicators[i]) illuminated=true;
    if (illuminated) {
      if (!allOff()) errorReply(0,F("heartbeat_led_off_failed"));
      state(0); lastHost=millis();
    }
  }
  if (!measuring && streaming) {
    if (!sensor.start(gainCode)) { errorReply(0,F("i2c_start_failed")); sensorOK=false; allOff(); return; }
    measuring=true; conversionStarted=millis();
  }
  if (measuring && millis()-lastPoll >= 2) {
    lastPoll=millis(); bool available=false;
    if (!sensor.ready(available)) { errorReply(0,F("i2c_poll_failed")); sensorOK=false; allOff(); return; }
    if (available) {
      float values[18];
      if (!sensor.spectrum(values,calibrated)) { errorReply(0,F("i2c_frame_failed")); sensorOK=false; allOff(); return; }
      bool valid=true;
      for (uint8_t i=0; i<18; ++i) if (!isfinite(values[i])) valid=false;
      if (valid) {
        for (uint8_t i=0; i<18; ++i) { if(i) Serial.print(','); Serial.print(values[i],calibrated ? 4 : 0); }
        Serial.println();
      } else errorReply(0,F("non_finite_sensor_value"));
      measuring=false;
    } else if (millis()-conversionStarted > 2000UL) {
      errorReply(0,F("conversion_timeout")); streaming=false; measuring=false; allOff(); state(0);
    }
  }
  if (!measuring && millis()-lastTelemetry > 2000UL) {
    lastTelemetry=millis(); temperatures(0);
  }
}
