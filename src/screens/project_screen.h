#pragma once

#include "screen.h"
#include <filesystem>
#include <vector>
#include <string>

// Represents a discovered asset in the project
struct AssetInfo {
    std::string name;
    std::filesystem::path path;
    std::string extension;
};

class ProjectScreen : public Screen
{
public:
    explicit ProjectScreen(std::filesystem::path& projectPath);

    void onEnter() override;
    void update() override;

private:
    std::filesystem::path& projectPath;
    
    // Selection state
    std::filesystem::path selectedFilePath;
    std::filesystem::path selectedAssetPath;
    
    // Cached asset lists
    std::vector<AssetInfo> scenes;
    std::vector<AssetInfo> models;
    
    // Panel width (resizable in future)
    float panelWidth = 280.0f;
    
    // New folder dialog state
    bool showNewFolderPopup = false;
    std::filesystem::path newFolderParentPath;
    char newFolderName[256] = "";
    
    // Context menu state
    std::filesystem::path contextMenuPath;
    
    // Rendering helpers
    void renderFileTree(const std::filesystem::path& path);
    void renderAssetList(const std::vector<AssetInfo>& assets, const char* emptyMessage);
    
    // Asset discovery
    void scanProjectAssets();
    void scanDirectory(const std::filesystem::path& dir);
    void categorizeAsset(const std::filesystem::path& path);
    
    // Folder operations
    void openNewFolderDialog(const std::filesystem::path& parentPath);
    void createNewFolder();
    void renderNewFolderPopup();
};
