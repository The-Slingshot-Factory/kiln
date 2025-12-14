#include "project_screen.h"
#include "welcome_screen.h"
#include "imgui.h"

#include <algorithm>
#include <cstring>

// Scene file extensions (OpenUSD formats)
static const std::vector<std::string> SCENE_EXTENSIONS = {".usda", ".usdc", ".usd", ".usdz"};

static bool isSceneFile(const std::string& ext)
{
    std::string lowerExt = ext;
    std::transform(lowerExt.begin(), lowerExt.end(), lowerExt.begin(), ::tolower);
    return std::find(SCENE_EXTENSIONS.begin(), SCENE_EXTENSIONS.end(), lowerExt) != SCENE_EXTENSIONS.end();
}

ProjectScreen::ProjectScreen(std::filesystem::path& path)
    : projectPath(path) {}

void ProjectScreen::onEnter()
{
    scanProjectScenes();
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
                    info.name = entry.path().filename().string();
                    info.path = entry.path();
                    info.extension = ext;
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
                if (ImGui::MenuItem("Folder"))
                {
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
    // Right Panel: Main Viewport / Editor Area
    // ═══════════════════════════════════════════════
    ImGui::BeginChild("Viewport", ImVec2(0, 0), true);
    
    if (!selectedFilePath.empty())
    {
        ImGui::Text("Selected File:");
        ImGui::TextWrapped("%s", selectedFilePath.string().c_str());
        ImGui::Spacing();
    }
    
    if (!selectedScenePath.empty())
    {
        ImGui::Text("Selected Scene:");
        ImGui::TextWrapped("%s", selectedScenePath.string().c_str());
    }
    
    if (selectedFilePath.empty() && selectedScenePath.empty())
    {
        ImGui::TextDisabled("Select a file or scene to view details");
    }
    
    ImGui::EndChild();

    renderNewFolderPopup();

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
                
                ImGui::TreeNodeEx(name.c_str(), flags);
                
                if (ImGui::IsItemClicked())
                {
                    selectedFilePath = p;
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
    
    for (const auto& scene : scenes)
    {
        bool selected = (selectedScenePath == scene.path);
        
        ImGui::TextDisabled("%s", scene.extension.c_str());
        ImGui::SameLine();
        
        if (ImGui::Selectable(scene.name.c_str(), selected))
        {
            selectedScenePath = scene.path;
        }
        
        if (ImGui::IsItemHovered())
        {
            ImGui::BeginTooltip();
            ImGui::Text("%s", scene.path.string().c_str());
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
