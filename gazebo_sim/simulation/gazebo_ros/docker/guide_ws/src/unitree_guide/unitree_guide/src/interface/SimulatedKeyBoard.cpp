#include <iostream>
#include <thread>
#include <chrono>
#include <cmath>
#include "interface/SimulatedKeyBoard.h"

SimulatedKeyBoard::SimulatedKeyBoard() : running(true) {
    userCmd = UserCommand::NONE;
    userValue.setZero();

    // Start the thread to simulate input
    inputThread = std::thread(&SimulatedKeyBoard::simulateInput, this);
}

SimulatedKeyBoard::~SimulatedKeyBoard() {
    running = false;
    if (inputThread.joinable()) {
        inputThread.join();
    }
}

void* SimulatedKeyBoard::run(void *arg) {
    return nullptr; // Override run from CmdPanel
}

void SimulatedKeyBoard::simulateInput() {
    int step = 0;
    while (running) {
        // Simulate discrete commands
        switch (step % 4) {
        case 0:
            userCmd = UserCommand::L2_B;
            break;
        case 1:
            userCmd = UserCommand::START;
            break;
        case 2:
            userCmd = UserCommand::L2_A;
            break;
        case 3:
            userCmd = UserCommand::NONE;
            break;
        }

        // Simulate continuous control values
        userValue.lx = std::sin(step * 0.1); // Simulate lateral oscillation
        userValue.ly = std::cos(step * 0.1); // Simulate longitudinal oscillation
        userValue.rx = 0.5 * std::sin(step * 0.05); // Simulate slow rotational oscillation
        userValue.ry = 0.5 * std::cos(step * 0.05); // Simulate slow rotational oscillation

        // Print current simulated values
        std::cout << "Simulated UserCmd: " << static_cast<int>(userCmd) << std::endl;
        std::cout << "Simulated UserValue: (lx=" << userValue.lx
                  << ", ly=" << userValue.ly
                  << ", rx=" << userValue.rx
                  << ", ry=" << userValue.ry << ")" << std::endl;

        // Wait before updating (e.g., simulate a 10 Hz update rate)
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        step++;
    }
}
