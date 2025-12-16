#pragma once

#include "screen.h"
#include <filesystem>
#include <vector>

class WelcomeScreen : public Screen
{
public:
    explicit WelcomeScreen(std::filesystem::path& projectPath);

    void onEnter() override;
    void update() override;

private:
    std::filesystem::path& projectPath;
    
    // Recent projects
    static constexpr size_t MAX_RECENT_PROJECTS = 10;
    std::vector<std::filesystem::path> recentProjects;
    std::filesystem::path configFilePath;
    
    // Recent projects management
    void loadRecentProjects();
    void saveRecentProjects();
    void addRecentProject(const std::filesystem::path& path);
    void removeRecentProject(const std::filesystem::path& path);
    std::filesystem::path getConfigDirectory();
    
    // Helper
    void openProject(const std::filesystem::path& path);
};
