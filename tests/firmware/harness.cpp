#include <cassert>
#include <cmath>
#include <iostream>
#include "../../firmware/AS7265xController/AS7265xController.ino"

void command(const char *text) {
  char line[96];
  strncpy(line,text,sizeof(line)); line[sizeof(line)-1]=0;
  executeCommand(line);
}

int main() {
  setup();
  assert(sensorOK && integrationCycles==10 && Wire.cycles==9);
  for (int i=0;i<3;++i) assert((Wire.leds[i] & 9)==0);
  command("@1 LED 1 1 3");
  assert(drivers[1] && Wire.leds[1]==0x38 && !drivers[0] && !drivers[2]);
  command("@2 IND 2 1 1");
  assert(indicators[2] && Wire.leds[2]==3);
  command("@3 SET 3 256 raw");
  assert(gainCode==3 && integrationCycles==256 && Wire.cycles==255 && !calibrated);
  command("@4 SET 9 0 calibrated");
  assert(gainCode==3 && integrationCycles==256 && !calibrated);
  command("@5 LED 3 1 0");
  assert(drivers[1] && !drivers[0]);
  float values[18];
  assert(sensor.spectrum(values,true));
  const float expected[18]={20.5,21.5,22.5,23.5,24.5,25.5,10.5,11.5,0.5,12.5,1.5,13.5,2.5,3.5,4.5,5.5,14.5,15.5};
  for(int i=0;i<18;++i) assert(std::fabs(values[i]-expected[i])<0.001);
  assert(sensor.spectrum(values,false));
  assert(values[0]==200 && values[8]==0 && values[17]==105);
  Wire.fail=true;
  command("@6 LED 0 1 0");
  assert(!drivers[0]); // Failed I2C operation is not reported as applied.
  Wire.fail=false;
  command("@7 TEMP");
  command("@8 RUN 0");
  assert(!streaming);
  measuring=false;
  command("@9 SHOT");
  assert(measuring);
  delay(3); loop();
  assert(!measuring);
  command("@10 PING");
  command("@11 OFF");
  for (int i=0;i<3;++i) assert(!drivers[i] && !indicators[i] && !(Wire.leds[i]&9));
  command("@12 LED 0 1 0");
  delay(6001); loop();
  assert(!drivers[0]); // Loss of host heartbeats releases illumination.
  for(int i=0;i<110;++i) Serial.input.push_back('X');
  Serial.input.push_back('\n');
  for(char c:std::string("@13 STATE\n")) Serial.input.push_back(c);
  while(Serial.available()) serialCommands();
  assert(commandLength==0 && !discardCommand);
  std::cout << Serial.output.str();
}
