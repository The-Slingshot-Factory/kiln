#pragma once

#include "screen.h"
#include "../renderer/scene_renderer.h"
#include "../scene/scene.h"
#include <filesystem>
#include <vector>
#include <string>

// Represents a discovered scene in the project
struct SceneInfo {
    std::string name;
    std::filesystem::path path;
};

class ProjectScreen : public Screen
{
public:
    explicit ProjectScreen(std::filesystem::path& projectPath);

    void onEnter() override;
    void onExit() override;
    void update() override;

private:
    std::filesystem::path& projectPath;
    
    // Selection state
    std::filesystem::path selectedFilePath;
    std::filesystem::path selectedScenePath;
    
    // Cached scenes list
    std::vector<SceneInfo> scenes;
    
    // Panel width (resizable in future)
    float panelWidth = 280.0f;
    
    // New folder dialog state
    bool showNewFolderPopup = false;
    std::filesystem::path newFolderParentPath;
    char newFolderName[256] = "";
    
    // New scene dialog state
    bool showNewScenePopup = false;
    char newSceneName[256] = "";
    std::filesystem::path newSceneLocation;
    bool newSceneWithGroundPlane = true;  // true = with ground plane, false = empty
    
    // Context menu state
    std::filesystem::path contextMenuPath;
    
    // 3D Viewport
    SceneRenderer sceneRenderer;
    Scene currentScene;  // Currently loaded scene
    bool rendererInitialized = false;
    float lastViewportWidth = 0;
    float lastViewportHeight = 0;
    
    // Properties panel
    float propertiesPanelWidth = 280.0f;
    SceneNode* selectedNode = nullptr;  // Selected object (nullptr = scene selected)
    bool sceneModified = false;  // Track unsaved changes
    
    // Rendering helpers
    void renderFileTree(const std::filesystem::path& path);
    void renderScenesList();
    
    // Scene discovery
    void scanProjectScenes();
    void scanDirectory(const std::filesystem::path& dir);
    
    // Folder operations
    void openNewFolderDialog(const std::filesystem::path& parentPath);
    void createNewFolder();
    void renderNewFolderPopup();
    
    // File/Folder deletion
    void deleteFileOrFolder(const std::filesystem::path& path);
    
    // Scene operations
    void openNewSceneDialog();
    void createNewScene();
    void renderNewScenePopup();
    void deleteScene(const std::filesystem::path& scenePath);
    
    // Viewport
    void renderViewport();
    void renderCameraControls();
    
    // Properties panel
    void renderPropertiesPanel();
    void renderSceneProperties();
    void renderNodeProperties(SceneNode* node);
    
    // Scene loading/saving
    void loadScene(const std::filesystem::path& scenePath);
    void saveScene();
};
