// A scripted controller for unattended test runs (see sasrt_input_script.h).
//
// sasrt_input_script holds timed presses separated by ';':
//
//   <when>[+<seconds held>]=<input>[+<input>...]
//
//   when      seconds after start ("35", "41.5"), or a game frame ("f1800": the 1800th D3DDevice_Swap), which keeps
//             a script in step with the game when it runs slower than real time
//   held      how long the inputs stay down, in seconds (default 0.15); for a frame-timed press, "<n>f" holds them for
//             n game frames ("f1800+9f=A"), so lockstep runs (vblank_per_swap) give the game the same input on the
//             same frames whatever the PC's speed
//   input     A B X Y START BACK LB RB LS RS UP DOWN LEFT RIGHT (buttons and d-pad), LT RT (triggers, fully
//             pressed), LX+ LX- LY+ LY- RX+ RX- RY+ RY- (sticks pushed fully)
//
// Example: "30=A; 33=START; 36=A; 40+1=DOWN; 45=A; 60+120=RT" presses A at 30 s, START at 33 s, ..., then holds the
// right trigger (accelerate) for two minutes from 60 s. Each press is logged ("[input-script] ..."), so a log shows
// what the game was given. The device is synthetic: InputSystem feeds it to guest user 0 together with any real pad
// (buttons OR-ed, the larger stick deflection wins).

#include "sasrt_input_script.h"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include <rex/cvar.h>
#include <rex/input/input_driver.h>
#include <rex/input/input_system.h>
#include <rex/logging.h>
#include <rex/runtime.h>

#include "sasrt_capture.h"

REXCVAR_DEFINE_STRING(sasrt_input_script, "", "SASRT",
                      "Scripted controller presses for unattended test runs, e.g. \"30=A; 60+120=RT\" "
                      "(app/src/sasrt_input_script.cpp)");
// sasrt-nx (2026-11-20, split-screen test runs on the emulator): players 2-4's scripted controllers (guest users 1-3),
// the same format; each a device of its own.
REXCVAR_DEFINE_STRING(sasrt_input_script_p2, "", "SASRT", "sasrt_input_script for player 2 (guest user 1)");
REXCVAR_DEFINE_STRING(sasrt_input_script_p3, "", "SASRT", "sasrt_input_script for player 3 (guest user 2)");
REXCVAR_DEFINE_STRING(sasrt_input_script_p4, "", "SASRT", "sasrt_input_script for player 4 (guest user 3)");

namespace sasrt::input_script {
namespace {

using rex::X_RESULT;
using rex::X_STATUS;

constexpr rex::input::DeviceId kScriptDevice = static_cast<rex::input::DeviceId>(0x53435249);  // "SCRI"

struct Step {
  bool by_frame = false;
  double at = 0;      // seconds, or a frame number
  double held = 0.15;  // seconds
  double held_frames = 0;  // a frame-timed press held for game frames ("+<n>f"), not seconds
  uint16_t buttons = 0;
  uint8_t left_trigger = 0, right_trigger = 0;
  int16_t lx = 0, ly = 0, rx = 0, ry = 0;
  std::string text;
};

bool ApplyInput(const std::string& name, Step& s) {
  struct Button {
    const char* name;
    uint16_t mask;
  };
  static const Button kButtons[] = {
      {"UP", 0x0001}, {"DOWN", 0x0002}, {"LEFT", 0x0004}, {"RIGHT", 0x0008}, {"START", 0x0010},
      {"BACK", 0x0020}, {"LS", 0x0040}, {"RS", 0x0080}, {"LB", 0x0100}, {"RB", 0x0200},
      {"A", 0x1000}, {"B", 0x2000}, {"X", 0x4000}, {"Y", 0x8000},
  };
  for (const auto& b : kButtons) {
    if (name == b.name) {
      s.buttons |= b.mask;
      return true;
    }
  }
  if (name == "LT") {
    s.left_trigger = 255;
  } else if (name == "RT") {
    s.right_trigger = 255;
  } else if (name == "LX+") {
    s.lx = 32767;
  } else if (name == "LX-") {
    s.lx = -32768;
  } else if (name == "LY+") {
    s.ly = 32767;
  } else if (name == "LY-") {
    s.ly = -32768;
  } else if (name == "RX+") {
    s.rx = 32767;
  } else if (name == "RX-") {
    s.rx = -32768;
  } else if (name == "RY+") {
    s.ry = 32767;
  } else if (name == "RY-") {
    s.ry = -32768;
  } else {
    return false;
  }
  return true;
}

std::string Trim(std::string s) {
  const auto not_space = [](unsigned char c) { return !std::isspace(c); };
  s.erase(s.begin(), std::find_if(s.begin(), s.end(), not_space));
  s.erase(std::find_if(s.rbegin(), s.rend(), not_space).base(), s.end());
  return s;
}

std::vector<Step> Parse(std::string script) {
  std::erase(script, '"');  // string cvars can come back quoted
  std::vector<Step> steps;
  size_t pos = 0;
  while (pos <= script.size()) {
    size_t end = script.find(';', pos);
    if (end == std::string::npos) {
      end = script.size();
    }
    const std::string item = Trim(script.substr(pos, end - pos));
    pos = end + 1;
    if (item.empty()) {
      continue;
    }
    const size_t eq = item.find('=');
    if (eq == std::string::npos) {
      REXLOG_WARN("[input-script] '{}': no '=', skipped", item);
      continue;
    }
    Step s;
    s.text = item;
    std::string when = Trim(item.substr(0, eq));
    if (const size_t plus = when.find('+'); plus != std::string::npos) {
      const std::string hold = Trim(when.substr(plus + 1));
      if (!hold.empty() && (hold.back() == 'f' || hold.back() == 'F')) {
        s.held_frames = std::atof(hold.c_str());
      } else {
        s.held = std::atof(hold.c_str());
      }
      when.resize(plus);
    }
    if (!when.empty() && (when[0] == 'f' || when[0] == 'F')) {
      s.by_frame = true;
      when.erase(0, 1);
    }
    if (s.held_frames > 0 && !s.by_frame) {
      REXLOG_WARN("[input-script] '{}': a hold in frames needs a frame-timed press (f<frame>); held 0.15 s", item);
      s.held_frames = 0;
    }
    s.at = std::atof(when.c_str());
    std::string inputs = item.substr(eq + 1);
    bool ok = true;
    size_t ip = 0;
    while (ip <= inputs.size()) {
      size_t ie = inputs.find('+', ip);
      // "LX+" etc. end in '+': keep the sign with its axis name.
      if (ie != std::string::npos && ie > ip && (inputs.compare(ip, 2, "LX") == 0 || inputs.compare(ip, 2, "LY") == 0 ||
                                                 inputs.compare(ip, 2, "RX") == 0 || inputs.compare(ip, 2, "RY") == 0) &&
          ie == ip + 2) {
        ie = inputs.find('+', ie + 1);
      }
      if (ie == std::string::npos) {
        ie = inputs.size();
      }
      const std::string name = Trim(inputs.substr(ip, ie - ip));
      ip = ie + 1;
      if (!name.empty() && !ApplyInput(name, s)) {
        REXLOG_WARN("[input-script] '{}': unknown input '{}'", item, name);
        ok = false;
      }
    }
    if (ok) {
      steps.push_back(s);
    }
  }
  return steps;
}

class ScriptInputDriver final : public rex::input::InputDriver {
 public:
  // sasrt-nx (2026-11-20): 'user' the guest user it feeds (0-3), its device id kScriptDevice + user.
  ScriptInputDriver(std::vector<Step> steps, uint32_t user)
      : InputDriver(nullptr, 0), steps_(std::move(steps)), start_(std::chrono::steady_clock::now()), user_(user),
        device_(static_cast<rex::input::DeviceId>(uint32_t(kScriptDevice) + user)) {}

  X_STATUS Setup() override { return X_STATUS_SUCCESS; }

  void EnumerateDevices(std::vector<rex::input::DeviceInfo>& out) override {
    rex::input::DeviceInfo info;
    info.id = device_;
    info.name = user_ ? "Input script P" + std::to_string(user_ + 1) : "Input script";
    info.synthetic = true;
    info.synthetic_user = user_;
    out.push_back(info);
  }

  X_RESULT GetDeviceState(rex::input::DeviceId id, rex::input::X_INPUT_STATE* out_state) override {
    if (id != device_) {
      return X_ERROR_DEVICE_NOT_CONNECTED;
    }
    const double now =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start_).count();
    const double frame = double(g_sasrt_game_frames.load(std::memory_order_relaxed));
    Step merged;
    std::vector<size_t> active;
    for (size_t i = 0; i < steps_.size(); ++i) {
      const Step& s = steps_[i];
      double start_s = s.at;
      if (s.by_frame && s.held_frames > 0) {
        // Down from game frame `at` for held_frames frames: the same frames in every run (lockstep).
        if (frame < s.at || frame >= s.at + s.held_frames) {
          continue;
        }
      } else if (s.by_frame) {
        // A frame-timed press starts when the game reaches that frame and lasts its held time in real seconds.
        std::lock_guard lock(mutex_);
        if (frame < s.at) {
          continue;
        }
        if (frame_started_.size() < steps_.size()) {
          frame_started_.resize(steps_.size(), -1.0);
        }
        if (frame_started_[i] < 0) {
          frame_started_[i] = now;
        }
        start_s = frame_started_[i];
      }
      if (!(s.by_frame && s.held_frames > 0) && (now < start_s || now >= start_s + s.held)) {
        continue;
      }
      active.push_back(i);
      merged.buttons |= s.buttons;
      merged.left_trigger = std::max(merged.left_trigger, s.left_trigger);
      merged.right_trigger = std::max(merged.right_trigger, s.right_trigger);
      if (s.lx) merged.lx = s.lx;
      if (s.ly) merged.ly = s.ly;
      if (s.rx) merged.rx = s.rx;
      if (s.ry) merged.ry = s.ry;
    }
    {
      std::lock_guard lock(mutex_);
      for (size_t i : active) {
        if (logged_.size() < steps_.size()) {
          logged_.resize(steps_.size(), false);
        }
        if (!logged_[i]) {
          logged_[i] = true;
          REXLOG_INFO("[input-script] {}{:.1f} s, game frame {}: {}", user_ ? "P" + std::to_string(user_ + 1) + " " : "",
                      now, uint64_t(frame), steps_[i].text);
        }
      }
      const uint64_t key = uint64_t(merged.buttons) | uint64_t(merged.left_trigger) << 16 |
                           uint64_t(merged.right_trigger) << 24 | uint64_t(uint16_t(merged.lx)) << 32 |
                           uint64_t(uint16_t(merged.ly)) << 48;
      if (key != last_key_ || merged.rx != last_rx_ || merged.ry != last_ry_) {
        last_key_ = key;
        last_rx_ = merged.rx;
        last_ry_ = merged.ry;
        ++packet_;
      }
    }
    if (out_state) {
      std::memset(out_state, 0, sizeof(*out_state));
      out_state->packet_number = packet_;
      out_state->gamepad.buttons = merged.buttons;
      out_state->gamepad.left_trigger = merged.left_trigger;
      out_state->gamepad.right_trigger = merged.right_trigger;
      out_state->gamepad.thumb_lx = merged.lx;
      out_state->gamepad.thumb_ly = merged.ly;
      out_state->gamepad.thumb_rx = merged.rx;
      out_state->gamepad.thumb_ry = merged.ry;
    }
    return X_ERROR_SUCCESS;
  }

  X_RESULT GetDeviceCapabilities(rex::input::DeviceId id, uint32_t,
                                 rex::input::X_INPUT_CAPABILITIES* out_caps) override {
    if (id != device_) {
      return X_ERROR_DEVICE_NOT_CONNECTED;
    }
    if (out_caps) {
      std::memset(out_caps, 0, sizeof(*out_caps));
      out_caps->type = 0x01;      // XINPUT_DEVTYPE_GAMEPAD
      out_caps->sub_type = 0x01;  // XINPUT_DEVSUBTYPE_GAMEPAD
      out_caps->gamepad.buttons = 0xFFFF;
      out_caps->gamepad.left_trigger = 0xFF;
      out_caps->gamepad.right_trigger = 0xFF;
      out_caps->gamepad.thumb_lx = int16_t(0x7FFF);
      out_caps->gamepad.thumb_ly = int16_t(0x7FFF);
      out_caps->gamepad.thumb_rx = int16_t(0x7FFF);
      out_caps->gamepad.thumb_ry = int16_t(0x7FFF);
    }
    return X_ERROR_SUCCESS;
  }

  X_RESULT SetDeviceVibration(rex::input::DeviceId id, rex::input::X_INPUT_VIBRATION*) override {
    return id == device_ ? X_ERROR_SUCCESS : X_ERROR_DEVICE_NOT_CONNECTED;
  }

  X_RESULT GetDeviceKeystroke(rex::input::DeviceId, uint32_t, rex::input::X_INPUT_KEYSTROKE*) override {
    return X_ERROR_EMPTY;
  }

 private:
  std::vector<Step> steps_;
  std::chrono::steady_clock::time_point start_;
  std::mutex mutex_;
  std::vector<double> frame_started_;
  std::vector<bool> logged_;
  uint64_t last_key_ = 0;
  int16_t last_rx_ = 0, last_ry_ = 0;
  uint32_t packet_ = 1;
  uint32_t user_ = 0;
  rex::input::DeviceId device_;
};

}  // namespace

void Install(rex::Runtime* runtime) {
  if (!runtime) {
    return;
  }
  // sasrt-nx (2026-11-20): a device per scripted player (sasrt_input_script for player 1, _p2.._p4 for users 1-3).
  const std::string scripts[4] = {REXCVAR_GET(sasrt_input_script), REXCVAR_GET(sasrt_input_script_p2),
                                  REXCVAR_GET(sasrt_input_script_p3), REXCVAR_GET(sasrt_input_script_p4)};
  for (uint32_t user = 0; user < 4; ++user) {
    const std::string &script = scripts[user];
    if (script.empty() || script == "\"\"") {
      continue;
    }
    auto steps = Parse(script);
    if (steps.empty()) {
      continue;
    }
    auto* input = static_cast<rex::input::InputSystem*>(runtime->input_system());
    if (!input) {
      REXLOG_WARN("[input-script] no input system");
      return;
    }
    REXLOG_INFO("[input-script] player {}: {} steps", user + 1, steps.size());
    input->AddDriver(std::make_unique<ScriptInputDriver>(std::move(steps), user));
  }
}

}  // namespace sasrt::input_script
