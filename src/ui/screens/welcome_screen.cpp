#include "welcome_screen.h"
#include "project_screen.h"
#include "imgui.h"
#include "tinyfiledialogs.h"

#include <fstream>
#include <algorithm>
#include <cstdlib>

WelcomeScreen::WelcomeScreen(std::filesystem::path& path)
    : projectPath(path) 
{
    configFilePath = getConfigDirectory() / "recent_projects.txt";
}

void WelcomeScreen::onEnter()
{
    loadRecentProjects();
}

std::filesystem::path WelcomeScreen::getConfigDirectory()
{
    std::filesystem::path configDir;
    
#ifdef _WIN32
    const char* appdata = std::getenv("APPDATA");
    if (appdata) {
        configDir = std::filesystem::path(appdata) / "Kiln";
    } else {
        configDir = std::filesystem::path(".") / ".kiln";
    }
#elif __APPLE__
    const char* home = std::getenv("HOME");
    if (home) {
        configDir = std::filesystem::path(home) / "Library" / "Application Support" / "Kiln";
    } else {
        configDir = std::filesystem::path(".") / ".kiln";
    }
#else
    const char* xdgConfig = std::getenv("XDG_CONFIG_HOME");
    if (xdgConfig) {
        configDir = std::filesystem::path(xdgConfig) / "kiln";
    } else {
        const char* home = std::getenv("HOME");
        if (home) {
            configDir = std::filesystem::path(home) / ".config" / "kiln";
        } else {
            configDir = std::filesystem::path(".") / ".kiln";
        }
    }
#endif
    
    try {
        if (!std::filesystem::exists(configDir)) {
            std::filesystem::create_directories(configDir);
        }
    } catch (const std::filesystem::filesystem_error&) {
    }
    
    return configDir;
}

void WelcomeScreen::loadRecentProjects()
{
    recentProjects.clear();
    
    std::ifstream file(configFilePath);
    if (!file.is_open()) return;
    
    std::string line;
    while (std::getline(file, line))
    {
        if (!line.empty())
        {
            std::filesystem::path path(line);
            if (std::filesystem::exists(path) && std::filesystem::is_directory(path))
            {
                recentProjects.push_back(path);
            }
        }
        
        if (recentProjects.size() >= MAX_RECENT_PROJECTS)
            break;
    }
}

void WelcomeScreen::saveRecentProjects()
{
    std::ofstream file(configFilePath);
    if (!file.is_open()) return;
    
    for (const auto& project : recentProjects)
    {
        file << project.string() << "\n";
    }
}

void WelcomeScreen::addRecentProject(const std::filesystem::path& path)
{
    std::filesystem::path normalizedPath = std::filesystem::absolute(path);
    
    auto it = std::find(recentProjects.begin(), recentProjects.end(), normalizedPath);
    if (it != recentProjects.end())
    {
        recentProjects.erase(it);
    }
    
    recentProjects.insert(recentProjects.begin(), normalizedPath);
    
    if (recentProjects.size() > MAX_RECENT_PROJECTS)
    {
        recentProjects.resize(MAX_RECENT_PROJECTS);
    }
    
    saveRecentProjects();
}

void WelcomeScreen::removeRecentProject(const std::filesystem::path& path)
{
    std::filesystem::path normalizedPath = std::filesystem::absolute(path);
    
    auto it = std::find(recentProjects.begin(), recentProjects.end(), normalizedPath);
    if (it != recentProjects.end())
    {
        recentProjects.erase(it);
        saveRecentProjects();
    }
}

void WelcomeScreen::openProject(const std::filesystem::path& path)
{
    projectPath = path;
    addRecentProject(path);
    switchTo<ProjectScreen>(projectPath);
}

void WelcomeScreen::update()
{
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(viewport->Pos);
    ImGui::SetNextWindowSize(viewport->Size);

    ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar
                           | ImGuiWindowFlags_NoResize
                           | ImGuiWindowFlags_NoMove
                           | ImGuiWindowFlags_NoCollapse
                           | ImGuiWindowFlags_NoBringToFrontOnFocus;

    ImGui::Begin("Welcome", nullptr, flags);

    float windowWidth = ImGui::GetWindowWidth();
    float windowHeight = ImGui::GetWindowHeight();
    
    float buttonWidth = 200.0f;
    float buttonHeight = 40.0f;
    float spacing = 20.0f;
    
    // Title
    ImGui::SetCursorPosY(60.0f);
    const char* title = "Welcome to Kiln";
    float titleWidth = ImGui::CalcTextSize(title).x;
    ImGui::SetCursorPosX((windowWidth - titleWidth) / 2.0f);
    ImGui::Text("%s", title);

    ImGui::Dummy(ImVec2(0, 30));

    // Buttons (centered)
    float totalButtonWidth = buttonWidth * 2 + spacing;
    ImGui::SetCursorPosX((windowWidth - totalButtonWidth) / 2.0f);

    if (ImGui::Button("New Project", ImVec2(buttonWidth, buttonHeight)))
    {
        const char* name = tinyfd_inputBox("New Project", "Enter project name:", "MyProject");
        if (name && name[0] != '\0')
        {
            const char* parentPath = tinyfd_selectFolderDialog("Select location for new project", nullptr);
            if (parentPath)
            {
                std::filesystem::path newPath = std::filesystem::path(parentPath) / name;
                if (std::filesystem::exists(newPath))
                {
                    tinyfd_messageBox("Error", "A project with this name already exists.", "ok", "error", 1);
                }
                else
                {
                    std::filesystem::create_directories(newPath);
                    openProject(newPath);
                }
            }
        }
    }

    ImGui::SameLine(0, spacing);

    if (ImGui::Button("Open Project", ImVec2(buttonWidth, buttonHeight)))
    {
        const char* path = tinyfd_selectFolderDialog("Select project folder", nullptr);
        if (path)
        {
            openProject(std::filesystem::path(path));
        }
    }

    // Recent Projects (below buttons)
    if (!recentProjects.empty())
    {
        ImGui::Dummy(ImVec2(0, 30));
        
        float panelWidth = 500.0f;
        float panelHeight = windowHeight - ImGui::GetCursorPosY() - 40.0f;
        
        ImGui::SetCursorPosX((windowWidth - panelWidth) / 2.0f);
        ImGui::BeginChild("RecentPanel", ImVec2(panelWidth, panelHeight), true);
        
        ImGui::TextColored(ImVec4(0.7f, 0.9f, 1.0f, 1.0f), "Recent Projects");
        ImGui::Separator();
        ImGui::Spacing();
        
        for (size_t i = 0; i < recentProjects.size(); ++i)
        {
            const auto& path = recentProjects[i];
            std::string projectName = path.filename().string();
            std::string pathStr = path.string();
            
            ImGui::PushID(static_cast<int>(i));
            
            if (ImGui::Selectable(projectName.c_str(), false, 0, ImVec2(0, 24)))
            {
                if (std::filesystem::exists(path))
                {
                    openProject(path);
                }
                else
                {
                    tinyfd_messageBox("Error", "This project no longer exists.", "ok", "error", 1);
                    removeRecentProject(path);
                }
            }
            
            if (ImGui::IsItemHovered())
            {
                ImGui::BeginTooltip();
                ImGui::Text("%s", pathStr.c_str());
                ImGui::EndTooltip();
            }
            
            if (ImGui::BeginPopupContextItem())
            {
                if (ImGui::MenuItem("Remove from Recent"))
                {
                    removeRecentProject(path);
                }
                ImGui::EndPopup();
            }
            
            ImGui::TextDisabled("  %s", pathStr.c_str());
            
            ImGui::PopID();
            ImGui::Spacing();
        }
        
        ImGui::EndChild();
    }

    ImGui::End();
}
