#include "project_screen.h"
#include "welcome_screen.h"
#include "imgui.h"

#include <algorithm>
#include <cstring>

// File extension categories (OpenUSD-compatible formats)
static const std::vector<std::string> SCENE_EXTENSIONS = {".usda", ".usdc", ".usd", ".usdz"};
static const std::vector<std::string> MODEL_EXTENSIONS = {".usda", ".usdc", ".usd", ".usdz", ".obj", ".fbx", ".gltf", ".glb"};

static bool hasExtension(const std::string& ext, const std::vector<std::string>& extensions)
{
    std::string lowerExt = ext;
    std::transform(lowerExt.begin(), lowerExt.end(), lowerExt.begin(), ::tolower);
    return std::find(extensions.begin(), extensions.end(), lowerExt) != extensions.end();
}

ProjectScreen::ProjectScreen(std::filesystem::path& path)
    : projectPath(path) {}

void ProjectScreen::onEnter()
{
    scanProjectAssets();
}

void ProjectScreen::scanProjectAssets()
{
    // Clear existing
    scenes.clear();
    models.clear();
    
    // Scan the project directory
    if (std::filesystem::exists(projectPath) && std::filesystem::is_directory(projectPath))
    {
        scanDirectory(projectPath);
    }
    
    // Sort all lists by name
    auto sortByName = [](const AssetInfo& a, const AssetInfo& b) {
        return a.name < b.name;
    };
    std::sort(scenes.begin(), scenes.end(), sortByName);
    std::sort(models.begin(), models.end(), sortByName);
}

void ProjectScreen::scanDirectory(const std::filesystem::path& dir)
{
    try {
        for (const auto& entry : std::filesystem::directory_iterator(dir))
        {
            if (entry.is_directory())
            {
                // Skip hidden directories and common non-asset folders
                std::string name = entry.path().filename().string();
                if (name[0] != '.' && name != "build" && name != "node_modules")
                {
                    scanDirectory(entry.path());
                }
            }
            else if (entry.is_regular_file())
            {
                categorizeAsset(entry.path());
            }
        }
    } catch (const std::filesystem::filesystem_error&) {
        // Permission denied or other filesystem error - skip
    }
}

void ProjectScreen::categorizeAsset(const std::filesystem::path& path)
{
    std::string ext = path.extension().string();
    if (ext.empty()) return;
    
    AssetInfo info;
    info.name = path.filename().string();
    info.path = path;
    info.extension = ext;
    
    if (hasExtension(ext, SCENE_EXTENSIONS))
    {
        scenes.push_back(info);
    }
    else if (hasExtension(ext, MODEL_EXTENSIONS))
    {
        models.push_back(info);
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
                if (ImGui::MenuItem("Folder"))
                {
                    // Create folder in project root or selected directory
                    std::filesystem::path parentPath = projectPath;
                    if (!selectedFilePath.empty() && std::filesystem::is_directory(selectedFilePath))
                    {
                        parentPath = selectedFilePath;
                    }
                    openNewFolderDialog(parentPath);
                }
                ImGui::EndMenu();
            }
            ImGui::Separator();
            if (ImGui::MenuItem("Refresh Assets", "Ctrl+R"))
            {
                scanProjectAssets();
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
        // Root project folder
        ImGuiTreeNodeFlags rootFlags = ImGuiTreeNodeFlags_OpenOnArrow 
                                     | ImGuiTreeNodeFlags_DefaultOpen
                                     | ImGuiTreeNodeFlags_SpanAvailWidth;
        
        bool rootOpen = ImGui::TreeNodeEx(projectPath.filename().string().c_str(), rootFlags);
        
        // Right-click context menu for root folder
        if (ImGui::BeginPopupContextItem())
        {
            if (ImGui::MenuItem("New Folder"))
            {
                openNewFolderDialog(projectPath);
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
    
    // --- Section 2: Assets Browser (Tabbed) ---
    if (ImGui::BeginTabBar("AssetTabs", ImGuiTabBarFlags_FittingPolicyScroll))
    {
        // Scenes Tab
        if (ImGui::BeginTabItem("Scenes"))
        {
            renderAssetList(scenes, "No scenes found");
            ImGui::EndTabItem();
        }
        
        // Models Tab
        if (ImGui::BeginTabItem("Models"))
        {
            renderAssetList(models, "No models found");
            ImGui::EndTabItem();
        }
        
        ImGui::EndTabBar();
    }
    
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
    // Right Panel: Main Viewport / Editor Area
    // ═══════════════════════════════════════════════
    ImGui::BeginChild("Viewport", ImVec2(0, 0), true);
    
    // Show selected file info
    if (!selectedFilePath.empty())
    {
        ImGui::Text("Selected File:");
        ImGui::TextWrapped("%s", selectedFilePath.string().c_str());
        ImGui::Spacing();
    }
    
    if (!selectedAssetPath.empty())
    {
        ImGui::Text("Selected Asset:");
        ImGui::TextWrapped("%s", selectedAssetPath.string().c_str());
    }
    
    if (selectedFilePath.empty() && selectedAssetPath.empty())
    {
        ImGui::TextDisabled("Select a file or asset to view details");
    }
    
    ImGui::EndChild();

    // Render the new folder popup if open
    renderNewFolderPopup();

    ImGui::End();
}

void ProjectScreen::renderFileTree(const std::filesystem::path& path)
{
    try {
        // Collect entries and sort (directories first, then alphabetically)
        std::vector<std::filesystem::directory_entry> entries;
        for (const auto& entry : std::filesystem::directory_iterator(path))
        {
            // Skip hidden files/folders
            if (entry.path().filename().string()[0] == '.')
                continue;
            entries.push_back(entry);
        }
        
        std::sort(entries.begin(), entries.end(), [](const auto& a, const auto& b) {
            // Directories first
            if (a.is_directory() != b.is_directory())
                return a.is_directory();
            // Then alphabetically
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
                
                // Right-click context menu for directories
                if (ImGui::BeginPopupContextItem())
                {
                    if (ImGui::MenuItem("New Folder"))
                    {
                        openNewFolderDialog(p);
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
                
                if (selectedFilePath == p)
                    flags |= ImGuiTreeNodeFlags_Selected;
                
                // Add file type indicator
                std::string ext = p.extension().string();
                std::string displayName = name;
                
                ImGui::TreeNodeEx(displayName.c_str(), flags);
                
                if (ImGui::IsItemClicked())
                {
                    selectedFilePath = p;
                }
                
                // Tooltip with full path
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

void ProjectScreen::renderAssetList(const std::vector<AssetInfo>& assets, const char* emptyMessage)
{
    if (assets.empty())
    {
        ImGui::TextDisabled("%s", emptyMessage);
        return;
    }
    
    for (const auto& asset : assets)
    {
        bool selected = (selectedAssetPath == asset.path);
        
        // Show extension as a badge
        ImGui::TextDisabled("%s", asset.extension.c_str());
        ImGui::SameLine();
        
        if (ImGui::Selectable(asset.name.c_str(), selected))
        {
            selectedAssetPath = asset.path;
        }
        
        // Tooltip with full path
        if (ImGui::IsItemHovered())
        {
            ImGui::BeginTooltip();
            ImGui::Text("%s", asset.path.string().c_str());
            ImGui::EndTooltip();
        }
    }
}

void ProjectScreen::openNewFolderDialog(const std::filesystem::path& parentPath)
{
    newFolderParentPath = parentPath;
    std::memset(newFolderName, 0, sizeof(newFolderName));
    std::strcpy(newFolderName, "New Folder");
    showNewFolderPopup = true;
    ImGui::OpenPopup("New Folder");
}

void ProjectScreen::createNewFolder()
{
    if (std::strlen(newFolderName) == 0) return;
    
    std::filesystem::path newPath = newFolderParentPath / newFolderName;
    
    try {
        if (!std::filesystem::exists(newPath))
        {
            std::filesystem::create_directory(newPath);
            selectedFilePath = newPath;
        }
    } catch (const std::filesystem::filesystem_error&) {
        // Failed to create folder
    }
}

void ProjectScreen::renderNewFolderPopup()
{
    if (showNewFolderPopup)
    {
        ImGui::OpenPopup("New Folder");
        showNewFolderPopup = false;
    }
    
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
    
    if (ImGui::BeginPopupModal("New Folder", nullptr, ImGuiWindowFlags_AlwaysAutoResize))
    {
        ImGui::Text("Create new folder in:");
        ImGui::TextColored(ImVec4(0.7f, 0.7f, 0.7f, 1.0f), "%s", newFolderParentPath.string().c_str());
        ImGui::Spacing();
        
        ImGui::Text("Folder name:");
        ImGui::SetNextItemWidth(300);
        
        bool enterPressed = ImGui::InputText("##FolderName", newFolderName, sizeof(newFolderName), 
                                              ImGuiInputTextFlags_EnterReturnsTrue);
        
        // Focus the input field when popup opens
        if (ImGui::IsWindowAppearing())
        {
            ImGui::SetKeyboardFocusHere(-1);
        }
        
        ImGui::Spacing();
        ImGui::Separator();
        ImGui::Spacing();
        
        if (ImGui::Button("Create", ImVec2(120, 0)) || enterPressed)
        {
            createNewFolder();
            ImGui::CloseCurrentPopup();
        }
        
        ImGui::SameLine();
        
        if (ImGui::Button("Cancel", ImVec2(120, 0)))
        {
            ImGui::CloseCurrentPopup();
        }
        
        ImGui::EndPopup();
    }
}
