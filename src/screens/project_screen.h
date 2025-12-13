#pragma once

#include "screen.h"
#include <filesystem>

class ProjectScreen : public Screen
{
public:
    explicit ProjectScreen(std::filesystem::path& projectPath);

    void update() override;

private:
    std::filesystem::path& projectPath;
};

