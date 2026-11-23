// A scripted controller for unattended test runs: timed button presses from the cvar sasrt_input_script, fed to guest
// user 0 as a synthetic device, so a minimized test run can get through the menus and into a race. The format is in
// sasrt_input_script.cpp.

#pragma once

namespace rex {
class Runtime;
}

namespace sasrt::input_script {

// Adds the scripted device to the runtime's input system when sasrt_input_script is set.
void Install(rex::Runtime* runtime);

}  // namespace sasrt::input_script
