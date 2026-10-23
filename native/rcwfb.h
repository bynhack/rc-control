// C interface over Aviateur's WfbngLink (RTL8812AU via devourer + wfb-ng),
// consumed from Rust. One link at a time.

#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint16_t vendor_id;
    uint16_t product_id;
    uint8_t bus_num;
    uint8_t port_num;
    bool known_adapter;
    char name[128];
} RcwfbDevice;

typedef struct {
    long long wifi_frames;
    long long wfb_frames;
    long long rtp_packets;
    int link_score[2];
    int packet_loss;
    /// 0 unknown, 1 H.264, 2 H.265 (detected from the stream).
    int codec;
    int payload_type;
    bool running;
    bool stopped_by_device;
} RcwfbStats;

/// level: 0 info, 1 debug, 2 warn, 3 error. Called from radio threads.
void rcwfb_set_log(void (*sink)(int level, const char *message));

/// Fills up to `max` adapters; returns how many were found.
int rcwfb_list_devices(RcwfbDevice *out, int max);

/// Starts receiving. Video RTP goes to UDP 127.0.0.1:`video_port`.
/// channel: e.g. 161; width_mode: 0 = 20 MHz, 1 = 40 MHz.
bool rcwfb_start(const RcwfbDevice *device, uint8_t channel, int width_mode, const char *key_path, int video_port);

void rcwfb_stop(void);

void rcwfb_stats(RcwfbStats *out);

#ifdef __cplusplus
}
#endif
