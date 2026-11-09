// Lap-timing transponder: a CH32V003J4M6 (SOP-8) in each car flashes its
// car number on a 940 nm IR LED, up through a window, for the finish-line
// arch to read.
//
// The light is 38 kHz bursts, so the arch can use ordinary TSOP-style IR
// receivers (sunlight and lamps don't trip them). One frame, T = 400 us
// (about 15 carrier cycles):
//
//   header   burst 4T, gap 2T
//   8 bits   LSB first, each burst 1T then gap 1T (0) or 2T (1):
//            bits 0..3 the car number 1..15, bits 4..7 its complement
//   stop     burst 1T
//
// 23..31 T long (9.2..12.4 ms). Frames repeat after a random 4..12 ms gap,
// so two cars side by side don't keep hitting each other's frames. A car at
// 5 m/s is under the arch for a few frames; the arch takes the middle of the
// first and last frame it reads as the crossing.
//
// Car number: set when flashing, `make flash CAR=3` (1..15), so every car
// runs the same board and the WCH-LinkE gives each its number. Flashed
// without CAR, it falls back to the three solder jumpers: 1 + JP1 (PC1,
// bit 0) + JP2 (PC2, bit 1) + JP3 (PA2, bit 2); no jumpers = car 1.
//
// Pins: PC4 (TIM1_CH4) -> the LED driver MOSFET's gate. PD1 = SWIO, for
// the WCH-LinkE. VDD is the car's 5 V.
//
// Build with ch32fun (https://github.com/cnlohr/ch32fun): make, make flash.

#include "ch32fun.h"

#ifndef CAR_ID
#define CAR_ID 0  // 0: read the jumpers
#endif
#if CAR_ID < 0 || CAR_ID > 15
#error "CAR must be 1..15"
#endif

#define T_US 400
#define CARRIER_HZ 38000
#define PERIOD (FUNCONF_SYSTEM_CORE_CLOCK / CARRIER_HZ)  // timer ticks per carrier cycle
#define DUTY (PERIOD / 3)                                 // a third on: brighter per mA, and the receivers like it

static uint32_t rng;

static uint32_t rand32(void)
{
	// xorshift32: no multiply, the V003 has none.
	rng ^= rng << 13;
	rng ^= rng >> 17;
	rng ^= rng << 5;
	return rng;
}

static void burst(int t)
{
	TIM1->CH4CVR = DUTY;
	Delay_Us(t * T_US);
	TIM1->CH4CVR = 0;  // PWM mode 1 with 0: the output stays low, the LED off
}

static void gap(int t)
{
	Delay_Us(t * T_US);
}

static void frame(int car)
{
	int data = (car & 0x0f) | ((~car & 0x0f) << 4);
	burst(4);
	gap(2);
	for (int i = 0; i < 8; i++) {
		burst(1);
		gap((data >> i) & 1 ? 2 : 1);
	}
	burst(1);
}

static int car_number(void)
{
	if (CAR_ID)
		return CAR_ID;
	// Jumpers pull to ground; the inputs pull up.
	funPinMode(PC1, GPIO_CFGLR_IN_PUPD);
	funPinMode(PC2, GPIO_CFGLR_IN_PUPD);
	funPinMode(PA2, GPIO_CFGLR_IN_PUPD);
	funDigitalWrite(PC1, FUN_HIGH);
	funDigitalWrite(PC2, FUN_HIGH);
	funDigitalWrite(PA2, FUN_HIGH);
	Delay_Us(50);
	int n = (!funDigitalRead(PC1)) | (!funDigitalRead(PC2)) << 1 | (!funDigitalRead(PA2)) << 2;
	return 1 + n;
}

static void carrier_init(void)
{
	RCC->APB2PCENR |= RCC_APB2Periph_TIM1;
	funPinMode(PC4, GPIO_CFGLR_OUT_10Mhz_AF_PP);
	TIM1->PSC = 0;
	TIM1->ATRLR = PERIOD - 1;
	TIM1->CH4CVR = 0;
	TIM1->CHCTLR2 = TIM_OC4M_2 | TIM_OC4M_1;  // PWM mode 1, no preload: a burst starts at once
	TIM1->CCER = TIM_CC4E;
	TIM1->BDTR = TIM_MOE;
	TIM1->SWEVGR = TIM_UG;
	TIM1->CTLR1 = TIM_CEN;
}

int main(void)
{
	SystemInit();
	funGpioInitAll();
	int car = car_number();
	// Seed from the chip's unique ID, so two cars with the same number
	// (by mistake) still drift apart instead of colliding every frame.
	rng = *(volatile uint32_t *)0x1FFFF7E8 ^ *(volatile uint32_t *)0x1FFFF7EC ^ (uint32_t)car;
	if (!rng)
		rng = 1;
	carrier_init();
	for (;;) {
		frame(car);
		gap(10);  // 4 ms
		Delay_Us(rand32() % 8000);
	}
}
