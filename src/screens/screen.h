#pragma once

#include <memory>

class Screen
{
public:
    virtual ~Screen() = default;

    // Called when screen becomes active
    virtual void onEnter() {}

    // Called when screen is deactivated
    virtual void onExit() {}

    // Draw and handle UI - called every frame
    virtual void update() = 0;

    // Request to switch to a new screen (set by screens, consumed by main loop)
    std::unique_ptr<Screen> nextScreen = nullptr;

protected:
    // Helper to request a screen transition
    template<typename T, typename... Args>
    void switchTo(Args&&... args)
    {
        nextScreen = std::make_unique<T>(std::forward<Args>(args)...);
    }
};

