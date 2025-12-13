#pragma once

#include "screen.h"
#include <filesystem>

class WelcomeScreen : public Screen
{
public:
    explicit WelcomeScreen(std::filesystem::path& projectPath);

    void update() override;

private:
    std::filesystem::path& projectPath;
};

