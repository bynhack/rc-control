// Finish-line lap-timing arch: an ESP32-C3 (or S3) SuperMini reading the
// cars' IR transponders (firmware/transponder) through TSOP38238 receivers
// that look down from the arch, and printing lap events on its USB serial.
//
// Receivers: open-collector outputs, active low. All wired-AND onto one GPIO
// (the default, CONFIG_LAP_IR_GPIOS = "4"), or one per GPIO, each GPIO with
// its own decoder. See docs/en/lap-arch.md.
//
// Each edge is timestamped in the GPIO interrupt and queued; a task runs
// the decoders (ir_decode.c) and the lap tracker (laps.c).
//
// Output, one JSON object per line (115200 is fine, it's USB):
//   {"ev":"boot","inputs":[4],"pass_gap_ms":200,"min_lap_ms":2000}
//   {"ev":"start","car":3,"t_ms":12345,"frames":4,"span_ms":38}
//   {"ev":"lap","car":3,"lap":1,"t_ms":20579,"lap_ms":8234,"frames":3,"span_ms":30}
//   {"ev":"too_soon","car":3,"t_ms":21002,"after_ms":423,"frames":1}
//   {"ev":"frame","car":3,"in":0,"t_ms":12345.6}           ("raw" on)
// t_ms is the arch's clock since boot. A crossing is reported pass_gap_ms
// after the car leaves the arch's view.
//
// Commands (type a line): reset, raw, stats, sim <car> (0 stops), help.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_random.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "ir_decode.h"
#include "laps.h"

#define MAX_INPUTS 8

typedef struct {
	int64_t t;
	uint8_t in, level;
} edge_t;

static int n_inputs;
static gpio_num_t inputs[MAX_INPUTS];
static ir_decoder_t dec[MAX_INPUTS];
static lap_tracker_t laps;
static QueueHandle_t edges;
static volatile uint32_t queue_full;
static volatile int raw;
static volatile int reset_req;
static volatile int sim_car;

static void IRAM_ATTR edge_isr(void *arg)
{
	int in = (int)(intptr_t)arg;
	edge_t e = {.t = esp_timer_get_time(), .in = (uint8_t)in, .level = (uint8_t)gpio_get_level(inputs[in])};
	BaseType_t woken = pdFALSE;
	if (xQueueSendFromISR(edges, &e, &woken) != pdTRUE)
		queue_full++;
	portYIELD_FROM_ISR(woken);
}

static void parse_inputs(void)
{
	char buf[64];
	strlcpy(buf, CONFIG_LAP_IR_GPIOS, sizeof buf);
	for (char *tok = strtok(buf, ", "); tok && n_inputs < MAX_INPUTS; tok = strtok(NULL, ", "))
		inputs[n_inputs++] = (gpio_num_t)atoi(tok);
}

static void inputs_init(void)
{
	gpio_install_isr_service(0);
	for (int i = 0; i < n_inputs; i++) {
		gpio_config_t c = {
			.pin_bit_mask = 1ULL << inputs[i],
			.mode = GPIO_MODE_INPUT,
			.pull_up_en = GPIO_PULLUP_ENABLE,  // weak; the receivers' own pull-ups and the 10k do the work
			.intr_type = GPIO_INTR_ANYEDGE,
		};
		ESP_ERROR_CHECK(gpio_config(&c));
		ir_decoder_init(&dec[i]);
		ESP_ERROR_CHECK(gpio_isr_handler_add(inputs[i], edge_isr, (void *)(intptr_t)i));
	}
}

static void print_event(const lap_event_t *ev)
{
	long long t = ev->t_us / 1000, span = ev->span_us / 1000, lap = ev->lap_us / 1000;
	switch (ev->kind) {
	case LAP_EV_START:
		printf("{\"ev\":\"start\",\"car\":%d,\"t_ms\":%lld,\"frames\":%d,\"span_ms\":%lld}\n", ev->car, t,
		       ev->frames, span);
		break;
	case LAP_EV_LAP:
		printf("{\"ev\":\"lap\",\"car\":%d,\"lap\":%d,\"t_ms\":%lld,\"lap_ms\":%lld,\"frames\":%d,\"span_ms\":%lld}\n",
		       ev->car, ev->lap, t, lap, ev->frames, span);
		break;
	case LAP_EV_TOO_SOON:
		printf("{\"ev\":\"too_soon\",\"car\":%d,\"t_ms\":%lld,\"after_ms\":%lld,\"frames\":%d}\n", ev->car, t, lap,
		       ev->frames);
		break;
	}
}

static void on_frame(int in, const ir_frame_t *f)
{
	lap_frame(&laps, f->car, f->t_us);
	if (raw)
		printf("{\"ev\":\"frame\",\"car\":%d,\"in\":%d,\"t_ms\":%.1f}\n", f->car, in, f->t_us / 1000.0);
}

static void decode_task(void *arg)
{
	edge_t e;
	ir_frame_t f;
	lap_event_t ev;
	for (;;) {
		// Wait for an edge or 2 ms, then take the time *before* draining the
		// queue: every edge older than `now` is then fed in before the
		// decoders are told nothing happened until `now`.
		xQueuePeek(edges, &e, pdMS_TO_TICKS(2));
		int64_t now = esp_timer_get_time();
		while (xQueueReceive(edges, &e, 0) == pdTRUE)
			if (ir_decoder_edge(&dec[e.in], e.t, e.level, &f))
				on_frame(e.in, &f);
		for (int i = 0; i < n_inputs; i++)
			if (ir_decoder_poll(&dec[i], now, &f))
				on_frame(i, &f);
		if (reset_req) {
			reset_req = 0;
			lap_reset(&laps);
			printf("{\"ev\":\"reset\",\"t_ms\":%lld}\n", (long long)(now / 1000));
		}
		while (lap_poll(&laps, now, &ev))
			print_event(&ev);
	}
}

// ---- "sim": send transponder frames on an IR LED, for a bench test ----

#define SIM_DUTY 85  // of 256: a third, like the transponder

static void sim_burst(int t)
{
	ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, SIM_DUTY);
	ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
	esp_rom_delay_us(t * IR_T_US);
	ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
	ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
}

static void sim_task(void *arg)
{
	ledc_timer_config_t tc = {
		.speed_mode = LEDC_LOW_SPEED_MODE,
		.duty_resolution = LEDC_TIMER_8_BIT,
		.timer_num = LEDC_TIMER_0,
		.freq_hz = 38000,
		.clk_cfg = LEDC_AUTO_CLK,
	};
	ESP_ERROR_CHECK(ledc_timer_config(&tc));
	ledc_channel_config_t cc = {
		.gpio_num = CONFIG_LAP_SIM_GPIO,
		.speed_mode = LEDC_LOW_SPEED_MODE,
		.channel = LEDC_CHANNEL_0,
		.timer_sel = LEDC_TIMER_0,
		.duty = 0,
	};
	ESP_ERROR_CHECK(ledc_channel_config(&cc));
	for (;;) {
		int car = sim_car;
		if (!car) {
			vTaskDelay(pdMS_TO_TICKS(20));
			continue;
		}
		// The same frame as firmware/transponder/transponder.c.
		int data = (car & 0x0f) | ((~car & 0x0f) << 4);
		sim_burst(4);
		esp_rom_delay_us(2 * IR_T_US);
		for (int i = 0; i < 8; i++) {
			sim_burst(1);
			esp_rom_delay_us(((data >> i) & 1 ? 2 : 1) * IR_T_US);
		}
		sim_burst(1);
		vTaskDelay(pdMS_TO_TICKS(4 + esp_random() % 9));  // 4..12 ms, sleeping so the idle task runs
	}
}

// ---- commands ----

static void print_stats(void)
{
	for (int i = 0; i < n_inputs; i++)
		printf("{\"ev\":\"stats\",\"in\":%d,\"gpio\":%d,\"frames\":%lu,\"bad_check\":%lu,\"bad_timing\":%lu,"
		       "\"not_quiet\":%lu}\n",
		       i, inputs[i], (unsigned long)dec[i].frames, (unsigned long)dec[i].bad_check,
		       (unsigned long)dec[i].bad_timing, (unsigned long)dec[i].not_quiet);
	printf("{\"ev\":\"stats\",\"queue_full\":%lu}\n", (unsigned long)queue_full);
}

static void command_task(void *arg)
{
	char line[64];
	for (;;) {
		if (!fgets(line, sizeof line, stdin)) {
			vTaskDelay(pdMS_TO_TICKS(50));
			continue;
		}
		line[strcspn(line, "\r\n")] = 0;
		if (!strcmp(line, "reset")) {
			reset_req = 1;
		} else if (!strcmp(line, "raw")) {
			raw = !raw;
			printf("{\"ev\":\"raw\",\"on\":%s}\n", raw ? "true" : "false");
		} else if (!strcmp(line, "stats")) {
			print_stats();
		} else if (!strncmp(line, "sim", 3) && CONFIG_LAP_SIM_GPIO >= 0) {
			int car = atoi(line + 3);
			sim_car = car >= 1 && car <= 15 ? car : 0;
			printf("{\"ev\":\"sim\",\"car\":%d,\"gpio\":%d}\n", sim_car, CONFIG_LAP_SIM_GPIO);
		} else if (line[0]) {
			printf("{\"ev\":\"help\",\"commands\":\"reset | raw | stats | sim <car 1..15, 0 stops>\"}\n");
		}
	}
}

void app_main(void)
{
	// Blocking reads on the USB serial, for the commands.
	usb_serial_jtag_driver_config_t uc = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
	ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&uc));
	usb_serial_jtag_vfs_use_driver();
	setvbuf(stdin, NULL, _IONBF, 0);

	parse_inputs();
	lap_init(&laps, CONFIG_LAP_PASS_GAP_MS * 1000LL, CONFIG_LAP_MIN_LAP_MS * 1000LL);
	edges = xQueueCreate(512, sizeof(edge_t));
	xTaskCreate(decode_task, "decode", 4096, NULL, 10, NULL);
	inputs_init();
	if (CONFIG_LAP_SIM_GPIO >= 0)
		xTaskCreate(sim_task, "sim", 3072, NULL, 2, NULL);
	xTaskCreate(command_task, "cmd", 3072, NULL, 3, NULL);

	printf("{\"ev\":\"boot\",\"inputs\":[");
	for (int i = 0; i < n_inputs; i++)
		printf("%s%d", i ? "," : "", inputs[i]);
	printf("],\"pass_gap_ms\":%d,\"min_lap_ms\":%d}\n", CONFIG_LAP_PASS_GAP_MS, CONFIG_LAP_MIN_LAP_MS);
}
