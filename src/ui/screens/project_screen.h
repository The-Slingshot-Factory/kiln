#pragma once

#include "screen.h"
#include "../dialogs/new_folder_dialog.h"
#include "../dialogs/new_scene_dialog.h"
#include "../../renderer/scene_renderer.h"
#include "../../scene/scene.h"
#include "../../scene/primitives/plane_tool.h"
#include <filesystem>
#include <vector>
#include <memory>
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
    
    // Panel widths
    float panelWidth = 280.0f;
    float propertiesPanelWidth = 280.0f;
    
    // Dialogs
    NewFolderDialog newFolderDialog;
    NewSceneDialog newSceneDialog;
    
    // 3D Viewport
    SceneRenderer sceneRenderer;
    Scene currentScene;
    bool rendererInitialized = false;
    float lastViewportWidth = 0;
    float lastViewportHeight = 0;
    
    // Properties panel
    SceneNode* selectedNode = nullptr;
    SceneNode* contextMenuNode = nullptr;  // Node right-clicked in viewport
    
    // Primitive tools
    std::vector<std::unique_ptr<PrimitiveTool>> primitiveTools;
    
    // Rendering
    void renderFileTree(const std::filesystem::path& path);
    void renderScenesList();
    void renderViewport();
    void renderCameraControls();
    void renderPropertiesPanel();
    void renderSceneProperties();
    void renderNodeProperties(SceneNode* node);
    
    // Scene discovery
    void scanProjectScenes();
    void scanDirectory(const std::filesystem::path& dir);
    
    // File operations
    void deleteFileOrFolder(const std::filesystem::path& path);
    void deleteScene(const std::filesystem::path& scenePath);
    
    // Scene loading/saving
    void loadScene(const std::filesystem::path& scenePath);
    void saveScene();
};
