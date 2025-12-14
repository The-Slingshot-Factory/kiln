#include "project_screen.h"
#include "welcome_screen.h"
#include "imgui.h"

ProjectScreen::ProjectScreen(std::filesystem::path& path)
    : projectPath(path) {}

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

    if (ImGui::BeginMenuBar())
    {
        if (ImGui::BeginMenu("File"))
        {
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

    ImGui::Text("Project: %s", projectPath.filename().string().c_str());
    ImGui::Text("Path: %s", projectPath.string().c_str());

    ImGui::End();
}

