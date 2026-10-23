// Stand-in for Aviateur's src/gui_interface.h.
//
// Aviateur's radio code (src/wifi) reports to its GUI through the
// GuiInterface singleton. The build stages those sources next to this file
// instead of the real header, so they compile unmodified while their logs,
// counters and stream info flow to rc-control through rcwfb.cpp.

#pragma once

#include <atomic>
#include <cstdint>
#include <format>
#include <mutex>
#include <string>
#include <string_view>

enum class LogLevel {
    Info,
    Debug,
    Warn,
    Error,
};

using RcwfbLogSink = void (*)(int level, const char *message);

/// Aviateur assigns "H264"/"H265" from its receive thread and reads it back
/// as a std::string; an atomic code keeps that race-free for our reader.
struct CodecSlot {
    std::atomic<int> code{0}; // 0 unknown, 1 H.264, 2 H.265

    CodecSlot &operator=(const char *name) {
        code = std::string_view(name) == "H264" ? 1 : 2;
        return *this;
    }

    operator std::string() const {
        switch (code.load()) {
            case 1:
                return "H264";
            case 2:
                return "H265";
            default:
                return "";
        }
    }
};

class GuiInterface {
public:
    static GuiInterface &Instance() {
        static GuiInterface instance;
        return instance;
    }

    template <typename... Args>
    void PutLog(LogLevel level, const std::string_view message, Args... format_items) {
        EmitLog(level, std::vformat(message, std::make_format_args(format_items...)));
    }

    void EmitLog(LogLevel level, const std::string &msg) {
        std::lock_guard lock(sink_mutex);
        if (sink) {
            sink(static_cast<int>(level), msg.c_str());
        }
    }

    void ShowTip(const std::string &msg, bool bad_news) {
        EmitLog(bad_news ? LogLevel::Error : LogLevel::Info, msg);
    }

    // Counters are polled by rc-control; nothing to push.
    void UpdateCount() {}

    void EmitWifiStopped() {
        wifi_stopped = true;
    }

    void NotifyRtpStream(int pt, uint32_t /*ssrc*/, int /*port*/, const std::string & /*codec*/) {
        payload_type = pt;
    }

    std::atomic<long long> wifiFrameCount_{0};
    std::atomic<long long> wfbngFrameCount_{0};
    std::atomic<long long> rtpPktCount_{0};
    std::atomic<int> drone_fec_level_{0};
    /// Where the decrypted video RTP is sent: rc-control's video receiver.
    int playerPort = 5600;
    CodecSlot playerCodec;

    std::atomic<int> payload_type{-1};
    std::atomic<bool> wifi_stopped{false};

    std::mutex sink_mutex;
    RcwfbLogSink sink = nullptr;
};
