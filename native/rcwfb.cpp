#include "rcwfb.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <memory>
#include <mutex>

#include "gui_interface.h"
#include "wifi/wfbng_link.h"

namespace {

std::mutex g_mutex;
std::shared_ptr<WfbngLink> g_link;

} // namespace

extern "C" {

void rcwfb_set_log(void (*sink)(int level, const char *message)) {
    auto &gi = GuiInterface::Instance();
    std::lock_guard lock(gi.sink_mutex);
    gi.sink = sink;
}

int rcwfb_list_devices(RcwfbDevice *out, int max) {
    const auto devices = WfbngLink::get_device_list();
    const int n = std::min<int>(static_cast<int>(devices.size()), max);
    for (int i = 0; i < n; ++i) {
        const DeviceId &d = devices[i];
        RcwfbDevice &o = out[i];
        o.vendor_id = d.vendor_id;
        o.product_id = d.product_id;
        o.bus_num = d.bus_num;
        o.port_num = d.port_num;
        o.known_adapter = d.known_adapter;
        std::snprintf(o.name, sizeof(o.name), "%s", d.display_name.c_str());
    }
    return static_cast<int>(devices.size());
}

bool rcwfb_start(const RcwfbDevice *device, uint8_t channel, int width_mode, const char *key_path, int video_port) {
    std::lock_guard lock(g_mutex);
    if (g_link) {
        return false;
    }
    auto &gi = GuiInterface::Instance();
    gi.playerPort = video_port;
    gi.wifi_stopped = false;
    gi.payload_type = -1;

    DeviceId id{
        .vendor_id = device->vendor_id,
        .product_id = device->product_id,
        .bus_num = device->bus_num,
        .port_num = device->port_num,
        .display_name = device->name,
        .known_adapter = device->known_adapter,
    };
    auto link = std::make_shared<WfbngLink>();
    if (!link->start(id, channel, width_mode, key_path)) {
        return false;
    }
    g_link = link;
    return true;
}

void rcwfb_stop(void) {
    std::shared_ptr<WfbngLink> link;
    {
        std::lock_guard lock(g_mutex);
        link.swap(g_link);
    }
    if (link) {
        link->stop();
    }
}

void rcwfb_stats(RcwfbStats *out) {
    auto &gi = GuiInterface::Instance();
    *out = RcwfbStats{};
    out->wifi_frames = gi.wifiFrameCount_;
    out->wfb_frames = gi.wfbngFrameCount_;
    out->rtp_packets = gi.rtpPktCount_;
    out->codec = gi.playerCodec.code;
    out->payload_type = gi.payload_type;
    out->stopped_by_device = gi.wifi_stopped;

    std::lock_guard lock(g_mutex);
    out->running = g_link != nullptr && !gi.wifi_stopped;
    if (g_link) {
        const auto score = g_link->get_link_score();
        out->link_score[0] = score[0];
        out->link_score[1] = score[1];
        out->packet_loss = g_link->get_packet_loss();
    }
}

} // extern "C"
