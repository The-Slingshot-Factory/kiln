#include "config.h"
#include "paths.h"
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include "tinyfiledialogs.h"

#include <GLFW/glfw3.h>
#include <filesystem>

enum class Screen { Welcome, Project };

int main(int, char**)
{
    glfwInit();
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);

    GLFWwindow* window = glfwCreateWindow(WINDOW_WIDTH, WINDOW_HEIGHT, APP_NAME, nullptr, nullptr);
    glfwMakeContextCurrent(window);
    glfwSwapInterval(1);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGui::StyleColorsDark();

    // Load Inter font
    ImGuiIO& io = ImGui::GetIO();
    io.Fonts->AddFontFromFileTTF(FONT_PATH, 18.0f);

    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    // App state
    Screen currentScreen = Screen::Welcome;
    std::filesystem::path projectPath;

    while (!glfwWindowShouldClose(window))
    {
        glfwPollEvents();

        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        const ImGuiViewport* viewport = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(viewport->Pos);
        ImGui::SetNextWindowSize(viewport->Size);

        ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar
                               | ImGuiWindowFlags_NoResize
                               | ImGuiWindowFlags_NoMove
                               | ImGuiWindowFlags_NoCollapse
                               | ImGuiWindowFlags_NoBringToFrontOnFocus;

        if (currentScreen == Screen::Welcome)
        {
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
                        currentScreen = Screen::Project;
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
                    currentScreen = Screen::Project;
                }
            }

            ImGui::End();
        }
        else if (currentScreen == Screen::Project)
        {
            ImGuiWindowFlags projectFlags = flags | ImGuiWindowFlags_MenuBar;
            ImGui::Begin("Project", nullptr, projectFlags);

            if (ImGui::BeginMenuBar())
            {
                if (ImGui::BeginMenu("File"))
                {
                    if (ImGui::MenuItem("Close Project"))
                    {
                        projectPath.clear();
                        currentScreen = Screen::Welcome;
                    }
                    ImGui::EndMenu();
                }
                ImGui::EndMenuBar();
            }

            ImGui::Text("Project: %s", projectPath.filename().string().c_str());
            ImGui::Text("Path: %s", projectPath.string().c_str());

            ImGui::End();
        }

        ImGui::Render();
        int w, h;
        glfwGetFramebufferSize(window, &w, &h);
        glViewport(0, 0, w, h);
        glClearColor(0.1f, 0.1f, 0.1f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

        glfwSwapBuffers(window);
    }

    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();

    return 0;
}
