#include <Arduino.h>

// put function declarations here:
//#define RGB_BRIGHTNESS 64 // Change white brightness (max 255)

// the setup function runs once when you press reset or power the board
#define RGB_BUILTIN 48
#define RGB_BRIGHTNESS 255

void setup() {
  // No need to initialize the RGB LED
   pinMode(RGB_BUILTIN , OUTPUT);   
}

// the loop function runs over and over again forever
void loop() {
//#ifdef RGB_BUILTIN
  neopixelWrite(RGB_BUILTIN, 255, 255, 255);  // BRIGHT White
  delay(500);
  //   neopixelWrite(RGB_BUILTIN, 64, 64, 64);  // Soft White 
  //delay(500);
  neopixelWrite(RGB_BUILTIN, RGB_BRIGHTNESS, 0, 0);  // Red
  delay(500);
  neopixelWrite(RGB_BUILTIN, RGB_BRIGHTNESS, RGB_BRIGHTNESS, 0 );  // Yellow
  delay(500);
  neopixelWrite(RGB_BUILTIN, 0, RGB_BRIGHTNESS/2, 0);  // Green
  delay(500);
  neopixelWrite(RGB_BUILTIN, 0, 0,RGB_BRIGHTNESS);  // Blue
//#endif
}
