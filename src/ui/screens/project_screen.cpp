#include "project_screen.h"
#include "welcome_screen.h"
#include "../../scene/scene.h"
#include "imgui.h"
#include "tinyfiledialogs.h"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <functional>
#include <iterator>

// Scene file extensions (OpenUSD formats)
static const std::vector<std::string> SCENE_EXTENSIONS = {".usda", ".usdc", ".usd", ".usdz"};

static bool isSceneFile(const std::string& ext)
{
    std::string lowerExt = ext;
    std::transform(lowerExt.begin(), lowerExt.end(), lowerExt.begin(), ::tolower);
    return std::find(SCENE_EXTENSIONS.begin(), SCENE_EXTENSIONS.end(), lowerExt) != SCENE_EXTENSIONS.end();
}

ProjectScreen::ProjectScreen(std::filesystem::path& path)
    : projectPath(path)
{
    // Initialize tools
    primitiveTools.push_back(std::make_unique<PlaneTool>());
}

void ProjectScreen::onEnter()
{
    scanProjectScenes();
    // Renderer will be initialized on first frame when viewport size is known
}

void ProjectScreen::onExit()
{
    sceneRenderer.cleanup();
    rendererInitialized = false;
}

void ProjectScreen::scanProjectScenes()
{
    scenes.clear();
    
    if (std::filesystem::exists(projectPath) && std::filesystem::is_directory(projectPath))
    {
        scanDirectory(projectPath);
    }
    
    // Sort by name
    std::sort(scenes.begin(), scenes.end(), [](const SceneInfo& a, const SceneInfo& b) {
        return a.name < b.name;
    });
}

void ProjectScreen::scanDirectory(const std::filesystem::path& dir)
{
    try {
        for (const auto& entry : std::filesystem::directory_iterator(dir))
        {
            if (entry.is_directory())
            {
                std::string name = entry.path().filename().string();
                if (name[0] != '.' && name != "build" && name != "node_modules")
                {
                    scanDirectory(entry.path());
                }
            }
            else if (entry.is_regular_file())
            {
                std::string ext = entry.path().extension().string();
                if (!ext.empty() && isSceneFile(ext))
                {
                    SceneInfo info;
                    info.name = entry.path().stem().string();  // Name without extension
                    info.path = entry.path();
                    scenes.push_back(info);
                }
            }
        }
    } catch (const std::filesystem::filesystem_error&) {
    }
}

void ProjectScreen::update()
{
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(viewport->Pos);
    ImGui::SetNextWindowSize(viewport->Size);

    ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar
                           | ImGuiWindowFlags_NoResize
                           | ImGuiWindowFlags_NoMove
                           | ImGuiWindowFlags_NoCollapse
                           | ImGuiWindowFlags_NoBringToFrontOnFocus
                           | ImGuiWindowFlags_MenuBar;

    ImGui::Begin("Project", nullptr, flags);

    // ═══════════════════════════════════════════════
    // Menu Bar
    // ═══════════════════════════════════════════════
    if (ImGui::BeginMenuBar())
    {
        if (ImGui::BeginMenu("File"))
        {
            if (ImGui::BeginMenu("New"))
            {
                if (ImGui::MenuItem("Scene..."))
                {
                    std::filesystem::path loc = (!selectedFilePath.empty() && std::filesystem::is_directory(selectedFilePath))
                                               ? selectedFilePath : projectPath;
                    newSceneDialog.setLocation(loc, projectPath);
                    newSceneDialog.open();
                }
                if (ImGui::MenuItem("Folder"))
                {
                    std::filesystem::path parentPath = (!selectedFilePath.empty() && std::filesystem::is_directory(selectedFilePath))
                                                      ? selectedFilePath : projectPath;
                    newFolderDialog.setParentPath(parentPath);
                    newFolderDialog.open();
                }
                ImGui::EndMenu();
            }
            ImGui::Separator();
            if (ImGui::MenuItem("Refresh", "Ctrl+R"))
            {
                scanProjectScenes();
            }
            ImGui::Separator();
            if (ImGui::MenuItem("Close Project"))
            {
                projectPath.clear();
                switchTo<WelcomeScreen>(projectPath);
            }
            ImGui::Separator();
            if (ImGui::MenuItem("Exit"))
            {
                requestExit();
            }
            ImGui::EndMenu();
        }
        ImGui::EndMenuBar();
    }

    // ═══════════════════════════════════════════════
    // Left Panel: Project Browser
    // ═══════════════════════════════════════════════
    ImGui::BeginChild("ProjectPanel", ImVec2(panelWidth, 0), true);
    
    // --- Section 1: File Tree ---
    ImGui::BeginChild("FileTreeRegion", ImVec2(0, ImGui::GetContentRegionAvail().y * 0.45f), false);
    if (std::filesystem::exists(projectPath))
    {
        ImGuiTreeNodeFlags rootFlags = ImGuiTreeNodeFlags_OpenOnArrow 
                                     | ImGuiTreeNodeFlags_DefaultOpen
                                     | ImGuiTreeNodeFlags_SpanAvailWidth;
        
        bool rootOpen = ImGui::TreeNodeEx(projectPath.filename().string().c_str(), rootFlags);
        
        if (ImGui::BeginPopupContextItem())
        {
            if (ImGui::MenuItem("New Scene..."))
            {
                newSceneDialog.setLocation(projectPath, projectPath);
                newSceneDialog.open();
            }
            if (ImGui::MenuItem("New Folder"))
            {
                newFolderDialog.setParentPath(projectPath);
                newFolderDialog.open();
            }
            ImGui::EndPopup();
        }
        
        if (rootOpen)
        {
            renderFileTree(projectPath);
            ImGui::TreePop();
        }
    }
    else
    {
        ImGui::TextDisabled("Project path not found");
    }
    ImGui::EndChild();
    
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();
    
    // --- Section 2: Scenes List ---
    ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Scenes");
    ImGui::Separator();
    renderScenesList();
    
    ImGui::EndChild();
    
    ImGui::SameLine();
    
    // ═══════════════════════════════════════════════
    // Splitter (draggable edge)
    // ═══════════════════════════════════════════════
    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.2f, 0.2f, 0.2f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.4f, 0.4f, 0.4f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.5f, 0.5f, 0.5f, 1.0f));
    
    ImGui::Button("##Splitter", ImVec2(4.0f, -1));
    
    if (ImGui::IsItemHovered())
    {
        ImGui::SetMouseCursor(ImGuiMouseCursor_ResizeEW);
    }
    
    if (ImGui::IsItemActive())
    {
        float delta = ImGui::GetIO().MouseDelta.x;
        panelWidth += delta;
        panelWidth = std::clamp(panelWidth, 150.0f, 600.0f);
        ImGui::SetMouseCursor(ImGuiMouseCursor_ResizeEW);
    }
    
    ImGui::PopStyleColor(3);
    
    ImGui::SameLine();
    
    // ═══════════════════════════════════════════════
    // Center: 3D Viewport
    // ═══════════════════════════════════════════════
    float availWidth = ImGui::GetContentRegionAvail().x;
    float viewportWidth = availWidth - propertiesPanelWidth - 8.0f;  // 8 for splitter
    
    ImGui::BeginChild("ViewportRegion", ImVec2(viewportWidth, 0), false);
    renderViewport();
    ImGui::EndChild();
    
    ImGui::SameLine();
    
    // Splitter between viewport and properties
    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.2f, 0.2f, 0.2f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.4f, 0.4f, 0.4f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.5f, 0.5f, 0.5f, 1.0f));
    
    ImGui::Button("##PropertiesSplitter", ImVec2(4.0f, -1));
    
    if (ImGui::IsItemHovered())
    {
        ImGui::SetMouseCursor(ImGuiMouseCursor_ResizeEW);
    }
    
    if (ImGui::IsItemActive())
    {
        float delta = ImGui::GetIO().MouseDelta.x;
        propertiesPanelWidth -= delta;
        propertiesPanelWidth = std::clamp(propertiesPanelWidth, 200.0f, 500.0f);
        ImGui::SetMouseCursor(ImGuiMouseCursor_ResizeEW);
    }
    
    ImGui::PopStyleColor(3);
    
    ImGui::SameLine();
    
    // ═══════════════════════════════════════════════
    // Right Panel: Properties
    // ═══════════════════════════════════════════════
    renderPropertiesPanel();

    // Render dialogs
    if (newFolderDialog.render())
    {
        scanProjectScenes();
    }
    
    if (newSceneDialog.render())
    {
        scanProjectScenes();
        auto createdPath = newSceneDialog.getCreatedPath();
        if (!createdPath.empty())
        {
            selectedScenePath = createdPath;
            loadScene(createdPath);
        }
    }

    ImGui::End();
}

void ProjectScreen::renderFileTree(const std::filesystem::path& path)
{
    try {
        std::vector<std::filesystem::directory_entry> entries;
        for (const auto& entry : std::filesystem::directory_iterator(path))
        {
            if (entry.path().filename().string()[0] == '.')
                continue;
            entries.push_back(entry);
        }
        
        std::sort(entries.begin(), entries.end(), [](const auto& a, const auto& b) {
            if (a.is_directory() != b.is_directory())
                return a.is_directory();
            return a.path().filename() < b.path().filename();
        });
        
        for (const auto& entry : entries)
        {
            const auto& p = entry.path();
            std::string name = p.filename().string();
            
            if (entry.is_directory())
            {
                ImGuiTreeNodeFlags flags = ImGuiTreeNodeFlags_OpenOnArrow 
                                         | ImGuiTreeNodeFlags_SpanAvailWidth;
                
                if (selectedFilePath == p)
                    flags |= ImGuiTreeNodeFlags_Selected;
                
                bool open = ImGui::TreeNodeEx(name.c_str(), flags);
                
                if (ImGui::IsItemClicked() && !ImGui::IsItemToggledOpen())
                {
                    selectedFilePath = p;
                }
                
                if (ImGui::BeginPopupContextItem())
                {
                    if (ImGui::MenuItem("New Scene..."))
                    {
                        newSceneDialog.setLocation(p, projectPath);
                        newSceneDialog.open();
                    }
                    if (ImGui::MenuItem("New Folder"))
                    {
                        newFolderDialog.setParentPath(p);
                        newFolderDialog.open();
                    }
                    ImGui::Separator();
                    if (ImGui::MenuItem("Delete"))
                    {
                        deleteFileOrFolder(p);
                    }
                    ImGui::EndPopup();
                }
                
                if (open)
                {
                    renderFileTree(p);
                    ImGui::TreePop();
                }
            }
            else
            {
                ImGuiTreeNodeFlags flags = ImGuiTreeNodeFlags_Leaf 
                                         | ImGuiTreeNodeFlags_NoTreePushOnOpen
                                         | ImGuiTreeNodeFlags_SpanAvailWidth;
                
                // Highlight scene files and selected files
                bool isScene = isSceneFile(p.extension().string());
                if (selectedFilePath == p || (isScene && selectedScenePath == p))
                    flags |= ImGuiTreeNodeFlags_Selected;
                
                ImGui::TreeNodeEx(name.c_str(), flags);
                
                if (ImGui::IsItemClicked())
                {
                    selectedFilePath = p;
                    
                    // If it's a scene file, also load and view it
                    if (isScene)
                    {
                        selectedScenePath = p;
                        loadScene(p);
                    }
                }
                
                // Context menu for files
                if (ImGui::BeginPopupContextItem())
                {
                    if (ImGui::MenuItem("Delete"))
                    {
                        deleteFileOrFolder(p);
                    }
                    ImGui::EndPopup();
                }
                
                if (ImGui::IsItemHovered())
                {
                    ImGui::BeginTooltip();
                    ImGui::Text("%s", p.string().c_str());
                    ImGui::EndTooltip();
                }
            }
        }
    } catch (const std::filesystem::filesystem_error&) {
        ImGui::TextDisabled("Unable to read directory");
    }
}

void ProjectScreen::renderScenesList()
{
    if (scenes.empty())
    {
        ImGui::TextDisabled("No scenes found");
        return;
    }
    
    for (size_t i = 0; i < scenes.size(); ++i)
    {
        const auto& scene = scenes[i];
        bool selected = (selectedScenePath == scene.path);
        
        ImGui::PushID(static_cast<int>(i));
        
        // Draw scene icon
        ImVec2 pos = ImGui::GetCursorScreenPos();
        ImDrawList* drawList = ImGui::GetWindowDrawList();
        float r = 5.0f;
        ImVec2 center(pos.x + r + 2, pos.y + ImGui::GetTextLineHeight() * 0.5f);
        drawList->AddCircleFilled(center, r, IM_COL32(100, 180, 100, 255));
        
        ImGui::SetCursorPosX(ImGui::GetCursorPosX() + r * 2 + 8);
        
        if (ImGui::Selectable(scene.name.c_str(), selected))
        {
            selectedScenePath = scene.path;
            loadScene(scene.path);
        }
        
        if (ImGui::BeginPopupContextItem())
        {
            if (ImGui::MenuItem("Delete"))
            {
                deleteScene(scene.path);
            }
            ImGui::EndPopup();
        }
        
        ImGui::PopID();
    }
}

void ProjectScreen::deleteFileOrFolder(const std::filesystem::path& path)
{
    bool isDirectory = std::filesystem::is_directory(path);
    std::string itemType = isDirectory ? "folder" : "file";
    std::string message = "Are you sure you want to delete this " + itemType + "?\n" + path.filename().string();
    
    if (isDirectory)
    {
        message += "\n\nThis will delete all contents inside.";
    }
    
    int result = tinyfd_messageBox("Delete", message.c_str(), "yesno", "warning", 0);
    
    if (result == 1)  // User clicked Yes
    {
        try {
            // Check if it's a scene file that's currently selected
            bool isScene = isSceneFile(path.extension().string());
            if (isScene && selectedScenePath == path)
            {
                selectedScenePath.clear();
                selectedNode = nullptr;
                sceneRenderer.clearScene();
            }
            
            // Clear file selection if this was selected
            if (selectedFilePath == path)
            {
                selectedFilePath.clear();
            }
            
            // Delete file or folder (recursively for folders)
            if (isDirectory)
            {
                std::filesystem::remove_all(path);
            }
            else
            {
                std::filesystem::remove(path);
            }
            
            // Refresh scenes list in case a scene was deleted
            scanProjectScenes();
            
        } catch (const std::filesystem::filesystem_error&) {
            tinyfd_messageBox("Error", "Failed to delete.", "ok", "error", 1);
        }
    }
}

void ProjectScreen::deleteScene(const std::filesystem::path& scenePath)
{
    // Confirm deletion
    std::string message = "Are you sure you want to delete:\n" + scenePath.filename().string() + "?";
    int result = tinyfd_messageBox("Delete Scene", message.c_str(), "yesno", "warning", 0);
    
    if (result == 1)  // User clicked Yes
    {
        try {
            if (std::filesystem::remove(scenePath))
            {
                // If the deleted scene was selected, clear selection
                if (selectedScenePath == scenePath)
                {
                    selectedScenePath.clear();
                    selectedNode = nullptr;
                    sceneRenderer.clearScene();
                }
                if (selectedFilePath == scenePath)
                {
                    selectedFilePath.clear();
                }
                
                // Refresh the scenes list
                scanProjectScenes();
            }
        } catch (const std::filesystem::filesystem_error&) {
            tinyfd_messageBox("Error", "Failed to delete scene file.", "ok", "error", 1);
        }
    }
}

void ProjectScreen::renderViewport()
{
    ImGui::BeginChild("Viewport", ImVec2(0, 0), true, ImGuiWindowFlags_NoScrollbar);
    
    if (selectedScenePath.empty())
    {
        ImVec2 size = ImGui::GetContentRegionAvail();
        ImVec2 textSize = ImGui::CalcTextSize("Select a scene to view");
        ImGui::SetCursorPos(ImVec2((size.x - textSize.x) * 0.5f, (size.y - textSize.y) * 0.5f));
        ImGui::TextDisabled("Select a scene to view");
        ImGui::EndChild();
        return;
    }
    
    ImVec2 size = ImGui::GetContentRegionAvail();
    int w = std::max(1, static_cast<int>(size.x));
    int h = std::max(1, static_cast<int>(size.y));
    
    if (!rendererInitialized)
    {
        sceneRenderer.init(w, h);
        rendererInitialized = true;
    }
    else if (w != static_cast<int>(lastViewportWidth) || h != static_cast<int>(lastViewportHeight))
    {
        sceneRenderer.resize(w, h);
    }
    lastViewportWidth = size.x;
    lastViewportHeight = size.y;
    
    sceneRenderer.render();
    
    ImVec2 imagePos = ImGui::GetCursorScreenPos();
    ImGui::Image((ImTextureID)(intptr_t)sceneRenderer.getTextureID(), size, ImVec2(0, 1), ImVec2(1, 0));
    
    // Handle viewport interaction
    if (ImGui::IsItemHovered())
    {
        Camera& cam = sceneRenderer.getCamera();
        ImGuiIO& io = ImGui::GetIO();
        
        // Camera controls (dragging)
        bool isDragging = ImGui::IsMouseDragging(ImGuiMouseButton_Left) || 
                          ImGui::IsMouseDragging(ImGuiMouseButton_Middle) ||
                          ImGui::IsMouseDragging(ImGuiMouseButton_Right);
        
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Left))
            cam.orbit(io.MouseDelta.x, io.MouseDelta.y);
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Middle) || ImGui::IsMouseDragging(ImGuiMouseButton_Right))
            cam.pan(io.MouseDelta.x, io.MouseDelta.y);
        if (io.MouseWheel != 0)
            cam.zoom(io.MouseWheel);
        
        // Keyboard movement (arrow keys)
        const float moveSpeed = 0.5f;
        if (ImGui::IsKeyDown(ImGuiKey_UpArrow))
            cam.moveForward(moveSpeed);
        if (ImGui::IsKeyDown(ImGuiKey_DownArrow))
            cam.moveBackward(moveSpeed);
        if (ImGui::IsKeyDown(ImGuiKey_LeftArrow))
            cam.moveLeft(moveSpeed);
        if (ImGui::IsKeyDown(ImGuiKey_RightArrow))
            cam.moveRight(moveSpeed);
        
        // Object picking (only when not dragging)
        if (!isDragging)
        {
            // Calculate mouse position relative to viewport image
            float mouseX = io.MousePos.x - imagePos.x;
            float mouseY = io.MousePos.y - imagePos.y;
            
            // Pick object under cursor
            SceneNode* hoveredObject = sceneRenderer.pickObject(mouseX, mouseY);
            sceneRenderer.setHoveredNode(hoveredObject);
            
            // Show tooltip for hovered object
            if (hoveredObject)
            {
                ImGui::BeginTooltip();
                ImGui::TextColored(ImVec4(1.0f, 0.9f, 0.3f, 1.0f), "%s", hoveredObject->name.c_str());
                ImGui::TextColored(ImVec4(0.6f, 0.6f, 0.6f, 1.0f), "Type: %s", primTypeToString(hoveredObject->type));
                if (hoveredObject->type == PrimType::Mesh && hoveredObject->meshData)
                {
                    ImGui::TextColored(ImVec4(0.6f, 0.6f, 0.6f, 1.0f), "Vertices: %zu", hoveredObject->meshData->vertices.size());
                }
                ImGui::TextColored(ImVec4(0.5f, 0.7f, 0.9f, 1.0f), "Click to select");
                ImGui::EndTooltip();
                
                // Click to select
                if (ImGui::IsMouseClicked(ImGuiMouseButton_Left))
                {
                    selectedNode = hoveredObject;
                }
            }
            
            // Right-click context menu
            if (ImGui::IsMouseClicked(ImGuiMouseButton_Right))
            {
                contextMenuNode = hoveredObject;  // Store hovered node for context menu
                ImGui::OpenPopup("ViewportContextMenu");
            }
        }
        else
        {
            // Clear hover when dragging camera
            sceneRenderer.setHoveredNode(nullptr);
        }
    }
    else
    {
        // Clear hover when not over viewport
        sceneRenderer.setHoveredNode(nullptr);
    }
    
    // Viewport context menu
    if (ImGui::BeginPopup("ViewportContextMenu"))
    {
        // Only show "New" menu when not clicking on an object
        if (!contextMenuNode)
        {
            if (ImGui::BeginMenu("New"))
            {
                for (auto& tool : primitiveTools)
                {
                    if (ImGui::MenuItem(tool->getName()))
                    {
                        tool->onActivate(&currentScene);
                    }
                }
                ImGui::EndMenu();
            }
        }
        
        // Delete option (only if right-clicked on an object)
        if (contextMenuNode)
        {
            ImGui::Separator();
            if (ImGui::MenuItem("Delete", nullptr, false, contextMenuNode != nullptr))
            {
                // Clear selection if deleting selected node
                if (selectedNode == contextMenuNode)
                {
                    selectedNode = nullptr;
                }
                
                // Remove from parent
                if (contextMenuNode->parent)
                {
                    contextMenuNode->parent->removeChild(contextMenuNode);
                }
                
                // Update renderer and save
                sceneRenderer.setScene(&currentScene);
                saveScene();
                
                contextMenuNode = nullptr;
            }
        }
        
        ImGui::EndPopup();
    }
    
    // Render tool popups/logic
    for (auto& tool : primitiveTools)
    {
        SceneNode* newNode = tool->render();
        if (newNode)
        {
            // Node was created
            sceneRenderer.setScene(&currentScene);
            saveScene();
            selectedNode = newNode;
        }
    }
    
    // Camera control buttons overlay (top-right)
    renderCameraControls();
    
    ImGui::EndChild();
}

void ProjectScreen::renderCameraControls()
{
    ImGuiWindowFlags overlayFlags = ImGuiWindowFlags_NoDecoration 
                                   | ImGuiWindowFlags_AlwaysAutoResize 
                                   | ImGuiWindowFlags_NoSavedSettings 
                                   | ImGuiWindowFlags_NoFocusOnAppearing 
                                   | ImGuiWindowFlags_NoNav
                                   | ImGuiWindowFlags_NoMove;
    
    // Position at top-right of the viewport child window
    ImVec2 windowPos = ImGui::GetWindowPos();
    ImVec2 windowSize = ImGui::GetWindowSize();
    float padding = 10.0f;
    
    ImGui::SetNextWindowPos(ImVec2(windowPos.x + windowSize.x - padding, windowPos.y + 35.0f), ImGuiCond_Always, ImVec2(1.0f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.7f);
    
    if (ImGui::Begin("##CameraControls", nullptr, overlayFlags))
    {
        Camera& cam = sceneRenderer.getCamera();
        
        // Reset button
        if (ImGui::Button("Reset"))
        {
            cam.reset();
        }
        
        ImGui::SameLine();
        
        // Zoom buttons
        if (ImGui::Button("-"))
        {
            cam.zoom(-2.0f);
        }
        ImGui::SameLine();
        if (ImGui::Button("+"))
        {
            cam.zoom(2.0f);
        }
        
        ImGui::SameLine();
        ImGui::Spacing();
        ImGui::SameLine();
        
        // View presets for planes
        if (ImGui::Button("XY"))
        {
            cam.reset();
            cam.orbit(150, -100);  // yaw=0, pitch=0 - View XY plane (looking along Z)
        }
        ImGui::SameLine();
        if (ImGui::Button("XZ"))
        {
            cam.reset();
            cam.orbit(150, 197);  // yaw=0, pitch=89 - View XZ plane (top-down)
        }
        ImGui::SameLine();
        if (ImGui::Button("YZ"))
        {
            cam.reset();
            cam.orbit(-150, -100);  // yaw=90, pitch=0 - View YZ plane (looking along X)
        }
    }
    ImGui::End();
}

void ProjectScreen::renderPropertiesPanel()
{
    ImGui::BeginChild("PropertiesPanel", ImVec2(0, 0), true);
    
    if (selectedScenePath.empty())
    {
        ImGui::TextDisabled("No scene loaded");
        ImGui::EndChild();
        return;
    }
    
    // Header with back button if a node is selected
    if (selectedNode)
    {
        // Store name before potentially clearing the pointer
        std::string nodeName = selectedNode->name;
        
        if (ImGui::Button("<< Scene"))
        {
            selectedNode = nullptr;
        }
        
        // Only show the name if we still have a selected node
        if (selectedNode)
        {
            ImGui::SameLine();
            ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Object: %s", nodeName.c_str());
        }
    }
    
    if (!selectedNode)
    {
        ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Scene Properties");
    }
    
    ImGui::Separator();
    ImGui::Spacing();
    
    // Show appropriate properties
    if (selectedNode)
    {
        renderNodeProperties(selectedNode);
    }
    else
    {
        renderSceneProperties();
    }
    
    ImGui::EndChild();
}

void ProjectScreen::renderSceneProperties()
{
    // Scene name
    ImGui::Text("Name:");
    ImGui::SameLine(100);
    ImGui::TextColored(ImVec4(1.0f, 1.0f, 1.0f, 1.0f), "%s", currentScene.name.c_str());
    
    ImGui::Spacing();
    
    // Scene metadata
    ImGui::Text("Up Axis:");
    ImGui::SameLine(100);
    ImGui::Text("%s", currentScene.upAxis.c_str());
    
    ImGui::Text("Units:");
    ImGui::SameLine(100);
    ImGui::Text("%.2f m/unit", currentScene.metersPerUnit);
    
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();
    
    // Scene hierarchy
    ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Hierarchy");
    ImGui::Separator();
    
    if (currentScene.root)
    {
        // Recursive function to render hierarchy
        std::function<void(SceneNode*, int)> renderNode = [&](SceneNode* node, int depth)
        {
            ImGuiTreeNodeFlags flags = ImGuiTreeNodeFlags_OpenOnArrow 
                                     | ImGuiTreeNodeFlags_SpanAvailWidth;
            
            if (node->children.empty())
            {
                flags |= ImGuiTreeNodeFlags_Leaf;
            }
            
            // Highlight meshes differently
            if (node->type == PrimType::Mesh)
            {
                ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.5f, 0.8f, 1.0f, 1.0f));
            }
            
            bool open = ImGui::TreeNodeEx(node->name.c_str(), flags);
            
            if (node->type == PrimType::Mesh)
            {
                ImGui::PopStyleColor();
            }
            
            // Click to select (not on root)
            if (ImGui::IsItemClicked() && node != currentScene.root.get())
            {
                selectedNode = node;
            }
            
            if (open)
            {
                for (const auto& child : node->children)
                {
                    renderNode(child.get(), depth + 1);
                }
                ImGui::TreePop();
            }
        };
        
        renderNode(currentScene.root.get(), 0);
    }
}

void ProjectScreen::renderNodeProperties(SceneNode* node)
{
    if (!node) return;
    
    // Node info
    ImGui::Text("Name:");
    ImGui::SameLine(100);
    ImGui::TextColored(ImVec4(1.0f, 1.0f, 1.0f, 1.0f), "%s", node->name.c_str());
    
    ImGui::Text("Type:");
    ImGui::SameLine(100);
    ImGui::Text("%s", primTypeToString(node->type));
    
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();
    
    // Mesh-specific properties
    if (node->type == PrimType::Mesh && node->meshData)
    {
        ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Mesh Data");
        ImGui::Separator();
        
        ImGui::Text("Vertices:");
        ImGui::SameLine(100);
        ImGui::Text("%zu", node->meshData->vertices.size());
        
        ImGui::Text("Triangles:");
        ImGui::SameLine(100);
        ImGui::Text("%zu", node->meshData->indices.size() / 3);
        
        ImGui::Spacing();
        
        // Display color
        ImGui::Text("Color:");
        glm::vec3& color = node->meshData->displayColor;
        float colorArr[3] = { color.r, color.g, color.b };
        if (ImGui::ColorEdit3("##MeshColor", colorArr))
        {
            color.r = colorArr[0];
            color.g = colorArr[1];
            color.b = colorArr[2];
            // Update the GPU mesh
            sceneRenderer.setScene(&currentScene);
            // Auto-save changes
            saveScene();
        }
        
        ImGui::Spacing();
        ImGui::Separator();
        ImGui::Spacing();
        
        // Physics properties section
        ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Physics");
        ImGui::Separator();
        
        // Single collision checkbox
        bool collision = node->meshData->collision;
        if (ImGui::Checkbox("Collision", &collision))
        {
            node->meshData->collision = collision;
            saveScene();
        }
        if (ImGui::IsItemHovered())
        {
            ImGui::SetTooltip("Applies PhysicsCollisionAPI schema");
        }
    }
    
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();
    
    // Children count
    if (!node->children.empty())
    {
        ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Children (%zu)", node->children.size());
        ImGui::Separator();
        
        for (const auto& child : node->children)
        {
            ImGuiTreeNodeFlags flags = ImGuiTreeNodeFlags_Leaf | ImGuiTreeNodeFlags_SpanAvailWidth;
            
            if (child->type == PrimType::Mesh)
            {
                ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.5f, 0.8f, 1.0f, 1.0f));
            }
            
            if (ImGui::TreeNodeEx(child->name.c_str(), flags))
            {
                ImGui::TreePop();
            }
            
            if (child->type == PrimType::Mesh)
            {
                ImGui::PopStyleColor();
            }
            
            if (ImGui::IsItemClicked())
            {
                selectedNode = child.get();
            }
        }
    }
}

void ProjectScreen::loadScene(const std::filesystem::path& scenePath)
{
    // Clear selection when loading a new scene
    selectedNode = nullptr;
    
    // Load the scene and pass to renderer
    if (currentScene.loadFromFile(scenePath))
    {
        sceneRenderer.setScene(&currentScene);
    }
    else
    {
        sceneRenderer.clearScene();
    }
}

void ProjectScreen::saveScene()
{
    if (!selectedScenePath.empty())
    {
        currentScene.saveToFile(selectedScenePath);
    }
}

