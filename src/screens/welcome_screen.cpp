#include "welcome_screen.h"
#include "project_screen.h"
#include "imgui.h"
#include "tinyfiledialogs.h"

WelcomeScreen::WelcomeScreen(std::filesystem::path& path)
    : projectPath(path) {}

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

    float windowHeight = ImGui::GetWindowHeight();
    float contentHeight = 100.0f;
    ImGui::SetCursorPosY((windowHeight - contentHeight) / 2.0f);

    const char* title = "Welcome to Kiln";
    float titleWidth = ImGui::CalcTextSize(title).x;
    ImGui::SetCursorPosX((ImGui::GetWindowWidth() - titleWidth) / 2.0f);
    ImGui::Text("%s", title);

    ImGui::Dummy(ImVec2(0, 30));

    float buttonWidth = 200.0f;
    float buttonHeight = 40.0f;
    float spacing = 20.0f;
    float totalWidth = buttonWidth * 2 + spacing;
    ImGui::SetCursorPosX((ImGui::GetWindowWidth() - totalWidth) / 2.0f);

    if (ImGui::Button("New Project", ImVec2(buttonWidth, buttonHeight)))
    {
        const char* projectName = tinyfd_inputBox("New Project", "Enter project name:", "MyProject");
        if (projectName && projectName[0] != '\0')
        {
            const char* parentPath = tinyfd_selectFolderDialog("Select location for new project", nullptr);
            if (parentPath)
            {
                projectPath = std::filesystem::path(parentPath) / projectName;
                std::filesystem::create_directories(projectPath);
                switchTo<ProjectScreen>(projectPath);
            }
        }
    }

    ImGui::SameLine(0, spacing);

    if (ImGui::Button("Open Project", ImVec2(buttonWidth, buttonHeight)))
    {
        const char* path = tinyfd_selectFolderDialog("Select project folder", nullptr);
        if (path)
        {
            projectPath = path;
            switchTo<ProjectScreen>(projectPath);
        }
    }

    ImGui::End();
}

